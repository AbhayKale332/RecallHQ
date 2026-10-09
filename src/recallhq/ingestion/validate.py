import re
from collections import Counter
from datetime import datetime, timedelta


FACT_ID_IN_TEXT = re.compile(r"F\d\d")
BAN_TEXT = re.compile(r"hinglish|persona|conflict with|no new decisions|acceptance criteria: nothing|archive|story", re.IGNORECASE)


def validate_corpus(
    messages: list[dict], fact_ids: set[str], author_ids: set[str] | None = None,
    require_all: bool = True, key_tokens: dict[str, list[str]] | None = None,
) -> list[str]:
    errors: list[str] = []
    seen: dict[tuple[str, str], dict] = {}
    plants: Counter[str] = Counter()
    last_time: dict[str, datetime] = {}
    by_id = {(row["channel"], row["local_id"]): row for row in messages}
    for row in messages:
        channel = row["channel"]
        local_id = row["local_id"]
        key = (channel, local_id)
        timestamp = datetime.fromisoformat(row["created_at"])
        if timestamp.utcoffset() != timedelta(hours=5, minutes=30):
            errors.append(f"timestamp must use +05:30 {channel}:{local_id}")
        if author_ids is not None and row["author"] not in author_ids:
            errors.append(f"unknown author {channel}:{local_id}: {row['author']}")
        if key in seen:
            errors.append(f"duplicate local id {channel}:{local_id}")
        if not row["text"].strip():
            errors.append(f"empty text {channel}:{local_id}")
        if FACT_ID_IN_TEXT.search(row["text"]):
            errors.append(f"fact id leaked into text {channel}:{local_id}")
        if match := BAN_TEXT.search(row["text"]):
            errors.append(f"banned text {match.group(0)!r} in {channel}:{local_id}")
        if channel in last_time and timestamp < last_time[channel]:
            errors.append(f"timestamps out of order {channel}:{local_id}")
        last_time[channel] = timestamp
        parent_id = row.get("parent_id")
        if parent_id:
            parent = seen.get((channel, parent_id))
            if parent is None or datetime.fromisoformat(parent["created_at"]) >= timestamp:
                errors.append(f"missing or late parent {channel}:{local_id} -> {parent_id}")
        for fact_id in row["plants"]:
            if fact_id not in fact_ids:
                errors.append(f"unknown planted fact {fact_id} in {channel}:{local_id}")
            evidence = by_id.get((channel, parent_id)) if fact_id in {"F20", "F36"} and parent_id else row
            if evidence is None:
                continue  # the missing parent is reported above
            for token in (key_tokens or {}).get(fact_id, []):
                if token.casefold() not in evidence["text"].casefold():
                    errors.append(f"plant {fact_id} in {channel}:{local_id} lacks key token {token!r}")
            plants[fact_id] += 1
        for fact_id in row.get("refs", []):
            if fact_id not in fact_ids:
                errors.append(f"unknown referenced fact {fact_id} in {channel}:{local_id}")
        seen[key] = row
    if require_all:
        for fact_id in sorted(fact_ids - plants.keys()):
            errors.append(f"unplanted fact {fact_id}")
    return errors
