You are implementing **Day 1** of RecallHQ, a RAG project that searches, answers questions about, and
summarizes old Slack/Discord group-chat messages. It is a 5-day interview portfolio project aimed at
AI/ML engineer roles, so correctness of data and labels matters more than infrastructure.

Read first, fully: `.agents/5-day-plan.md` (the source of truth for scope, data model, eval format and
Day 1 tasks). `.agents/generation-plan.md` is the long-term production roadmap — do NOT implement its
extra scope (RLS, multi-tenancy, queues, workers, Langfuse, Ragas, MCP).

## Environment facts
- Repo root: `/home/abhay/F/7th SEM/RAG-Proj/RecallHQ` (note the space in the path; quote it). Only
  `LICENSE` is committed. Do not modify `.agents/skills/` or the sibling reference repos
  `../tea-bot` and `../tiger-slack` (read them for ideas only; TeaL;DR has no reuse license).
- Available: `uv` 0.11, Python 3.12, Docker + Docker Compose v5. `psql` is not installed on the host —
  use `docker compose exec` or Python (`psycopg`) for DB access.
- The OpenAI key currently lives in `.env.save` as `OPEN_AI_API` (already git-ignored via `.gitignore`).
  Ask the user to rename it to `.env` with the standard name `OPENAI_API_KEY`; never print or read the
  value. Load settings with `pydantic-settings`; create `.env.example` with empty values.
- Models (free daily tiers on this project — cache aggressively, log tokens used per command):
  `gpt-5.4-mini` for corpus generation (2.5M tokens/day shared tier), `gpt-5.4` only for drafting the
  story bible (250k/day tier), `text-embedding-3-small` for embeddings (paid, cents). Verify the ids
  via the models API and pin them in config. Data on this project may be shared with OpenAI, so only
  synthetic data goes through it.

## Day 1 deliverables
1. **Scaffold**: `pyproject.toml` (uv), `src/recallhq/` package (`config.py`, `db.py`, `cli.py`,
   `ingestion/`, `retrieval/` placeholder only if needed), `tests/`, `evals/`, `data/synthetic/`,
   `scripts/`, `migrations/`, `compose.yaml` (pgvector/pgvector:pg16 image, healthcheck, named volume),
   `.gitignore`, `.env.example`, short `README.md` "how to run Day 1".
2. **Schema**: SQL migration creating `messages` and `chunks` exactly as in the plan (vector(1536),
   generated `tsv` using the `simple` config, GIN index on `tsv`, btree on `(channel_id, created_at)`,
   unique `(source, channel_id, source_message_id)`). A tiny migration runner is fine; no Alembic.
3. **Story bible** `data/synthetic/story.yaml`: 6 personas with distinct writing styles (one writes
   Hinglish, one terse, one emoji-heavy, one pastes code/commands), a 6-week student/startup project,
   5 channels (3 tagged `platform_style: slack`, 2 tagged `discord`), and ~30 planted facts with ids,
   dates, channels and owners. Include: decisions later reversed, bugs with exact error codes and the
   fixing command, owners + deadlines, a meeting time change, something decided in a thread via a short
   reply ("yes, do that"), and one Hinglish-only fact. Draft it, then **show it to the user for approval
   before generating the corpus.**
4. **Generator** `scripts/generate_corpus.py`: one structured-output call per channel-day via
   `ChatOpenAI(model=...).with_structured_output(<Pydantic model>)`, run with `.batch(...,
   config={"max_concurrency": 6})`
   (weekdays only is fine) using that day's planted facts + filler topics. Each message: local id,
   channel, author, created_at, parent_id (thread), text, `plants: [fact_id]`. Add realistic noise
   (lol/+1/typos/off-topic/links/code blocks). Cache every raw response under `data/synthetic/raw/`
   so reruns are free and deterministic; write `data/synthetic/corpus.jsonl` (~1.5–2.5k messages).
   Before running, print the number of calls and an estimated cost; check the model id exists via the
   OpenAI models API and pin it in config. Validate after generation: every fact planted ≥1 time,
   thread parents exist and precede replies, timestamps sorted, no empty texts. Retry/repair only the
   failing channel-days.
5. **Ingestion** `recallhq.cli ingest <corpus.jsonl>`: normalize to `messages` (ids are strings;
   `id = "synthetic:{channel_id}:{local_id}"`; planted fact ids go into `metadata`), idempotent upsert.
   Chunker produces `message` chunks and `thread` chunks (root + replies; split > ~600 tokens with
   1-message overlap) with deterministic sha256 ids and rendered text lines like
   `[2026-09-02 14:05] #eng Priya: ...`. Embed with `text-embedding-3-small` in batches, with retry and
   backoff; skip chunks that already have an embedding for the same model (re-runs must not re-pay).
   Keep all embedding calls in one `embed(texts) -> list[list[float]]` function (backed by
   `langchain_openai.OpenAIEmbeddings`) with the model name and
   dimension read from config and `embedding_model` stored per chunk — a local model (`bge-m3`, 1024 d)
   will replace OpenAI later, so the dimension must not be hard-coded anywhere else.
6. **Labels** `evals/queries.jsonl` in the plan's format: ≥40 queries (~30 dev / ≥10 test, split by
   fact/topic so paraphrases of one fact stay in one split). Draft from the planted facts with an LLM,
   then **present them to the user for review** — they must approve labels. Coverage as listed in the
   plan (exact identifiers, paraphrases, reversed decisions, person+time filters, thread-context short
   replies, Hinglish, multi-message evidence, ≥8 unanswerable, ≥3 catch-up windows with key facts).
   Relevance grades: 3 = directly states the answer, 2 = partial evidence, 1 = needed context.
   `scripts/validate_queries.py` checks every labeled id exists in the DB and every query has a split.
7. **Tests** (pytest): ID/timestamp string preservation, deterministic chunk ids across runs, thread
   chunk split boundaries, corpus validator catches a broken parent_id, query validator catches an
   unknown id. No test may call OpenAI (mock the client).

## Constraints
- Follow the "Framework usage" section of the plan: LangChain for chat-model/embedding calls and prompts,
  LangGraph for the query pipeline and catch-up (not needed until Day 2). Plain code for schema,
  ingestion, chunking, SQL retrieval, RRF and metrics. Do NOT use `langchain-postgres`/`PGVector` or
  LlamaIndex. Install current stable versions, pin them in `uv.lock`, and check current docs for APIs.
- Keep code small: typed functions, no abstractions "for later".
- Never commit `.env`, API keys, or raw real chat data. Do not git commit at all unless the user asks.
- Spend guard: stop and ask before any single command expected to cost more than ~$2 or to use more
  than ~1M tokens of the daily free tier.

## Done when
`docker compose up -d`, `uv run python -m recallhq.cli migrate`,
`uv run python -m recallhq.cli ingest data/synthetic/corpus.jsonl` all succeed from a clean DB; the CLI
prints message/chunk/embedded counts; `uv run pytest` is green; `scripts/validate_queries.py` passes;
the user has approved the story bible and the labeled queries. Finish with a short report: counts,
cost spent, anything skipped, and open issues for Day 2 (lexical/dense/RRF + eval harness).
