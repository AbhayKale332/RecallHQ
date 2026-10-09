from recallhq.ingestion.pipeline import build_chunks, chunk, split_thread, tokens
from recallhq.ingestion.validate import validate_corpus


def row(local_id: str, text: str) -> dict:
    return {"channel": "eng", "local_id": local_id, "created_at": "2026-09-01T09:00:00+05:30",
            "author": "priya", "text": text, "parent_id": None, "plants": [], "refs": []}


def test_thread_split_keeps_root_and_one_reply_overlap():
    root = row("root", "Decision context")
    replies = [row(str(i), f"Reply {i} with enough detail to matter. " * 9) for i in range(3)]
    limit = tokens([root, *replies[:2]]) + 1
    parts = split_thread(root, replies, limit=limit)
    assert len(parts) == 2
    assert [item["local_id"] for item in parts[0]] == ["root", "0", "1"]
    assert [item["local_id"] for item in parts[1]] == ["root", "1", "2"]
    assert chunk("thread", parts[0])["id"] == chunk("thread", parts[0])["id"]
    assert chunk("thread", parts[0])["id"] != chunk("thread", parts[1])["id"]


def test_thread_split_at_exact_boundary():
    root, first, second = row("root", "Context"), row("1", "first"), row("2", "second")
    limit = tokens([root, first, second])
    assert split_thread(root, [first, second], limit) == [[root, first, second]]
    assert split_thread(root, [first, second], limit - 1) == [[root, first], [root, second]]


def test_id_and_timestamp_strings_survive_json_and_chunking():
    import json
    original = row("0007", "hello")
    restored = json.loads(json.dumps(original))
    assert restored["local_id"] == "0007"
    assert restored["created_at"] == "2026-09-01T09:00:00+05:30"
    item = chunk("message", [restored])
    assert item["message_ids"] == ["synthetic:eng:0007"]
    assert item["start_at"] == item["end_at"] == original["created_at"]


def test_chunk_ids_deterministic_across_runs():
    root, reply = row("root", "context"), row("reply", "answer")
    reply["parent_id"] = "root"
    reply["created_at"] = "2026-09-01T09:01:00+05:30"
    first, _ = build_chunks([root, reply])
    second, _ = build_chunks([root, reply])
    assert [item["id"] for item in first] == [item["id"] for item in second]
    assert len({item["id"] for item in first}) == 3


def test_corpus_validator_rejects_broken_parent_and_missing_key_token():
    root = row("root", "context")
    reply = row("reply", "fix later")
    reply["parent_id"] = "missing"
    reply["created_at"] = "2026-09-01T09:01:00+05:30"
    reply["plants"] = ["F21"]
    errors = validate_corpus([root, reply], {"F21"}, key_tokens={"F21": ["23505"]})
    assert any("missing or late parent" in error for error in errors)
    assert any("lacks key token" in error for error in errors)


def test_corpus_chunk_counts():
    import json
    from pathlib import Path
    path = Path(__file__).resolve().parents[1] / "data/synthetic/corpus.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    chunks, splits = build_chunks(rows)
    assert len(rows) == 2233
    assert sum(item["kind"] == "message" for item in chunks) == 2233
    assert sum(item["kind"] == "thread" for item in chunks) == 158
    assert splits == 0
