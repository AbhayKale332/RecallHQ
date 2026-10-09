# RecallHQ

Day 1 imports the frozen synthetic Slack/Discord-style corpus into Postgres,
builds message and thread chunks, and embeds each chunk.

```bash
uv sync --locked
docker compose up -d
uv run python -m recallhq.cli migrate
uv run python scripts/validate_corpus.py
uv run python scripts/validate_queries.py
uv run python -m recallhq.cli ingest data/synthetic/corpus.jsonl
uv run pytest -q
```

Set `OPENAI_API_KEY` in your environment or a local `.env`; the local database
defaults match `compose.yaml`. Ingest can be rerun: unchanged chunks retain their
embeddings. The count and API-token report is in
`data/synthetic/ingest-report.json`.

`uv run python scripts/qa_corpus.py` regenerates the detailed corpus QA report
when the original generation caches in `data/synthetic/raw/` are available.
