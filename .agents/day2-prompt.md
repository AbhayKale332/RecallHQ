You are implementing **Day 2** of RecallHQ: lexical, dense, and hybrid (RRF) retrieval as a LangGraph
pipeline, plus the evaluation harness that produces the first results table (E0–E2). AI/ML-interview
project: the quality and honesty of the measurements matter most.

Read first, fully: `.agents/5-day-plan.md` (scope, "Framework usage", "Evaluation spec", Day 2),
`README.md`, `evals/queries.yaml` (schema), `migrations/001_initial.sql`, `src/recallhq/` (Day 1 code).
Do not implement Day 3+ (reranking, answer generation, bots).

## Preconditions (stop and report if any fails)
- `docker compose up -d`, DB has 2,233 messages, 2,391 chunks, all embedded with text-embedding-3-small.
- `scripts/validate_corpus.py`, `scripts/validate_queries.py`, `pytest` pass.
- Day 1 is committed (record the git sha in every run's metadata).

## Build
1. **Lexical retrieval** `retrieval/lexical.py` — Postgres FTS on `chunks.tsv` (`simple` config),
   ranked by `ts_rank_cd`. Natural-language questions must NOT be AND-ed (`websearch_to_tsquery` /
   `plainto_tsquery` AND all terms and return almost nothing for long questions): tokenize in Python,
   drop a small English stopword list (the `simple` config keeps stopwords), keep identifiers intact
   (`28P01`, `QR_EXPIRED`, `23505`, `ALLOWED_ORIGINS`, `/healthz`), and OR the terms with
   `to_tsquery('simple', ...)` built from bound, escaped lexemes (no string-concatenated SQL).
2. **Dense retrieval** `retrieval/dense.py` — embed the query with the same model as the chunks
   (`embed()`), exact cosine search `embedding <=> :q` filtered by `embedding_model`; no ANN index.
   Cache query embeddings on disk keyed by (model, text) so eval reruns make no API calls.
3. **Filters inside SQL** for every branch: channel, author, after, before. Date-only filter values
   mean Asia/Kolkata day boundaries (convert to timestamptz `+05:30`); `before` is exclusive. Author
   filters join chunk → message(s). Never post-filter a shortlist.
4. **RRF** `retrieval/fusion.py` — hand-written: score = Σ 1/(60 + rank), ranks 1-based, top 50 per
   branch, dedupe by chunk id, ties by best single-branch rank then chunk id. Keep each candidate's
   per-branch ranks.
5. **LangGraph pipeline** `pipeline/graph.py` — `StateGraph` with a typed `State`
   (query, request_time, filters, run config, lexical_hits, dense_hits, fused, timings_ms).
   Nodes: `prepare` → (`lexical` ∥ `dense`, fan-out) → `fuse` → END. Run config selects branches:
   E0 = lexical only, E1 = dense only, E2 = both + RRF (single-branch configs pass their list through
   `fuse` unchanged). Record per-node latency. Retrieval nodes call the plain SQL functions above.
   Filters come from the structured query fields (no LLM filter parsing today).
6. **Retrieval unit for E0–E2: message chunks only** (`kind = 'message'`). Thread chunks are the E4
   experiment on Day 3 — keep the code able to include them via config.

## Evaluation harness `evals/run.py`
- `uv run python -m evals.run --config E0|E1|E2 --split dev|test|all` invokes the graph per query and
  writes `evals/runs/<UTC timestamp>_<config>.jsonl` (per query: ranked chunk ids, mapped message ids,
  branch ranks, metrics, timings) and run metadata (git sha, corpus sha256, queries.yaml sha256,
  embedding model, k values, package versions).
- Scored queries: all answerable retrieval queries, including `no_decision` (F35 evidence).
  Exclude `unanswerable` (scored on Day 3 as abstention) and `catch_up` (Day 4).
- Metrics (hand-written in `evals/metrics.py`, unit-tested on hand-computed examples):
  - **Evidence-group recall@k** (k = 5, 10, 20, 50; main metric): fraction of a query's evidence
    groups with ≥ 1 member among the messages of the top-k chunks.
  - **nDCG@10** with graded `relevant` (gain = grade; unlisted = 0; ideal DCG from the query's grades).
  - **MRR@10**: reciprocal rank of the first chunk containing a message with grade ≥ 2.
  - **Exact-message hit@10** for `search` queries with an exact target.
- `evals/report.py` → `evals/reports/day2-E0-E2.md`:
  - rows = config, columns = metrics; one table each for dev, test, and slices
    (all / easy / non-easy / paraphrase / exact / filtered / as_of / cross_language / why).
  - p50/p95 latency per node.
  - per-query comparison E2 vs E0 and E2 vs E1 on EG-recall@10 and nDCG@10: wins / ties / losses
    with query ids, plus a paired bootstrap 95% CI of the mean difference (10,000 resamples, fixed seed).
  - a short "notable queries" list: where lexical wins (exact codes), where dense wins (paraphrase),
    where RRF fixes both, and where all three fail (with the missing evidence message).
- No tuning in Day 2. If you change anything after looking at results, use dev only and say so.

## Tests (no network; DB integration tests may use the compose DB and be marked)
RRF on a hand-computed 3-candidate example incl. ties; each metric on hand-computed cases (incl. a
query with 2 groups and graded nDCG); tsquery builder keeps identifiers and drops stopwords and is safe
against quotes/`&|!:()` in user text; IST date-boundary conversion; a filter integration test proving
author/channel/date constraints apply in both branches.

## Learning note
Write `docs/learning/day2.md` (≤ 1 page): what was built by hand vs LangGraph, the E0–E2 table, one
lexical win, one dense win, one RRF fix, one failure, and what you'd try next. Use only measured numbers.

## Constraints
- Only query embeddings call OpenAI today (expected < $0.01). No chat-model calls.
- Keep code small and typed; no `langchain-postgres`/PGVector; no abstractions for later.
- Don't modify `data/synthetic/corpus.jsonl` or `evals/queries.yaml`. If you find a label problem,
  report it instead of editing.
- Don't commit unless the user asks.

## Done when
E0, E1, E2 runs exist for dev and test, the report and learning note are written, pytest is green, and
you finish with a short summary: the headline table (dev + test, EG-recall@10/20, nDCG@10, MRR@10),
wins/losses with CI, the most interesting failures, latency, cost, and open issues for Day 3
(reranking + grounded answers).
