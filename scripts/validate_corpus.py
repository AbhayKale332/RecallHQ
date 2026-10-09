"""Validate the frozen corpus independently of generation caches or Postgres."""

import json
from pathlib import Path

import yaml

from recallhq.ingestion.validate import validate_corpus


ROOT = Path(__file__).resolve().parents[1]
story = yaml.safe_load((ROOT / "data/synthetic/story.yaml").read_text())
rows = [json.loads(line) for line in (ROOT / "data/synthetic/corpus.jsonl").read_text().splitlines()]
errors = validate_corpus(rows, {fact["id"] for fact in story["facts"]},
                         {author["id"] for author in story["personas"]},
                         key_tokens={fact["id"]: fact["key_tokens"] for fact in story["facts"]})
if errors:
    raise SystemExit("Corpus validation failed:\n" + "\n".join(errors))
print(f"Valid: {len(rows)} messages, {len(story['facts'])} planted facts")
