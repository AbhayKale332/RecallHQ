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

## Public demo

The [frontend](frontend/README.md) adapts the MIT-licensed
[Slack clone](https://github.com/sanidhyy/slack-clone) into a public Beacon
workspace. It opens with the synthetic archive, supports threads and paging,
and preloads an example command. Visitor messages and command results exist only
in the current tab. The archive remains read-only.
Each channel's unchanged example question uses a prepared answer in the frontend;
edited questions are sent to the API.

Live site: https://recallhq-black.vercel.app

Commands in the composer:

- `/ask <question>` — grounded answer with links to source messages
- `/search <terms>` — matching messages across channels
- `/catchup YYYY-MM-DD YYYY-MM-DD [#channel]` — date-bounded recap

The FastAPI service exposes `/health`, `/channels`, `/messages`, `/threads/{id}`,
and `/commands`. Run it locally with `uv run uvicorn recallhq.api:app --reload`
after migrating and ingesting Postgres. Set `DATABASE_URL` and `OPENAI_API_KEY`
in `.env`; the API limits anonymous commands to 3/minute and 20/day per IP,
plus 200/day site-wide. Limits persist in a local SQLite file (`QUOTA_DB`).

Production uses Vercel project `recallhq`, Azure resource group `recallhq-rg`
with PostgreSQL Flexible Server `recallhq-pg-abhay` (PostgreSQL 16, B1ms,
32 GB, `vector` allowlisted), and an isolated `recallhq-api` container on the
existing `recova-vm` Docker network. Caddy routes `/recallhq/api/*` to that
container. The database firewall permits only the VM's public IP. The API uses
a read-only PostgreSQL role and verifies the server certificate with the VM's
CA bundle. Runtime credentials are kept in the VM's
`/home/azureuser/recallhq/runtime.env`, outside this repository.
