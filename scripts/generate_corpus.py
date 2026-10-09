"""Generate and cache one structured response per channel-day."""

import argparse
import copy
import hashlib
import json
import re
from math import ceil
from datetime import date, timedelta
from pathlib import Path

import tiktoken
import yaml
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from openai import OpenAI
from pydantic import BaseModel

from recallhq.config import Settings
from recallhq.generation.prompts import CORPUS_PROMPT
from recallhq.ingestion.validate import validate_corpus


ROOT = Path(__file__).resolve().parents[1]
STORY_PATH = ROOT / "data/synthetic/story.yaml"
RAW = ROOT / "data/synthetic/raw"
CORPUS = ROOT / "data/synthetic/corpus.jsonl"
REPAIRS = ROOT / "data/synthetic/repairs.yaml"
TOKEN_LIMIT = 1_500_000


class GeneratedMessage(BaseModel):
    local_id: str
    channel: str
    author: str
    created_at: str
    parent_id: str | None
    text: str
    plants: list[str]
    refs: list[str]


class DayResponse(BaseModel):
    messages: list[GeneratedMessage]


def story() -> dict:
    return yaml.safe_load(STORY_PATH.read_text())


def cache_version() -> str:
    digest = hashlib.sha256()
    digest.update(repr(CORPUS_PROMPT.messages).encode())
    digest.update(STORY_PATH.read_bytes())
    digest.update(json.dumps(DayResponse.model_json_schema(), sort_keys=True).encode())
    return digest.hexdigest()[:12]


def channel_facts(book: dict, channel_id: str, day: date) -> list[dict]:
    selected = []
    for fact in book["facts"]:
        channels = fact["channel"] if isinstance(fact["channel"], list) else [fact["channel"]]
        if fact["date"] != day or channel_id not in channels:
            continue
        # Explicit allowlist: label_notes and future/cross-fact metadata cannot reach the model.
        public = {key: fact[key] for key in ("id", "fact", "owner", "language", "thread_instruction", "key_tokens") if key in fact}
        if "channel_instructions" in fact:
            public["fact"] = fact["channel_instructions"][channel_id]
            public["owner"] = fact["owner"][channels.index(channel_id)]
        selected.append(public)
    return selected


def tasks(book: dict) -> list[tuple[str, date, list, set[str]]]:
    result = []
    day = book["period"]["start"]
    while day <= book["period"]["end"]:
        if day.weekday() < 5:
            for channel in book["channels"]:
                facts = channel_facts(book, channel["id"], day)
                brief = {
                    "premise": book["premise"],
                    "date": day.isoformat(),
                    "timezone": book["timezone"],
                    "channel": channel,
                    "personas": book["personas"],
                    "filler_topics": book["filler_topics"],
                    "story_so_far": [
                        {"id": fact["id"], "date": fact["date"].isoformat(), "channel": fact["channel"],
                         "fact": fact["fact"], "key_tokens": fact["key_tokens"]}
                        for fact in book["facts"] if fact["date"] < day
                    ],
                    "facts": facts,
                    "target_messages": book["period"]["target_messages_per_channel_day"],
                }
                prompt = CORPUS_PROMPT.format_messages(brief=json.dumps(brief, default=str))
                result.append((channel["id"], day, prompt, {fact["id"] for fact in facts}))
        day += timedelta(days=1)
    return result


def cache_dir(channel: str, day: date) -> Path:
    return RAW / cache_version() / channel / day.isoformat()


def apply_repair(rows: list[dict], channel: str, day: date, attempt: int) -> list[dict]:
    if not REPAIRS.exists():
        return rows
    repair = (yaml.safe_load(REPAIRS.read_text()) or {}).get("repairs", {}).get(f"{channel}:{day}")
    if not repair or repair["attempt"] != attempt:
        return rows
    updated = copy.deepcopy(rows)
    by_id = {row["local_id"]: row for row in updated}
    for local_id, changes in repair["messages"].items():
        if local_id not in by_id:
            raise ValueError(f"repair target missing: {channel}:{day}:{local_id}")
        by_id[local_id].update(changes)
    return updated


def ref_supported(text: str, fact: dict) -> bool:
    """Keep references with identifying content; favor precision over recall."""
    lower = text.casefold()
    if fact["id"] == "F01":
        return bool(re.search(r"2026-10-02|oct(?:ober)?[ .-]*0?2\b", lower)) or ("qr" in lower and "attendance" in lower)
    if any(token.casefold() in lower for token in fact["key_tokens"]):
        return True
    if fact["id"] == "F23":
        return all(term in lower for term in ("gate 3", "lanyard", "drill"))
    if fact["id"] == "F33":
        return bool(re.search(r"oct(?:ober)?[ .-]*0?[23]\b|2026-10-0[23]", lower))
    if fact["id"] == "F36":
        return "deploy" in lower and "freeze" in lower and bool(re.search(r"18:00|oct(?:ober)?[ .-]*0?1\b|2026-10-01", lower))
    if fact["id"] == "F17":
        return bool((re.search(r"join|export", lower) and re.search(r"attendance|scan|report|postgres", lower))
                    or ("postgres" in lower and re.search(r"dedup|constraint|mongo|relational|join", lower))
                    or ("timeline" in lower and re.search(r"migrat|switch", lower)))
    stop = {"about", "after", "again", "because", "before", "current", "demo", "first", "later",
            "only", "pilot", "still", "team", "that", "their", "there", "these", "this", "those",
            "with", "would", "should"}
    pattern = r"[a-z][a-z0-9_+-]{3,}|\b\d+(?:%|:\d+)?\b"
    fact_terms = {word[:5] for word in re.findall(pattern, fact["fact"].casefold()) if word not in stop}
    text_terms = {word[:5] for word in re.findall(pattern, lower) if word not in stop}
    return len(fact_terms & text_terms) >= 2


def normalize_day(rows: list[dict], day: date, required: set[str], facts: list[dict]) -> list[dict]:
    """Fix mechanical tag and parent mistakes while retaining the raw response in cache."""
    rows = copy.deepcopy(rows)
    fact_dates = {fact["id"]: fact["date"] for fact in facts}
    facts_by_id = {fact["id"]: fact for fact in facts}
    introduced: set[str] = set()
    for row in rows:
        raw_plants, raw_refs = row["plants"], row["refs"]
        row["plants"] = list(dict.fromkeys(fact_id for fact_id in raw_plants if fact_id in required))
        row["refs"] = list(dict.fromkeys(
            fact_id for fact_id in [*raw_refs, *raw_plants]
            if (fact_id in fact_dates and fact_dates[fact_id] < day
                or fact_id in introduced and fact_id not in row["plants"])
            and ref_supported(row["text"], facts_by_id[fact_id])
        ))
        introduced.update(row["plants"])
    by_id = {row["local_id"]: row for row in rows}
    for row in rows:
        parent_id = row["parent_id"]
        if parent_id and parent_id in by_id:
            parent = by_id[parent_id]
            if parent["parent_id"] and parent["parent_id"] in by_id:
                row["parent_id"] = parent["parent_id"]
    replies = {}
    for row in rows:
        if row["parent_id"]:
            replies.setdefault(row["parent_id"], []).append(row)
    for root_id, children in list(replies.items()):
        if len(children) != 1:
            continue
        child = children[0]
        special = next((fact_id for fact_id in ("F20", "F36") if fact_id in child["plants"]), None)
        if special:
            keywords = ("qr format", "v2", "frozen") if special == "F20" else ("deploy freeze", "freeze deploy")
            candidate = next((row for row in rows if row["parent_id"] is None
                              and row["local_id"] != root_id
                              and row["created_at"] > child["created_at"]
                              and row["local_id"] not in replies
                              and any(word in row["text"].casefold() for word in keywords)), None)
            if candidate:
                candidate["parent_id"] = root_id
        else:
            child["parent_id"] = None
    return rows


def validate_day(rows: list[dict], channel: str, day: date, required: set[str], authors: set[str], facts: list[dict]) -> list[str]:
    errors = []
    if not 12 <= len(rows) <= 16:
        errors.append(f"{channel} {day}: expected 12-16 messages, got {len(rows)}")
    for row in rows:
        if row["channel"] != channel or not row["local_id"].startswith(day.strftime("%Y%m%d") + "-"):
            errors.append(f"{channel} {day}: wrong channel or local id")
        if not row["created_at"].startswith(day.isoformat()):
            errors.append(f"{channel} {day}: wrong date")
    known = {fact["id"] for fact in facts}
    earlier = {fact["id"] for fact in facts if fact["date"] < day}
    applicable = [fact for fact in facts if fact["date"] <= day]
    errors.extend(validate_corpus(rows, known, authors, require_all=False,
                                  key_tokens={fact["id"]: fact["key_tokens"] for fact in facts}))
    reply_counts = {}
    roots = {row["local_id"]: row for row in rows if not row["parent_id"]}
    short_reply_parents = {
        (row["parent_id"], fact_id)
        for row in rows for fact_id in ("F20", "F36")
        if row["parent_id"] and fact_id in row["plants"]
    }
    if len(roots) * 2 < len(rows):
        errors.append(f"{channel} {day}: fewer than 50% top-level messages")
    zoya_rows = [row for row in rows if row["author"] == "zoya"]
    if len(zoya_rows) >= 2:
        hinglish = sum(len(set(re.findall(
            r"\b(?:haan|kal|yaar|bhai|thoda|nahi|kya|hai|hoon|hoga|pe|baje|dono|wala|waise|abhi|ab|mujhe|bas|warna|karne|hain|padega|woh|kar|rahi|ke|ko|milna|laungi)\b",
            row["text"].casefold(),
        ))) >= 2 for row in zoya_rows)
        if hinglish < ceil(len(zoya_rows) * 0.4):
            errors.append(f"{channel} {day}: Zoya needs roughly half her messages mainly in Hinglish")
    introduced: set[str] = set()
    for row in rows:
        if re.search(r"[\u0900-\u097f\u0980-\u09ff]", row["text"]):
            errors.append(f"{channel} {day}: all chat text must use Latin script in {row['local_id']}")
        if row["parent_id"]:
            if row["parent_id"] not in roots:
                errors.append(f"{channel} {day}: reply-to-reply or missing root {row['local_id']}")
            reply_counts[row["parent_id"]] = reply_counts.get(row["parent_id"], 0) + 1
        for ref in row["refs"]:
            if ref not in earlier and ref not in introduced:
                errors.append(f"{channel} {day}: ref must point to an earlier fact: {ref}")
        if {"F09", "F31"} <= set(row["refs"]):
            text = row["text"].casefold()
            if not (("28p01" in text and "28000" in text) or
                    (re.search(r"stale|password|volume", text) and re.search(r"username|role", text))):
                errors.append(f"{channel} {day}: ambiguous refs conflate the two Postgres auth errors in {row['local_id']}")
        if "F14" in row["refs"] and not re.search(r"qr_expired|expires_at|expir|15.min", row["text"].casefold()):
            errors.append(f"{channel} {day}: unsupported F14 ref in {row['local_id']}")
        if set(row["plants"]) - required:
            errors.append(f"{channel} {day}: plants must be today's channel facts")
        text = row["text"].casefold()
        for fact in applicable:
            if any(token.casefold() in text for token in fact["key_tokens"]):
                if (fact["id"] not in row["plants"] and fact["id"] not in row["refs"]
                        and (row["local_id"], fact["id"]) not in short_reply_parents):
                    errors.append(f"{channel} {day}: missing plant/ref for key token of {fact['id']} in {row['local_id']}")
        introduced.update(row["plants"])
    if len(reply_counts) > 3:
        errors.append(f"{channel} {day}: more than three threads")
    for root_id, count in reply_counts.items():
        if not 2 <= count <= 6:
            errors.append(f"{channel} {day}: thread {root_id} has {count} replies")
    errors.extend(f"unplanted fact {fact_id}" for fact_id in sorted(required - {plant for row in rows for plant in row["plants"]}))
    for fact_id, exact_reply in (("F20", "yes, do that"), ("F36", "+1, go with that")):
        if fact_id in required and not any(
            row["text"].strip() == exact_reply and row["parent_id"] and fact_id in row["plants"]
            for row in rows
        ):
            errors.append(f"{channel} {day}: {fact_id} needs its exact planted thread reply")
    if "F17" in required:
        planted_roots = {row["local_id"] for row in rows if "F17" in row["plants"] and not row["parent_id"]}
        if not any(reply_counts.get(root_id, 0) >= 4 for root_id in planted_roots):
            errors.append(f"{channel} {day}: F17 needs a planted root with at least four replies")
        for row in rows:
            text = row["text"].casefold()
            if (re.search(r"join|report|export", text) and re.search(r"dedup|constraint|unique", text)
                    and re.search(r"timeline|migrat", text)):
                errors.append(f"{channel} {day}: F17 reasons collapsed into one message {row['local_id']}")
    return errors


def cached_rows(channel: str, day: date, required: set[str], authors: set[str], facts: list[dict]) -> list[dict] | None:
    for path in sorted(cache_dir(channel, day).glob("attempt-*.json"), reverse=True):
        data = json.loads(path.read_text())
        rows = (data.get("parsed") or {}).get("messages", [])
        rows = apply_repair(rows, channel, day, int(path.stem.split("-")[-1])) if rows else rows
        rows = normalize_day(rows, day, required, facts) if rows else rows
        if rows and not validate_day(rows, channel, day, required, authors, facts):
            return rows
    return None


def estimate(pending: list[tuple], model: str) -> tuple[int, int, float]:
    encoder = tiktoken.get_encoding("o200k_base")
    input_tokens = sum(sum(len(encoder.encode(message.content)) for message in prompt) + 500 for _, _, prompt, _ in pending)
    # 12-16 structured messages plus a small reasoning/output allowance per call.
    output_tokens = len(pending) * 2400
    paid_equivalent = input_tokens * 0.75 / 1_000_000 + output_tokens * 4.50 / 1_000_000
    return input_tokens, output_tokens, paid_equivalent


def cumulative_tokens() -> tuple[int, int]:
    input_tokens = output_tokens = 0
    for path in RAW.glob("*/**/attempt-*.json"):
        usage = (json.loads(path.read_text()).get("raw") or {}).get("usage_metadata") or {}
        input_tokens += usage.get("input_tokens", 0)
        output_tokens += usage.get("output_tokens", 0)
    return input_tokens, output_tokens


def generate(pending: list[tuple], settings: Settings, authors: set[str], facts: list[dict]) -> None:
    OpenAI(api_key=settings.openai_api_key).models.retrieve(settings.generation_model)
    model = ChatOpenAI(model=settings.generation_model, api_key=settings.openai_api_key, reasoning_effort="none")
    runnable = model.with_structured_output(DayResponse, method="json_schema", include_raw=True)
    queue = pending[:]
    attempts = {(channel, day): len(list(cache_dir(channel, day).glob("attempt-*.json")))
                for channel, day, _, _ in pending}
    first_pass = 0
    first_calls = 0
    while queue:
        batch, queue = queue[:10], queue[10:]
        if any(attempts[(channel, day)] >= 4 for channel, day, _, _ in batch):
            raise RuntimeError("Four-attempt limit reached for a channel-day; inspect raw cache")
        used = sum(cumulative_tokens())
        projected = sum(estimate(batch, settings.generation_model)[:2])
        if used + projected > TOKEN_LIMIT:
            raise RuntimeError(f"Token guard: {used:,} already used; next batch projected at {projected:,}")
        outputs = runnable.batch([item[2] for item in batch], config={"max_concurrency": 6}, return_exceptions=True)
        for (channel, day, prompt, required), output in zip(batch, outputs):
            key = (channel, day)
            attempt = attempts[key]
            attempts[key] += 1
            folder = cache_dir(channel, day)
            folder.mkdir(parents=True, exist_ok=True)
            if isinstance(output, Exception):
                if attempt == 0:
                    first_calls += 1
                (folder / f"attempt-{attempt:02d}.json").write_text(json.dumps({"error_type": type(output).__name__}))
                feedback = HumanMessage(content=f"The prior channel-day generation failed with {type(output).__name__}. Regenerate the entire day following the schema and thread rules.")
                queue.append((channel, day, [*prompt, feedback], required))
                print(f"{channel} {day}: call failed ({type(output).__name__})")
                continue
            parsed = output["parsed"]
            data = {
                "raw": output["raw"].model_dump(mode="json"),
                "parsed": parsed.model_dump(mode="json") if parsed else None,
                "parsing_error": str(output["parsing_error"]) if output["parsing_error"] else None,
            }
            (folder / f"attempt-{attempt:02d}.json").write_text(json.dumps(data, ensure_ascii=False, indent=2))
            rows = normalize_day(data["parsed"]["messages"], day, required, facts) if parsed else []
            errors = validate_day(rows, channel, day, required, authors, facts) if parsed else ["parse failed"]
            if attempt == 0:
                first_calls += 1
                first_pass += not errors
            if errors:
                print(f"{channel} {day}: {len(errors)} validation errors; retrying ({'; '.join(errors[:3])})")
                feedback = HumanMessage(content="The prior response failed validation. Regenerate the entire channel-day and fix every issue: " + "; ".join(errors[:12]))
                queue.append((channel, day, [*prompt, feedback], required))
        spent = sum(cumulative_tokens())
        print(f"Generation progress: {len(pending) - len(queue)}/{len(pending)} channel-days resolved; cumulative {spent:,} tokens")
        if spent > TOKEN_LIMIT:
            raise RuntimeError(f"Token guard exceeded: {spent:,} tokens")
    if first_calls:
        print(f"First-attempt pass rate this run: {first_pass}/{first_calls} ({first_pass / first_calls:.1%})")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--estimate", action="store_true", help="Print estimate without an API call")
    parser.add_argument("--only", action="append", metavar="CHANNEL:YYYY-MM-DD", help="Generate only selected channel-days; repeatable")
    parser.add_argument("--quiet", action="store_true", help="Skip printing each generated message with --only")
    args = parser.parse_args()
    book = story()
    all_tasks = tasks(book)
    authors = {persona["id"] for persona in book["personas"]}
    if args.only:
        selected = set(args.only)
        all_tasks = [item for item in all_tasks if f"{item[0]}:{item[1].isoformat()}" in selected]
        if len(all_tasks) != len(selected):
            raise SystemExit("--only must name existing channel-days as CHANNEL:YYYY-MM-DD")
    pending = [item for item in all_tasks if cached_rows(item[0], item[1], item[3], authors, book["facts"]) is None]
    settings = Settings()
    input_tokens, output_tokens, dollars = estimate(pending, settings.generation_model)
    print(f"Channel-days: {len(all_tasks)}; uncached calls: {len(pending)}")
    print(f"Estimated tokens: {input_tokens:,} input + {output_tokens:,} output = {input_tokens + output_tokens:,} total")
    print(f"Estimated paid equivalent: ${dollars:.2f} at standard {settings.generation_model} rates; actual free-tier charge may differ")
    if args.estimate:
        return
    if input_tokens + output_tokens > 1_000_000 or dollars > 2:
        raise SystemExit("Spend guard: estimate exceeds 1M tokens or $2; get approval before running")
    if pending:
        generate(pending, settings, authors, book["facts"])
    rows = []
    for channel, day, _, required in all_tasks:
        cached = cached_rows(channel, day, required, authors, book["facts"])
        if cached is None:
            raise RuntimeError(f"No valid cache for {channel} {day}")
        rows.extend(cached)
    rows.sort(key=lambda row: (row["created_at"], row["channel"], row["local_id"]))
    errors = validate_corpus(rows, {fact["id"] for fact in book["facts"]}, authors, require_all=not args.only,
                             key_tokens={fact["id"]: fact["key_tokens"] for fact in book["facts"]})
    if errors:
        raise RuntimeError("Corpus invalid:\n" + "\n".join(errors))
    if args.only:
        if not args.quiet:
            for channel, day, _, required in all_tasks:
                print(f"\n## {channel} {day}")
                for row in cached_rows(channel, day, required, authors, book["facts"]):
                    marker = f" ↳{row['parent_id']}" if row["parent_id"] else ""
                    print(f"{row['created_at'][11:16]} {row['author']}{marker}: {row['text']}  [plants: {','.join(row['plants']) or '-'}; refs: {','.join(row['refs']) or '-'}]")
        else:
            print(f"Validated {len(rows)} messages across {len(all_tasks)} selected channel-days")
        return
    CORPUS.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows))
    print(f"Validated and wrote {len(rows)} messages to {CORPUS}")


if __name__ == "__main__":
    main()
