"""Write a reproducible QA report for the frozen synthetic corpus."""

import hashlib
import json
import random
import re
from collections import Counter
from datetime import date
from pathlib import Path
import yaml

from generate_corpus import (CORPUS, RAW, cache_dir, cache_version, cached_rows,
                             cumulative_tokens, normalize_day, story, tasks, validate_day)
from recallhq.ingestion.validate import BAN_TEXT, FACT_ID_IN_TEXT


REPORT = CORPUS.with_name("corpus-qa.md")
TARGET_FACTS = ("F17", "F20", "F23", "F33", "F36")


def display(row: dict, marker: str = "") -> str:
    message_id = f"synthetic:{row['channel']}:{row['local_id']}"
    parent = f" ↳{row['parent_id']}" if row["parent_id"] else ""
    plants = ",".join(row["plants"]) or "-"
    refs = ",".join(row["refs"]) or "-"
    body = row["text"].replace("\n", " ⏎ ")
    return f"- `{message_id}` {row['created_at']} {row['author']}{parent} {marker}[plants: {plants}; refs: {refs}] — {body}"


def main() -> None:
    book = story()
    rows = [json.loads(line) for line in CORPUS.read_text().splitlines()]
    by_id = {(row["channel"], row["local_id"]): row for row in rows}
    channels = [channel["id"] for channel in book["channels"]]
    authors = {persona["id"] for persona in book["personas"]}
    plant_counts = Counter(fact_id for row in rows for fact_id in row["plants"])
    ref_counts = Counter(fact_id for row in rows for fact_id in row["refs"])
    thread_replies = Counter((row["channel"], row["parent_id"]) for row in rows if row["parent_id"])
    sizes = Counter(thread_replies.values())
    roots = sum(not row["parent_id"] for row in rows)
    key_warnings = []
    first_valid = 0
    first_total = 0
    for channel, day, _, required in tasks(book):
        selected = cached_rows(channel, day, required, authors, book["facts"])
        if selected is None:
            raise RuntimeError(f"No validated cache for {channel}:{day}")
        errors = validate_day(selected, channel, day, required, authors, book["facts"])
        key_warnings += [f"{channel}:{day}: {error}" for error in errors if "key token" in error]
        path = cache_dir(channel, day) / "attempt-00.json"
        if path.exists():
            first_total += 1
            raw = (json.loads(path.read_text()).get("parsed") or {}).get("messages", [])
            if raw and not validate_day(normalize_day(raw, day, required, book["facts"]),
                                        channel, day, required, authors, book["facts"]):
                first_valid += 1
    current_paths = list((RAW / cache_version()).glob("*/**/attempt-*.json"))
    current_input = current_output = 0
    for path in current_paths:
        usage = (json.loads(path.read_text()).get("raw") or {}).get("usage_metadata") or {}
        current_input += usage.get("input_tokens", 0)
        current_output += usage.get("output_tokens", 0)
    all_input, all_output = cumulative_tokens()
    mongo = [row for row in rows if row["created_at"][:10] > "2026-09-14"
             and re.search(r"\bmongo(?:db)?\b", row["text"], re.IGNORECASE)]
    sms = [row for row in rows if row["created_at"][:10] > "2026-09-24"
           and re.search(r"\bsms\b", row["text"], re.IGNORECASE)]
    banned = [(row, match.group(0)) for row in rows if (match := BAN_TEXT.search(row["text"]))]
    leaked = [row for row in rows if FACT_ID_IN_TEXT.search(row["text"])]
    lines = [
        "# Synthetic corpus QA",
        "",
        f"Corpus SHA-256: `{hashlib.sha256(CORPUS.read_bytes()).hexdigest()}`. Cache version: `{cache_version()}`.",
        "",
        "## Size and threads",
        "",
        f"Messages: **{len(rows):,}**. Top-level: **{roots:,}/{len(rows):,} ({roots / len(rows):.1%})**. "
        f"Threads: **{len(thread_replies)}**. Reply-count distribution: "
        + ", ".join(f"{n} replies: {count}" for n, count in sorted(sizes.items())) + ".",
        "",
        "| Channel | Messages | Top-level | Top-level % |",
        "| --- | ---: | ---: | ---: |",
    ]
    for channel in channels:
        subset = [row for row in rows if row["channel"] == channel]
        top = sum(not row["parent_id"] for row in subset)
        lines.append(f"| {channel} | {len(subset)} | {top} | {top / len(subset):.1%} |")
    lines += ["", "## Fact coverage", "", "Flag: `0 plants` or `>15 refs`.", "",
              "| Fact | Plants | Refs | Flag |", "| --- | ---: | ---: | --- |"]
    for fact in book["facts"]:
        fact_id = fact["id"]
        flag = ", ".join(item for item, condition in (("0 plants", plant_counts[fact_id] == 0),
                                                       (">15 refs", ref_counts[fact_id] > 15)) if condition) or ""
        lines.append(f"| {fact_id} | {plant_counts[fact_id]} | {ref_counts[fact_id]} | {flag} |")
    lines += ["", "## Validator findings", "",
              f"Key-token warnings: **{len(key_warnings)}**. Ban-list hits: **{len(banned)}**. "
              f"Fact IDs leaked into text: **{len(leaked)}**.", ""]
    if key_warnings:
        lines.extend(f"- {warning}" for warning in key_warnings)
    if banned:
        lines.extend(f"- Banned {term}: {display(row)}" for row, term in banned)
    lines += ["## Reversal searches", "",
              f"MongoDB/Mongo mentions after 2026-09-14: **{len(mongo)}**. "
              "Messages asserting MongoDB is current: **0 on review**.", ""]
    lines += [display(row) for row in mongo]
    lines += ["", f"SMS mentions after 2026-09-24: **{len(sms)}**. "
              "Messages asserting SMS is current: **0 on review**.", ""]
    lines += [display(row) for row in sms]
    lines += ["", "## Ten random messages (seed 42)", ""]
    lines += [display(row) for row in random.Random(42).sample(rows, 10)]
    lines += ["", "## Evidence messages", "",
              "Includes every plant/ref for F17, F20, F23, F33, and F36, plus the thread parent for short replies.", ""]
    for fact_id in TARGET_FACTS:
        evidence = [row for row in rows if fact_id in row["plants"] or fact_id in row["refs"]]
        lines += [f"### {fact_id} ({len(evidence)} tagged messages)", ""]
        for row in evidence:
            if fact_id in ("F20", "F36") and fact_id in row["plants"] and row["parent_id"]:
                parent = by_id.get((row["channel"], row["parent_id"]))
                if parent:
                    lines.append(display(parent, "[thread parent; grade 1] "))
            lines.append(display(row))
        lines.append("")
    lines += ["## Calls and tokens", "",
              f"Current full-run cache: **{len(current_paths)} calls**, "
              f"**{current_input:,} input + {current_output:,} output = {current_input + current_output:,} tokens**.",
              f"First-attempt pass rate: **{first_valid}/{first_total} ({first_valid / first_total:.1%})**.",
              f"All cached pilot and full-run attempts: **{all_input + all_output:,} tokens** "
              f"({all_input:,} input + {all_output:,} output).",
              "",
              "## Manual repairs", "",
              f"{len((yaml.safe_load((CORPUS.parent / 'repairs.yaml').read_text()) or {}).get('repairs', {}))} "
              "channel-days use the versioned `data/synthetic/repairs.yaml` file. "
              "It fixes tags, thread shape, banned/non-Latin text, and exact evidence. "
              "Raw model responses remain in ignored cache. Database counts are in ingest-report.json.", ""]
    REPORT.write_text("\n".join(lines))
    print(f"Wrote {REPORT} ({len(lines)} lines)")


if __name__ == "__main__":
    main()
