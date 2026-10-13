"""Incremental Slack message updates and resumable history import."""

import hashlib
import json
import secrets
import time
from datetime import UTC, datetime
from decimal import Decimal

from openai import OpenAI
from psycopg.types.json import Jsonb
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from recallhq.ingestion.pipeline import ENCODER, THREAD_TOKEN_LIMIT, chunk, split_thread
from recallhq.slack.store import (
    PostgresInstallationStore,
    RetryLater,
    database,
    disable,
    enqueue,
    postpone_api,
    reserve_api,
)

TEXT_SUBTYPES = {None, "bot_message", "file_share", "thread_broadcast", "me_message"}


def source_id(team: str, channel: str, ts: str):
    if not ts or not isinstance(ts, str) or not ts.replace(".", "", 1).isdigit():
        raise ValueError("Invalid Slack message timestamp")
    return f"slack:{team}:{channel}:{ts}"


def client_for(settings, team):
    installation = PostgresInstallationStore(settings).find_installation(team_id=team)
    if not installation:
        raise ValueError("Workspace installation is no longer active.")
    return WebClient(token=installation.bot_token, timeout=20, retry_handlers=[]), installation


def slack_call(settings, team, client, method: str, **params):
    interval = settings.slack_history_interval_seconds if method in ("conversations.history", "conversations.replies") else 0
    reserve_api(settings, team, method, interval)
    try:
        return client.api_call(method, params=params)
    except SlackApiError as exc:
        if exc.response.status_code == 429:
            delay = float(exc.response.headers.get("retry-after", "60"))
            postpone_api(settings, team, method, delay)
            raise RetryLater(delay) from None
        # Never persist Slack SDK exceptions: their representations may contain payloads.
        error = exc.response.get("error", "slack_api_error")
        if error in ("invalid_auth", "token_revoked", "account_inactive"):
            with database(settings, team) as conn:
                disable(conn, team)
        raise ValueError(f"Slack API: {error}") from None


def activate_channel(settings, team, channel, *, explicit=False):
    client, _ = client_for(settings, team)
    info = slack_call(settings, team, client, "conversations.info", channel=channel)["channel"]
    if info.get("is_im") or info.get("is_mpim") or info.get("is_ext_shared") or info.get("is_archived") or not info.get("is_member"):
        return False
    boundary = f"{time.time():.6f}"
    with database(settings, team) as conn:
        active = conn.execute("SELECT active FROM slack_installations WHERE team_id = %s FOR SHARE", (team,)).fetchone()
        if not active or not active["active"]:
            return False
        existing = conn.execute("SELECT active FROM slack_channels WHERE team_id = %s AND channel_id = %s FOR UPDATE", (team, channel)).fetchone()
        if existing and (existing["active"] or not explicit):
            return existing["active"]
        conn.execute("""INSERT INTO slack_channels (team_id, channel_id, name, import_boundary)
                        VALUES (%s, %s, %s, %s) ON CONFLICT (team_id, channel_id) DO UPDATE SET
                        name = EXCLUDED.name, active = true, import_status = 'pending', history_cursor = '',
                        import_boundary = EXCLUDED.import_boundary, last_error = NULL""", (team, channel, info["name"], boundary))
        enqueue(conn, team, "history", {"boundary": boundary}, f"history:{team}:{channel}:{boundary}", channel)
    return True


def normalize(team: str, channel: str, message: dict, revision: str | None = None, *, allow_empty=False):
    if message.get("subtype") not in TEXT_SUBTYPES:
        return None
    text = message.get("text", "")
    if not text.strip():
        text = "\n".join(a.get("text") or a.get("fallback") or "" for a in message.get("attachments", []))
    if not text.strip() and not allow_empty:
        return None
    ts = message["ts"]
    mid = source_id(team, channel, ts)
    root_ts = message.get("thread_ts") or (ts if message.get("reply_count") else None)
    author = message.get("user") or message.get("bot_id") or "unknown"
    return {"id": mid, "source": "slack", "workspace_id": team, "channel": channel,
            "local_id": ts, "parent_id": root_ts if root_ts and root_ts != ts else None,
            "thread_root_id": source_id(team, channel, root_ts) if root_ts else None,
            "author": author, "text": text, "created_at": datetime.fromtimestamp(float(Decimal(ts)), UTC),
            "revision": Decimal(revision or message.get("edited", {}).get("ts") or ts)}


def row_for_chunk(row: dict):
    return {**row, "channel": row["channel_id"], "local_id": row["source_message_id"], "author": row["author_name"],
            "parent_id": row["thread_root_id"].rsplit(":", 1)[-1] if row["thread_root_id"] and row["thread_root_id"] != row["id"] else None}


def bounded_chunks(kind: str, rows: list[dict]):
    """Split oversized rendered chunks without truncating stored source messages."""
    item = chunk(kind, rows)
    encoded = ENCODER.encode(item["text"])
    if len(encoded) <= THREAD_TOKEN_LIMIT:
        return [item]
    result = []
    for offset in range(0, len(encoded), THREAD_TOKEN_LIMIT):
        part = {**item, "id": item["id"] + f":{offset // THREAD_TOKEN_LIMIT}",
                "text": ENCODER.decode(encoded[offset:offset + THREAD_TOKEN_LIMIT])}
        result.append(part)
    return result


def rebuild(conn, team: str, channel: str, mid: str, root_id: str | None):
    # Remove every old chunk containing the changed message, then reconstruct its thread.
    conn.execute("DELETE FROM chunks WHERE source = 'slack' AND workspace_id = %s AND channel_id = %s AND %s = ANY(message_ids)", (team, channel, mid))
    root_id = root_id or mid
    rows = conn.execute("""SELECT * FROM messages WHERE source = 'slack' AND workspace_id = %s AND channel_id = %s
                           AND (id = %s OR thread_root_id = %s) ORDER BY created_at, id""", (team, channel, root_id, root_id)).fetchall()
    if not rows:
        return
    normalized = [row_for_chunk(r) for r in rows if r["text"].strip()]
    ids = [r["id"] for r in rows]
    conn.execute("DELETE FROM chunks WHERE source = 'slack' AND workspace_id = %s AND channel_id = %s AND kind = 'thread' AND message_ids && %s::text[]", (team, channel, ids))
    items = [item for row in normalized for item in bounded_chunks("message", [row])]
    root = next((row for row in normalized if row["id"] == root_id), None)
    if root and len(normalized) > 1:
        for part in split_thread(root, [r for r in normalized if r["id"] != root_id]):
            items.extend(bounded_chunks("thread", part))
    for item in items:
        conn.execute("""INSERT INTO chunks (id, source, workspace_id, kind, chunker_version, channel_id, message_ids, start_at, end_at, text)
                        VALUES (%s, 'slack', %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (id) DO UPDATE SET text = EXCLUDED.text, start_at = EXCLUDED.start_at, end_at = EXCLUDED.end_at,
                        embedding = CASE WHEN chunks.text IS DISTINCT FROM EXCLUDED.text THEN NULL ELSE chunks.embedding END,
                        embedding_model = CASE WHEN chunks.text IS DISTINCT FROM EXCLUDED.text THEN NULL ELSE chunks.embedding_model END""",
                     (item["id"], team, item["kind"], item["chunker_version"], channel, item["message_ids"], item["start_at"], item["end_at"], item["text"]))


def upsert_message(conn, team: str, channel: str, message: dict, *, revision: str | None = None, bot_user: str = "", bot_id: str = "", allow_empty=False):
    if (bot_user and message.get("user") == bot_user) or (bot_id and message.get("bot_id") == bot_id):
        return False
    row = normalize(team, channel, message, revision, allow_empty=allow_empty)
    if row is None:
        return False
    info = conn.execute("""SELECT c.name FROM slack_channels c JOIN slack_installations i USING (team_id)
                           WHERE c.team_id = %s AND c.channel_id = %s AND c.active AND i.active FOR UPDATE OF c""", (team, channel)).fetchone()
    if not info:
        return False
    deleted = conn.execute("SELECT 1 FROM slack_tombstones WHERE team_id = %s AND channel_id = %s AND message_ts = %s", (team, channel, row["local_id"])).fetchone()
    if deleted:
        return False
    previous = conn.execute("SELECT thread_root_id FROM messages WHERE id = %s", (row["id"],)).fetchone()
    updated = conn.execute("""INSERT INTO messages (id, source, platform_style, workspace_id, channel_id, channel_name,
                             source_message_id, thread_root_id, author_id, author_name, text, created_at, source_revision)
                           VALUES (%s, 'slack', 'slack', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                           ON CONFLICT (id) DO UPDATE SET text = EXCLUDED.text,
                             thread_root_id = COALESCE(EXCLUDED.thread_root_id, messages.thread_root_id),
                             source_revision = EXCLUDED.source_revision
                           WHERE messages.source_revision <= EXCLUDED.source_revision
                             AND (messages.text IS DISTINCT FROM EXCLUDED.text OR messages.thread_root_id IS DISTINCT FROM COALESCE(EXCLUDED.thread_root_id, messages.thread_root_id)
                                  OR messages.source_revision < EXCLUDED.source_revision)
                           RETURNING id, thread_root_id""",
                          (row["id"], team, channel, info["name"], row["local_id"], row["thread_root_id"], row["author"],
                           message.get("username") or row["author"], row["text"], row["created_at"], row["revision"])).fetchone()
    if updated:
        if updated["thread_root_id"] and updated["thread_root_id"] != row["id"]:
            conn.execute("UPDATE messages SET thread_root_id = id WHERE id = %s AND thread_root_id IS NULL", (updated["thread_root_id"],))
        rebuild(conn, team, channel, row["id"], updated["thread_root_id"] or (previous or {}).get("thread_root_id"))
        conn.execute("UPDATE slack_channels SET last_ingested_at = now() WHERE team_id = %s AND channel_id = %s", (team, channel))
    return bool(updated)


def delete_message(conn, team: str, channel: str, ts: str, revision: str):
    info = conn.execute("SELECT channel_id FROM slack_channels WHERE team_id = %s AND channel_id = %s FOR UPDATE", (team, channel)).fetchone()
    if not info:
        return
    mid = source_id(team, channel, ts)
    conn.execute("""INSERT INTO slack_tombstones VALUES (%s, %s, %s, %s) ON CONFLICT (team_id, channel_id, message_ts)
                    DO UPDATE SET revision = GREATEST(slack_tombstones.revision, EXCLUDED.revision)""", (team, channel, ts, Decimal(revision)))
    conn.execute("""UPDATE slack_jobs SET status = 'cancelled', payload = '{}'::jsonb
                    WHERE team_id = %s AND channel_id = %s AND kind = 'event'
                    AND status IN ('pending','processing','failed')
                    AND (payload #>> '{event,ts}' = %s OR payload #>> '{event,message,ts}' = %s
                         OR payload #>> '{event,previous_message,ts}' = %s)""", (team, channel, ts, ts, ts))
    row = conn.execute("DELETE FROM messages WHERE id = %s RETURNING thread_root_id", (mid,)).fetchone()
    rebuild(conn, team, channel, mid, row["thread_root_id"] if row else None)


def process_event(settings, job):
    event = job["payload"]["event"]
    team, channel = job["team_id"], event.get("channel")
    _, installation = client_for(settings, team)
    kind = event["type"]
    if kind == "member_joined_channel" and event["user"] == installation.bot_user_id:
        activate_channel(settings, team, channel, explicit=True)
    elif kind == "message":
        subtype = event.get("subtype")
        with database(settings, team) as conn:
            if subtype == "message_deleted":
                delete_message(conn, team, channel, event["deleted_ts"], event.get("event_ts") or event["ts"])
            elif subtype == "message_changed":
                upsert_message(conn, team, channel, event["message"], revision=event.get("event_ts") or event["ts"], bot_user=installation.bot_user_id, bot_id=installation.bot_id, allow_empty=True)
            else:
                upsert_message(conn, team, channel, event, bot_user=installation.bot_user_id, bot_id=installation.bot_id)


def discover(settings, job):
    client, _ = client_for(settings, job["team_id"])
    cursor = job["payload"].get("cursor", "")
    response = slack_call(settings, job["team_id"], client, "conversations.list", types="public_channel,private_channel", exclude_archived=True, limit=200, cursor=cursor)
    for channel in response["channels"]:
        if channel.get("is_member"):
            activate_channel(settings, job["team_id"], channel["id"])
    cursor = response.get("response_metadata", {}).get("next_cursor", "")
    if cursor:
        with database(settings) as conn:
            enqueue(conn, job["team_id"], "discover", {"cursor": cursor}, f"discover:{job['team_id']}:{hashlib.sha256(cursor.encode()).hexdigest()}:{secrets.token_hex(6)}")


def history_page(settings, job):
    team, channel = job["team_id"], job["channel_id"]
    client, installation = client_for(settings, team)
    with database(settings, team) as conn:
        state = conn.execute("SELECT * FROM slack_channels WHERE team_id = %s AND channel_id = %s AND active", (team, channel)).fetchone()
    if not state or state["import_boundary"] != job["payload"]["boundary"]:
        return False
    response = slack_call(settings, team, client, "conversations.history", channel=channel, cursor=state["history_cursor"],
                          latest=state["import_boundary"], inclusive=True, limit=settings.slack_history_page_size)
    cursor = response.get("response_metadata", {}).get("next_cursor", "")
    with database(settings, team) as conn:
        current = conn.execute("SELECT import_boundary FROM slack_channels WHERE team_id = %s AND channel_id = %s AND active FOR UPDATE", (team, channel)).fetchone()
        if not current or current["import_boundary"] != state["import_boundary"]:
            return False
        for message in response["messages"]:
            conn.execute("INSERT INTO slack_seen_messages VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING", (team, channel, state["import_boundary"], message["ts"]))
            upsert_message(conn, team, channel, message, bot_user=installation.bot_user_id, bot_id=installation.bot_id)
            if message.get("reply_count"):
                enqueue(conn, team, "replies", {"ts": message["ts"], "cursor": "", "boundary": state["import_boundary"]},
                        f"replies:{team}:{channel}:{message['ts']}:{state['import_boundary']}", channel)
        conn.execute("UPDATE slack_channels SET history_cursor = %s, import_status = %s, last_error = NULL, last_reconciled_at = now() WHERE team_id = %s AND channel_id = %s",
                     (cursor, "importing" if cursor else "threads", team, channel))
    return bool(cursor)


def replies_page(settings, job):
    team, channel, payload = job["team_id"], job["channel_id"], job["payload"]
    client, installation = client_for(settings, team)
    with database(settings, team) as conn:
        state = conn.execute("SELECT active, import_boundary FROM slack_channels WHERE team_id = %s AND channel_id = %s", (team, channel)).fetchone()
    if not state or not state["active"] or state["import_boundary"] != payload["boundary"]:
        return False
    try:
        response = slack_call(settings, team, client, "conversations.replies", channel=channel, ts=payload["ts"], cursor=payload.get("cursor", ""),
                              latest=payload["boundary"], inclusive=True, limit=settings.slack_history_page_size)
    except ValueError as exc:
        if str(exc) == "Slack API: thread_not_found":
            return False
        raise
    cursor = response.get("response_metadata", {}).get("next_cursor", "")
    with database(settings, team) as conn:
        current = conn.execute("SELECT import_boundary FROM slack_channels WHERE team_id = %s AND channel_id = %s AND active FOR UPDATE", (team, channel)).fetchone()
        if not current or current["import_boundary"] != payload["boundary"]:
            return False
        for message in response["messages"]:
            conn.execute("INSERT INTO slack_seen_messages VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING", (team, channel, payload["boundary"], message["ts"]))
            upsert_message(conn, team, channel, message, bot_user=installation.bot_user_id, bot_id=installation.bot_id)
        conn.execute("UPDATE slack_jobs SET payload = %s WHERE id = %s AND lease_token = %s AND status = 'processing'",
                     (Jsonb({**payload, "cursor": cursor}), job["id"], job["lease_token"]))
    return bool(cursor)


def complete_import(settings, team, channel):
    """Reconcile removed/inaccessible sources only after every history/thread page succeeds."""
    with database(settings, team) as conn:
        state = conn.execute("SELECT * FROM slack_channels WHERE team_id = %s AND channel_id = %s AND active AND import_status = 'threads' FOR UPDATE", (team, channel)).fetchone()
        if not state:
            return
        if conn.execute("SELECT 1 FROM slack_jobs WHERE team_id = %s AND channel_id = %s AND kind IN ('history','replies') AND status IN ('pending','processing','failed') LIMIT 1", (team, channel)).fetchone():
            return
        missing = conn.execute("""SELECT m.id, m.thread_root_id FROM messages m WHERE m.source = 'slack' AND m.workspace_id = %s
                                  AND m.channel_id = %s AND m.source_revision <= %s::numeric
                                  AND NOT EXISTS (SELECT 1 FROM slack_seen_messages s WHERE s.team_id = m.workspace_id
                                    AND s.channel_id = m.channel_id AND s.boundary = %s AND s.message_ts = m.source_message_id)""", (team, channel, state["import_boundary"], state["import_boundary"])).fetchall()
        for row in missing:
            conn.execute("DELETE FROM messages WHERE id = %s", (row["id"],))
            rebuild(conn, team, channel, row["id"], row["thread_root_id"])
        conn.execute("DELETE FROM slack_seen_messages WHERE team_id = %s AND channel_id = %s", (team, channel))
        conn.execute("UPDATE slack_channels SET import_status = 'complete', last_reconciled_at = now(), last_error = NULL WHERE team_id = %s AND channel_id = %s", (team, channel))


def embed_channel(settings, team: str, channel: str):
    if not settings.openai_api_key:
        return 0
    with database(settings, team) as conn:
        active = conn.execute("SELECT 1 FROM slack_channels c JOIN slack_installations i USING(team_id) WHERE c.team_id = %s AND channel_id = %s AND c.active AND i.active", (team, channel)).fetchone()
        if not active:
            return 0
        rows = conn.execute("""SELECT id, text FROM chunks WHERE source = 'slack' AND workspace_id = %s AND channel_id = %s
                               AND (embedding IS NULL OR embedding_model IS DISTINCT FROM %s) ORDER BY id LIMIT 100""", (team, channel, settings.embedding_model)).fetchall()
    if not rows:
        return 0
    response = OpenAI(api_key=settings.openai_api_key, timeout=45, max_retries=0).embeddings.create(
        model=settings.embedding_model, dimensions=settings.embedding_dimension, input=[r["text"] for r in rows])
    vectors = sorted(response.data, key=lambda item: item.index)
    if len(vectors) != len(rows):
        raise ValueError("Embedding response length mismatch")
    with database(settings, team) as conn:
        active = conn.execute("SELECT active FROM slack_channels WHERE team_id = %s AND channel_id = %s FOR UPDATE", (team, channel)).fetchone()
        if not active or not active["active"]:
            return 0
        for row, vector in zip(rows, vectors):
            conn.execute("UPDATE chunks SET embedding = %s::vector, embedding_model = %s WHERE id = %s AND text = %s",
                         (json.dumps(vector.embedding), settings.embedding_model, row["id"], row["text"]))
    return len(rows)
