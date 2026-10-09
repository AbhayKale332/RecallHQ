"""Import the frozen synthetic corpus and embed deterministic message/thread chunks."""

import hashlib
import json
import time
from collections import defaultdict
from pathlib import Path

import psycopg
import tiktoken
import yaml
from openai import OpenAI
from psycopg.types.json import Jsonb

from recallhq.config import Settings
from recallhq.ingestion.validate import validate_corpus


ROOT = Path(__file__).resolve().parents[3]
STORY = ROOT / "data/synthetic/story.yaml"
REPORT = ROOT / "data/synthetic/ingest-report.json"
EMBED_USAGE = ROOT / "data/synthetic/embedding-usage.jsonl"
CHUNKER_VERSION = "v1"
THREAD_TOKEN_LIMIT = 600
EMBED_BATCH_SIZE = 100
ENCODER = tiktoken.get_encoding("o200k_base")


def message_id(row: dict) -> str:
    return f"synthetic:{row['channel']}:{row['local_id']}"


def render(row: dict) -> str:
    return f"[#{row['channel']} · {row['created_at']} · {row['author']}]\n{row['text']}"


def tokens(rows: list[dict]) -> int:
    return len(ENCODER.encode("\n\n".join(render(row) for row in rows)))


def split_thread(root: dict, replies: list[dict], limit: int = THREAD_TOKEN_LIMIT) -> list[list[dict]]:
    """Keep the root and one previous reply when a thread crosses the token limit."""
    parts = []
    current = [root]
    for reply in replies:
        if len(current) > 1 and tokens(current + [reply]) > limit:
            parts.append(current)
            current = [root, current[-1]]
            if tokens(current + [reply]) > limit:
                current = [root]  # one-message overlap cannot fit this unusually long reply
        current.append(reply)
    parts.append(current)
    return parts


def chunk(kind: str, rows: list[dict]) -> dict:
    ids = [message_id(row) for row in rows]
    digest = hashlib.sha256(json.dumps([CHUNKER_VERSION, kind, ids]).encode()).hexdigest()[:24]
    return {
        "id": f"synthetic:{kind}:{digest}", "kind": kind, "chunker_version": CHUNKER_VERSION,
        "channel_id": rows[0]["channel"], "message_ids": ids,
        "start_at": rows[0]["created_at"], "end_at": rows[-1]["created_at"],
        "text": "\n\n".join(render(row) for row in rows),
    }


def build_chunks(rows: list[dict]) -> tuple[list[dict], int]:
    by_key = {(row["channel"], row["local_id"]): row for row in rows}
    replies = defaultdict(list)
    for row in rows:
        if row["parent_id"]:
            replies[(row["channel"], row["parent_id"])].append(row)
    chunks = [chunk("message", [row]) for row in rows]
    splits = 0
    for key in sorted(replies):
        ordered = sorted(replies[key], key=lambda row: (row["created_at"], row["local_id"]))
        parts = split_thread(by_key[key], ordered)
        splits += len(parts) - 1
        chunks.extend(chunk("thread", part) for part in parts)
    return chunks, splits


def import_rows(conn: psycopg.Connection, rows: list[dict], chunks: list[dict], story: dict) -> None:
    channels = {item["id"]: item for item in story["channels"]}
    authors = {item["id"]: item for item in story["personas"]}
    thread_roots = {(row["channel"], row["parent_id"]) for row in rows if row["parent_id"]}
    message_values = []
    for row in rows:
        key = (row["channel"], row["local_id"])
        root_id = row["parent_id"] or (row["local_id"] if key in thread_roots else None)
        message_values.append((
            message_id(row), "synthetic", channels[row["channel"]]["platform_style"], "beacon",
            row["channel"], channels[row["channel"]]["name"], row["local_id"],
            f"synthetic:{row['channel']}:{root_id}" if root_id else None,
            row["author"], authors[row["author"]]["name"], row["text"], row["created_at"],
            Jsonb({"plants": row["plants"], "refs": row["refs"]}),
        ))
    chunk_values = [(item["id"], item["kind"], item["chunker_version"], item["channel_id"],
                     item["message_ids"], item["start_at"], item["end_at"], item["text"])
                    for item in chunks]
    with conn.cursor() as cur:
        cur.executemany("""
            INSERT INTO messages (id, source, platform_style, workspace_id, channel_id,
                channel_name, source_message_id, thread_root_id, author_id, author_name,
                text, created_at, metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                thread_root_id = EXCLUDED.thread_root_id, text = EXCLUDED.text,
                metadata = EXCLUDED.metadata
        """, message_values)
        cur.executemany("""
            INSERT INTO chunks (id, kind, chunker_version, channel_id, message_ids,
                start_at, end_at, text)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                text = EXCLUDED.text, start_at = EXCLUDED.start_at, end_at = EXCLUDED.end_at,
                embedding = CASE WHEN chunks.text IS DISTINCT FROM EXCLUDED.text
                                 THEN NULL ELSE chunks.embedding END,
                embedding_model = CASE WHEN chunks.text IS DISTINCT FROM EXCLUDED.text
                                       THEN NULL ELSE chunks.embedding_model END
        """, chunk_values)
        cur.execute("DELETE FROM chunks WHERE id LIKE 'synthetic:%%' AND id <> ALL(%s)",
                    ([item["id"] for item in chunks],))
        cur.execute("DELETE FROM messages WHERE source = 'synthetic' AND id <> ALL(%s)",
                    ([message_id(row) for row in rows],))
    conn.commit()


def embed_missing(conn: psycopg.Connection, settings: Settings, corpus_hash: str) -> tuple[int, int]:
    missing = conn.execute("""
        SELECT id, text FROM chunks
        WHERE id LIKE 'synthetic:%%' AND (embedding IS NULL OR embedding_model IS DISTINCT FROM %s)
        ORDER BY id
    """, (settings.embedding_model,)).fetchall()
    if not missing:
        return 0, 0
    client = OpenAI(api_key=settings.openai_api_key, max_retries=0)
    used_tokens = 0
    for offset in range(0, len(missing), EMBED_BATCH_SIZE):
        batch = missing[offset:offset + EMBED_BATCH_SIZE]
        for attempt in range(4):
            try:
                response = client.embeddings.create(
                    model=settings.embedding_model,
                    dimensions=settings.embedding_dimension,
                    encoding_format="float",
                    input=[text for _, text in batch],
                )
                break
            except Exception:
                if attempt == 3:
                    raise
                time.sleep(2 ** attempt)
        count = response.usage.total_tokens
        used_tokens += count
        with EMBED_USAGE.open("a") as file:
            file.write(json.dumps({"corpus_sha256": corpus_hash, "model": settings.embedding_model,
                                   "chunks": len(batch), "tokens": count,
                                   "response_id": getattr(response, "id", None)}) + "\n")
        vectors = sorted(response.data, key=lambda item: item.index)
        if len(vectors) != len(batch):
            raise RuntimeError("Embedding response length does not match request")
        with conn.cursor() as cur:
            cur.executemany("UPDATE chunks SET embedding = %s::vector, embedding_model = %s WHERE id = %s",
                            [(json.dumps(item.embedding), settings.embedding_model, mid)
                             for (mid, _), item in zip(batch, vectors)])
        conn.commit()
        print(f"Embedded {min(offset + len(batch), len(missing))}/{len(missing)} chunks", flush=True)
    return len(missing), used_tokens


def ingest(path: Path, settings: Settings | None = None) -> dict:
    settings = settings or Settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required to embed chunks")
    story = yaml.safe_load(STORY.read_text())
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    errors = validate_corpus(rows, {fact["id"] for fact in story["facts"]},
                             {author["id"] for author in story["personas"]},
                             key_tokens={fact["id"]: fact["key_tokens"] for fact in story["facts"]})
    if errors:
        raise ValueError("Invalid corpus:\n" + "\n".join(errors[:20]))
    chunks, splits = build_chunks(rows)
    corpus_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    with psycopg.connect(settings.database_url) as conn:
        import_rows(conn, rows, chunks, story)
        embedded_new, tokens_new = embed_missing(conn, settings, corpus_hash)
        counts = conn.execute("""
            SELECT (SELECT count(*) FROM messages WHERE source = 'synthetic'),
                   (SELECT count(*) FROM chunks WHERE id LIKE 'synthetic:%%' AND kind = 'message'),
                   (SELECT count(*) FROM chunks WHERE id LIKE 'synthetic:%%' AND kind = 'thread'),
                   (SELECT count(*) FROM chunks WHERE id LIKE 'synthetic:%%' AND embedding IS NOT NULL
                       AND embedding_model = %s)
        """, (settings.embedding_model,)).fetchone()
    usage = [json.loads(line) for line in EMBED_USAGE.read_text().splitlines()] if EMBED_USAGE.exists() else []
    report = {"corpus_sha256": corpus_hash, "chunker_version": CHUNKER_VERSION,
              "thread_token_limit": THREAD_TOKEN_LIMIT, "thread_splits": splits,
              "messages": counts[0], "message_chunks": counts[1], "thread_chunks": counts[2],
              "embedded_chunks": counts[3], "embedding_model": settings.embedding_model,
              "embedding_dimensions": settings.embedding_dimension,
              "new_embeddings": embedded_new, "new_embedding_tokens": tokens_new,
              "embedding_tokens_total": sum(item["tokens"] for item in usage
                                            if item["corpus_sha256"] == corpus_hash
                                            and item["model"] == settings.embedding_model)}
    REPORT.write_text(json.dumps(report, indent=2) + "\n")
    return report
