"""Verify planted and referenced corpus messages against each query part.

Uses gpt-5.4-mini once per small candidate batch. The append-only JSONL cache is
also the audit trail; reruns only call the API for missing claim/message pairs.
"""

import argparse
import asyncio
import hashlib
import json
from collections import Counter
from datetime import date, datetime
from pathlib import Path

import yaml
from openai import AsyncOpenAI

from recallhq.config import Settings


ROOT = Path(__file__).resolve().parents[1]
QUERIES = ROOT / "evals/queries.yaml"
AUDIT = ROOT / "evals/ref-verifications.jsonl"
CORPUS = ROOT / "data/synthetic/corpus.jsonl"
MODEL = "gpt-5.4-mini"
TOKEN_BUDGET = 300_000
BATCH_SIZE = 32
SHORT_REPLY_PARENTS = {
    "F20": "synthetic:product:20260917-01",
    "F36": "synthetic:eng:20260929-03",
}


def msg_id(row):
    return f"synthetic:{row['channel']}:{row['local_id']}"


def eligible(row, query):
    filters = query["filters"]
    day = date.fromisoformat(row["created_at"][:10])
    return (not filters["channel"] or row["channel"] == filters["channel"]) and \
        (not filters["author"] or row["author"] == filters["author"]) and \
        (not filters["after"] or day >= date.fromisoformat(filters["after"])) and \
        (not filters["before"] or day < date.fromisoformat(filters["before"])) and \
        datetime.fromisoformat(row["created_at"]) <= datetime.fromisoformat(query["request_time"])


def candidate_ids(query, part, rows):
    ids = {msg_id(row) for row in rows if eligible(row, query) and
           set(part["fact_ids"]) & set(row["plants"] + row["refs"])}
    if query["id"] == "Q11" and part["id"] == "p2":
        # F21 refs discuss retries broadly; only its plant states the exact SQL fix.
        by_id = {msg_id(row): row for row in rows}
        ids = {mid for mid in ids if "F37" in by_id[mid]["plants"] + by_id[mid]["refs"]
               or "F21" in by_id[mid]["plants"]}
    if "F20" in part["fact_ids"] and query["id"] in {"Q01", "Q41"}:
        parent = SHORT_REPLY_PARENTS["F20"]
        reply = "synthetic:product:20260917-02"
        if part["claim"].startswith(("Priya proposed", "Priya asked")):
            return [parent]
        if part["claim"].startswith("Meera approved"):
            return [reply]
    if "F36" in part["fact_ids"]:
        ids.add(SHORT_REPLY_PARENTS["F36"])
    return sorted(ids)


def content_tokens(text):
    import re
    stop = {"a", "an", "and", "are", "as", "at", "be", "by", "can", "did", "do", "does", "for",
            "from", "how", "in", "is", "it", "of", "on", "or", "our", "the", "their", "there",
            "to", "was", "were", "what", "when", "where", "which", "who", "why", "with", "we",
            "us", "anyone", "after", "before", "about", "s"}
    return {token for token in re.findall(r"[a-z0-9]+", text.lower()) if token not in stop}


def lexical_overlap(query_text, grade3_texts):
    query_tokens = content_tokens(query_text)
    evidence_tokens = content_tokens(" ".join(grade3_texts))
    return round(len(query_tokens & evidence_tokens) / len(query_tokens), 3) if query_tokens else 0.0


def cache_key(claim, mid, text):
    return hashlib.sha256(json.dumps([MODEL, claim, mid, text], ensure_ascii=False).encode()).hexdigest()


def payload(row, by_id):
    value = row["text"]
    if row["parent_id"]:
        parent = by_id.get(f"synthetic:{row['channel']}:{row['parent_id']}")
        if parent and (msg_id(row) in {"synthetic:product:20260917-02", "synthetic:eng:20260929-08"}):
            value = f"Parent: {parent['text']}\nReply: {value}"
    return value


async def check_batch(client, semaphore, part, batch, audit, counters):
    claims = [{"id": mid, "text": text} for mid, text, _ in batch]
    body = json.dumps({"claim": part["claim"], "messages": claims}, ensure_ascii=False)
    schema = {"type": "object", "properties": {"results": {"type": "array", "items": {
        "type": "object", "properties": {"id": {"type": "string"}, "yes": {"type": "boolean"}},
        "required": ["id", "yes"], "additionalProperties": False}}},
        "required": ["results"], "additionalProperties": False}
    async with semaphore:
        response = await client.responses.create(
            model=MODEL, reasoning={"effort": "none"},
            instructions="For each message, answer whether that message explicitly states the claim. Use its parent only to interpret a short reply. Related topic, speculation, a question, or missing detail is no. Return one yes/no for every id.",
            input=body,
            text={"format": {"type": "json_schema", "name": "ref_checks", "schema": schema, "strict": True}},
        )
    if response.status != "completed":
        raise RuntimeError(f"Verification response {response.status}")
    decisions = {item["id"]: item["yes"] for item in json.loads(response.output_text)["results"]}
    if set(decisions) != {mid for mid, _, _ in batch}:
        raise RuntimeError("Verifier returned incomplete or unexpected ids")
    counters["input"] += response.usage.input_tokens
    counters["output"] += response.usage.output_tokens
    for mid, text, key in batch:
        audit.append({"key": key, "model": MODEL, "claim": part["claim"], "message_id": mid,
                      "text_sha256": hashlib.sha256(text.encode()).hexdigest(), "yes": decisions[mid],
                      "response_id": response.id})


async def run(dry_run=False, only_messages=None):
    data = yaml.safe_load(QUERIES.read_text())
    rows = [json.loads(line) for line in CORPUS.read_text().splitlines()]
    by_id = {msg_id(row): row for row in rows}
    previous = [json.loads(line) for line in AUDIT.read_text().splitlines()] if AUDIT.exists() else []
    verdicts = {record["key"]: record["yes"] for record in previous}
    jobs = []
    candidates = {}
    for query in data["queries"]:
        for part in query["parts"]:
            mids = candidate_ids(query, part, rows)
            candidates[query["id"], part["id"]] = mids
            pending = []
            for mid in mids:
                text = payload(by_id[mid], by_id)
                key = cache_key(part["claim"], mid, text)
                if key not in verdicts and (only_messages is None or mid in only_messages):
                    pending.append((mid, text, key))
            jobs += [(part, pending[i:i+BATCH_SIZE]) for i in range(0, len(pending), BATCH_SIZE)]
    estimated = sum(sum(len(text) for _, text, _ in batch) // 3 + 500 + 20 * len(batch)
                    for _, batch in jobs)
    print(f"Candidate checks: {sum(map(len, candidates.values()))}; cached: {len(previous)}; "
          f"API batches: {len(jobs)}; estimated new tokens: {estimated}", flush=True)
    if dry_run:
        return
    if estimated > TOKEN_BUDGET:
        raise SystemExit(f"Estimated {estimated} tokens exceeds {TOKEN_BUDGET} budget")
    if jobs:
        settings = Settings()
        if not settings.openai_api_key:
            raise SystemExit("OPENAI_API_KEY missing")
        client = AsyncOpenAI(api_key=settings.openai_api_key)
        semaphore = asyncio.Semaphore(6)
        audit = []
        counters = Counter()
        tasks = [check_batch(client, semaphore, part, batch, audit, counters) for part, batch in jobs]
        try:
            for i, future in enumerate(asyncio.as_completed(tasks), 1):
                await future
                if i % 20 == 0:
                    print(f"Verified {i}/{len(jobs)} batches", flush=True)
        finally:
            await client.close()
            if audit:
                with AUDIT.open("a") as file:
                    for item in audit:
                        file.write(json.dumps(item, ensure_ascii=False) + "\n")
        print(f"API tokens: {counters['input']} input + {counters['output']} output = "
              f"{counters['input'] + counters['output']}", flush=True)
        if counters["input"] + counters["output"] > TOKEN_BUDGET:
            raise RuntimeError("Token budget exceeded")
        verdicts.update({item["key"]: item["yes"] for item in audit})
    if only_messages is not None:
        return
    ref_counts = Counter(fact for row in rows for fact in row["refs"])
    for query in data["queries"]:
        groups = []
        relevant = {}
        for part in query["parts"]:
            verified = []
            for mid in candidates[query["id"], part["id"]]:
                row = by_id[mid]
                key = cache_key(part["claim"], mid, payload(row, by_id))
                yes = verdicts[key]
                parent = mid in SHORT_REPLY_PARENTS.values() and not set(part["fact_ids"]) & set(row["plants"] + row["refs"])
                grade = 1 if parent else 3 if set(part["fact_ids"]) & set(row["plants"]) else 2 if yes else 1
                if yes:
                    verified.append(mid)
                if (yes or not parent) and (yes or not set(part["fact_ids"]) & set(row["plants"])):
                    relevant[mid] = max(grade, relevant.get(mid, 0))
            groups.append({"part": part["id"], "message_ids": verified})
        # The parent resolves a terse approval even when it does not assert approval itself.
        for fact, parent_mid in SHORT_REPLY_PARENTS.items():
            if fact in query["fact_ids"]:
                reply_mid = "synthetic:product:20260917-02" if fact == "F20" else "synthetic:eng:20260929-08"
                if relevant.get(reply_mid) == 3 and eligible(by_id[parent_mid], query):
                    relevant[parent_mid] = max(1, relevant.get(parent_mid, 0))
        query["evidence_groups"] = groups
        query["relevant"] = dict(sorted(relevant.items()))
        grade3_texts = [by_id[mid]["text"] for mid, grade in relevant.items() if grade == 3]
        query["lexical_overlap"] = lexical_overlap(query["query"], grade3_texts) if query["answerable"] else None
        facts = query["fact_ids"]
        query["tags"] = facts + (["easy"] if any(ref_counts[fact] > 15 for fact in facts) else [])
        if query["answerable"] and query["lexical_overlap"] < 0.3:
            query["tags"].append("paraphrase")
    QUERIES.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=110))
    print(f"Wrote {len(data['queries'])} queries; "
          f"{sum('paraphrase' in q['tags'] for q in data['queries'] if q['answerable'])} paraphrases", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--only-message", action="append", help="Verify changed message IDs without rewriting labels")
    args = parser.parse_args()
    asyncio.run(run(args.dry_run, set(args.only_message) if args.only_message else None))
