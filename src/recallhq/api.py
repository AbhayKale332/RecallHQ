"""Public, read-only chat API for the frozen synthetic corpus."""

import os
import re
import sqlite3
import time
from datetime import date, datetime, timedelta, timezone
from datetime import time as day_time
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from recallhq.db import DEMO_CONTEXT, connect
from recallhq.retrieval.service import SETTINGS, answer, rerank, retrieve

app = FastAPI(title="RecallHQ", docs_url=None, redoc_url=None)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://recall.abhaykale.me"],
    allow_origin_regex=r"https://[a-z0-9-]+\.vercel\.app",
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

CHANNELS = ("eng", "product", "ops", "build-help", "random")
QUOTA_DB = Path(os.getenv("QUOTA_DB", "/tmp/recallhq-quotas.sqlite3"))
MESSAGE_FIELDS = "id, channel_id AS channel, author_id AS author, author_name, text, created_at, thread_root_id"


class CommandInput(BaseModel):
    input: str = Field(min_length=1, max_length=1200)


def db():
    return connect(SETTINGS, DEMO_CONTEXT)


def check_quota(client_ip: str) -> None:
    """SQLite makes limits durable and atomic for the single VM deployment."""
    now = int(time.time())
    buckets = (
        ("minute", client_ip, now // 60, 3),
        ("day", client_ip, now // 86400, 20),
        ("global", "all", now // 86400, 200),
    )
    QUOTA_DB.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(QUOTA_DB, timeout=5) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS usage (kind text, subject text, period integer, count integer NOT NULL, PRIMARY KEY (kind, subject, period))")
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("DELETE FROM usage WHERE period < ? AND kind = 'minute'", (now // 60 - 1,))
        conn.execute("DELETE FROM usage WHERE period < ? AND kind != 'minute'", (now // 86400 - 1,))
        for kind, subject, period, limit in buckets:
            row = conn.execute("SELECT count FROM usage WHERE kind = ? AND subject = ? AND period = ?", (kind, subject, period)).fetchone()
            if row and row[0] >= limit:
                raise HTTPException(429, "Demo command limit reached. Please try again later.")
        for kind, subject, period, _ in buckets:
            conn.execute("INSERT INTO usage VALUES (?, ?, ?, 1) ON CONFLICT(kind, subject, period) DO UPDATE SET count = count + 1", (kind, subject, period))


@app.get("/health")
def health():
    with db() as conn:
        conn.execute("SELECT 1")
    return {"status": "ok"}


@app.get("/channels")
def channels():
    with db() as conn:
        rows = conn.execute("SELECT channel_id AS id, channel_name AS name, count(*) AS messages FROM messages WHERE source = 'synthetic' AND workspace_id = 'beacon' GROUP BY channel_id, channel_name").fetchall()
    return sorted(rows, key=lambda row: CHANNELS.index(row["id"]) if row["id"] in CHANNELS else len(CHANNELS))


@app.get("/messages")
def messages(channel: str, before: str | None = None, limit: int = Query(30, ge=1, le=50)):
    if channel not in CHANNELS:
        raise HTTPException(404, "Channel not found")
    with db() as conn:
        if before:
            cursor = conn.execute("SELECT created_at, id FROM messages WHERE source = 'synthetic' AND workspace_id = 'beacon' AND id = %s AND channel_id = %s", (before, channel)).fetchone()
            if cursor is None:
                raise HTTPException(400, "Invalid message cursor")
            rows = conn.execute(
                f"SELECT {MESSAGE_FIELDS} FROM messages WHERE source = 'synthetic' AND workspace_id = 'beacon' AND channel_id = %s AND (thread_root_id IS NULL OR id = thread_root_id) AND (created_at, id) < (%s, %s) ORDER BY created_at DESC, id DESC LIMIT %s",
                (channel, cursor["created_at"], cursor["id"], limit + 1),
            ).fetchall()
        else:
            rows = conn.execute(
                f"SELECT {MESSAGE_FIELDS} FROM messages WHERE source = 'synthetic' AND workspace_id = 'beacon' AND channel_id = %s AND (thread_root_id IS NULL OR id = thread_root_id) ORDER BY created_at DESC, id DESC LIMIT %s",
                (channel, limit + 1),
            ).fetchall()
        page = rows[:limit]
        roots = [row["id"] for row in page]
        if roots:
            counts = conn.execute("SELECT thread_root_id, count(*) AS replies, max(created_at) AS last_reply_at FROM messages WHERE source = 'synthetic' AND workspace_id = 'beacon' AND thread_root_id = ANY(%s) AND id <> thread_root_id GROUP BY thread_root_id", (roots,)).fetchall()
            by_root = {row["thread_root_id"]: row for row in counts}
            for row in page:
                detail = by_root.get(row["id"])
                row["reply_count"] = detail["replies"] if detail else 0
                row["last_reply_at"] = detail["last_reply_at"] if detail else None
    return {"items": page, "next_cursor": page[-1]["id"] if len(rows) > limit else None}


@app.get("/messages/{message_id:path}")
def message(message_id: str):
    with db() as conn:
        row = conn.execute(f"SELECT {MESSAGE_FIELDS} FROM messages WHERE source = 'synthetic' AND workspace_id = 'beacon' AND id = %s", (message_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "Message not found")
    return row


@app.get("/threads/{root_id:path}")
def thread(root_id: str):
    with db() as conn:
        rows = conn.execute(
            f"SELECT {MESSAGE_FIELDS} FROM messages WHERE source = 'synthetic' AND workspace_id = 'beacon' AND (id = %s OR (thread_root_id = %s AND id <> %s)) ORDER BY created_at, id",
            (root_id, root_id, root_id),
        ).fetchall()
    if not rows or rows[0]["id"] != root_id:
        raise HTTPException(404, "Thread not found")
    return rows


@app.post("/commands")
def command(payload: CommandInput, request: Request):
    raw = payload.input.strip()
    parts = raw.split(maxsplit=1)
    name = parts[0].lower()
    if name not in ("/ask", "/search", "/catchup") or len(parts) < 2:
        raise HTTPException(400, "Use /ask <question>, /search <terms>, or /catchup YYYY-MM-DD YYYY-MM-DD [#channel].")
    client_ip = request.headers.get("x-real-ip") or (request.client.host if request.client else "unknown")
    content = parts[1].strip()
    if name == "/catchup":
        match = re.fullmatch(r"(\d{4}-\d{2}-\d{2})\s+(\d{4}-\d{2}-\d{2})(?:\s+#([a-z-]+))?", content)
        if not match or (match[3] and match[3] not in CHANNELS):
            raise HTTPException(400, "Use /catchup YYYY-MM-DD YYYY-MM-DD [#channel].")
        try:
            start, end = date.fromisoformat(match[1]), date.fromisoformat(match[2])
        except ValueError:
            raise HTTPException(400, "Invalid date") from None
        if end < start or (end - start).days > 31:
            raise HTTPException(400, "Choose an inclusive range of up to 32 days.")
        corpus_zone = timezone(timedelta(hours=5, minutes=30))
        after = datetime.combine(start, day_time.min, corpus_zone)
        before = datetime.combine(end + timedelta(days=1), day_time.min, corpus_zone)
        check_quota(client_ip)
        evidence = retrieve("decisions updates changes blockers milestones next steps", after, before, match[3], 24)
        return {"kind": "answer", **answer(f"Catch me up from {start} through {end}" + (f" in #{match[3]}" if match[3] else ""), evidence)}
    if not content:
        raise HTTPException(400, "Enter a question or search terms.")
    check_quota(client_ip)
    evidence = rerank(content, retrieve(content, limit=12))
    if name == "/search":
        return {"kind": "search", "hits": evidence}
    return {"kind": "answer", **answer(content, evidence)}
