"""Validate graded query labels, evidence, corpus-search records, and split hygiene."""

import json
import re
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

import yaml

from verify_query_refs import cache_key, eligible, lexical_overlap, msg_id, payload

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "data/synthetic/corpus.jsonl"
QUERIES = ROOT / "evals/queries.yaml"
AUDIT = ROOT / "evals/ref-verifications.jsonl"
STORY = ROOT / "data/synthetic/story.yaml"
DEFAULT_TIME = "2026-10-05T10:00:00+05:30"


def main():
    rows = [json.loads(line) for line in CORPUS.read_text().splitlines()]
    by_id = {msg_id(row): row for row in rows}
    facts = {fact["id"] for fact in yaml.safe_load(STORY.read_text())["facts"]}
    ref_counts = Counter(fact for row in rows for fact in row["refs"])
    queries = yaml.safe_load(QUERIES.read_text())["queries"]
    audit = [json.loads(line) for line in AUDIT.read_text().splitlines()]
    yes = {record["key"] for record in audit if record["yes"]}
    errors = []
    ids = Counter(query.get("id") for query in queries)
    splits = defaultdict(set)
    kinds = Counter()
    for query in queries:
        qid = query["id"]
        if ids[qid] != 1:
            errors.append(f"{qid}: duplicate id")
        if query["split"] not in {"dev", "test"}:
            errors.append(f"{qid}: invalid split")
        if not query["query"].strip():
            errors.append(f"{qid}: empty query")
        if query["answer_type"] not in {"fact", "no_decision", "unanswerable"}:
            errors.append(f"{qid}: invalid answer_type")
        if query["answerable"] != (query["answer_type"] != "unanswerable"):
            errors.append(f"{qid}: answerable/answer_type mismatch")
        if query["request_time"] != DEFAULT_TIME and query["type"] != "as_of":
            errors.append(f"{qid}: nondefault request_time without as_of type")
        try:
            timestamp = datetime.fromisoformat(query["request_time"])
            if timestamp.utcoffset() != timedelta(hours=5, minutes=30):
                errors.append(f"{qid}: request_time must be +05:30")
        except ValueError:
            errors.append(f"{qid}: invalid request_time")
        filters = query["filters"]
        if set(filters) != {"channel", "author", "after", "before"}:
            errors.append(f"{qid}: filters must have channel, author, after, before")
        if filters["after"] and filters["before"] and date.fromisoformat(filters["after"]) >= date.fromisoformat(filters["before"]):
            errors.append(f"{qid}: invalid date filter window")
        fact_ids = query["fact_ids"]
        if any(fact not in facts for fact in fact_ids):
            errors.append(f"{qid}: unknown fact")
        for fact in fact_ids:
            splits[fact].add(query["split"])
        expected_easy = any(ref_counts[fact] > 15 for fact in fact_ids)
        if ("easy" in query["tags"]) != expected_easy:
            errors.append(f"{qid}: incorrect easy tag")
        if not set(fact_ids) <= set(query["tags"]):
            errors.append(f"{qid}: missing fact tag")
        relevant = query["relevant"]
        groups = query["evidence_groups"]
        parts = query["parts"]
        if query["type"] == "as_of":
            if not filters["before"]:
                errors.append(f"{qid}: as_of query requires filters.before")
            else:
                cutoff = date.fromisoformat(filters["before"])
                labeled = set(relevant) | {mid for group in groups for mid in group["message_ids"]}
                for mid in labeled:
                    if mid in by_id and date.fromisoformat(by_id[mid]["created_at"][:10]) >= cutoff:
                        errors.append(f"{qid}: labeled message is not before {filters['before']}: {mid}")
        if query["answerable"]:
            kinds[query["answer_type"]] += 1
            if not query["answer"] or not parts:
                errors.append(f"{qid}: missing answer or parts")
            if len(parts) != len(groups) or [p["id"] for p in parts] != [g["part"] for g in groups]:
                errors.append(f"{qid}: one evidence group per part required")
            if any(not group["message_ids"] for group in groups):
                errors.append(f"{qid}: empty verified evidence group")
            if any(grade not in {1, 2, 3} for grade in relevant.values()):
                errors.append(f"{qid}: invalid relevance grade")
            for part, group in zip(parts, groups):
                if not set(part["fact_ids"]) <= set(fact_ids):
                    errors.append(f"{qid}: part uses unlisted fact")
                if len(group["message_ids"]) != len(set(group["message_ids"])):
                    errors.append(f"{qid}: duplicate group evidence")
                for mid in group["message_ids"]:
                    if mid not in relevant or mid not in by_id:
                        errors.append(f"{qid}: group message missing from relevant or corpus: {mid}")
                        continue
                    if cache_key(part["claim"], mid, payload(by_id[mid], by_id)) not in yes:
                        errors.append(f"{qid}: unverified group evidence: {mid}")
                    if not eligible(by_id[mid], query):
                        errors.append(f"{qid}: filtered/out-of-time group evidence: {mid}")
            for mid, grade in relevant.items():
                row = by_id.get(mid)
                if not row:
                    errors.append(f"{qid}: missing corpus message {mid}")
                    continue
                if not eligible(row, query):
                    errors.append(f"{qid}: filtered/out-of-time relevant message {mid}")
                if grade == 3 and not set(fact_ids) & set(row["plants"]):
                    errors.append(f"{qid}: grade 3 is not a plant: {mid}")
                if grade == 2 and not set(fact_ids) & set(row["refs"]):
                    errors.append(f"{qid}: grade 2 is not a ref: {mid}")
                if grade == 2 and not any(cache_key(part["claim"], mid, payload(row, by_id)) in yes
                                          for part in parts):
                    errors.append(f"{qid}: grade 2 ref not verified: {mid}")
            g3_text = [by_id[mid]["text"] for mid, grade in relevant.items() if grade == 3 and mid in by_id]
            overlap = lexical_overlap(query["query"], g3_text)
            if query["lexical_overlap"] != overlap:
                errors.append(f"{qid}: lexical_overlap {query['lexical_overlap']} != {overlap}")
            if ("paraphrase" in query["tags"]) != (overlap < 0.3):
                errors.append(f"{qid}: incorrect paraphrase tag")
            if query.get("exact_target") and relevant.get(query["exact_target"]) != 3:
                errors.append(f"{qid}: exact_target must be grade 3")
            if query["type"] == "catch_up":
                kinds["catch_up"] += 1
                start, end = map(date.fromisoformat, query["window"])
                if filters["after"] != str(start) or filters["before"] != str(end + timedelta(days=1)):
                    errors.append(f"{qid}: catch-up filters do not match window")
                for fact in fact_ids:
                    if not any(fact in by_id[mid]["plants"] for mid, grade in relevant.items() if grade == 3):
                        errors.append(f"{qid}: no plant for catch-up fact {fact}")
        else:
            kinds["unanswerable"] += 1
            if relevant or groups or parts or query.get("answer") is not None or query["lexical_overlap"] is not None:
                errors.append(f"{qid}: never-discussed query has evidence/answer")
            search = query.get("absence_check") or {}
            if not search.get("terms") or not search.get("conclusion"):
                errors.append(f"{qid}: missing corpus search record")
            for term, expected in search.get("terms", {}).items():
                count = sum(bool(re.search(term, row["text"], re.IGNORECASE)) for row in rows)
                if count != expected:
                    errors.append(f"{qid}: search {term!r} found {count}, expected {expected}")
    for fact, used_splits in splits.items():
        if len(used_splits) > 1:
            errors.append(f"{fact}: appears in both dev and test")
    windows = {tuple(q["window"]) for q in queries if q["type"] == "catch_up"}
    required = {("2026-09-14", "2026-09-18"), ("2026-09-21", "2026-09-25"), ("2026-09-28", "2026-10-02")}
    if len(queries) < 44 or kinds["unanswerable"] != 6 or kinds["no_decision"] != 2 or not required <= windows:
        errors.append("query count/type/window requirement unmet")
    if sum("paraphrase" in q["tags"] for q in queries if q["answerable"]) < 10:
        errors.append("fewer than 10 answerable paraphrase queries")
    if errors:
        raise SystemExit("Query validation failed:\n" + "\n".join(f"- {e}" for e in errors))
    print(f"Valid: {len(queries)} queries; {kinds['fact']} factual, {kinds['no_decision']} no_decision, "
          f"{kinds['unanswerable']} unanswerable, {kinds['catch_up']} catch-up; "
          f"{sum('paraphrase' in q['tags'] for q in queries if q['answerable'])} paraphrase; "
          f"{len(splits)} facts, no dev/test overlap")


if __name__ == "__main__":
    main()
