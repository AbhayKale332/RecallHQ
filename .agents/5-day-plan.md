# RecallHQ — 5-day build plan

Prepared: 2026-10-09. Deadline: demoable by end of day 5 (≈2026-10-14).
Audience: AI/ML engineer interviews. This plan is the scoped-down slice of
[generation-plan.md](generation-plan.md); that document is the "production roadmap / future work".

## Goal

A RAG system that **searches, answers questions about, and summarizes old Slack and Discord group-chat
messages**, with citations to the original messages, plus a reproducible evaluation report that
compares retrieval strategies on labeled data.

What must exist at the end of day 5:

1. Labeled synthetic chat corpus (Slack-style + Discord-style channels) and ≥40 labeled queries.
2. Postgres + pgvector index with lexical, dense, and hybrid (RRF) retrieval.
3. Reranking: local cross-encoder (primary) and the OpenAI Decisions API (`gpt-6-luna`) as an LLM-judge reranker (experiment).
4. Grounded answers with validated citation IDs and abstention.
5. Catch-up summaries over a time window (exhaustive, not top-k).
6. Live Discord bot + live Slack bot (Socket Mode) using the same core pipeline.
7. Streamlit web demo on the synthetic corpus (no install needed by reviewers).
8. README: architecture diagram, eval table, failure cases, demo video.

## Explicitly out of scope (talk about these as "production next steps")

Multi-tenant RLS, durable inbox/outbox + workers, backups/RPO/RTO, load tests, Langfuse, Ragas,
MCP server, HNSW tuning (exact search is fine at this scale), GraphRAG, query rewriting/agents,
P1–P3 feature ideas from the main plan.

## Stack

| Concern | Choice |
| --- | --- |
| Language / deps | Python 3.12, `uv` |
| Store | PostgreSQL 16 + pgvector (Docker Compose), native FTS with the `simple` config |
| Embeddings | OpenAI `text-embedding-3-small` (1536 d) — not in the free tier, but the whole corpus costs cents |
| Generation | `gpt-5.4-mini` (free 2.5M-token/day tier) for corpus generation, answers and catch-up summaries; `gpt-5.4` (free 250k/day tier) only for the story bible and spot-check judging. Pin ids in config |
| Reranker | `BAAI/bge-reranker-v2-m3` via `sentence-transformers` CrossEncoder (local, E3); LLM-judge rerankers through **one OpenRouter Decisions adapter** (`POST https://openrouter.ai/api/alpha/decisions`, key `OPEN_ROUTER` in `.env`) with the model as config: `typesafe/jev-1.13-20260917` (E3c) and `openai/gpt-6-luna-decisions-20261006` (E3b). Both verified working on 2026-10-09. Primitive names there: `score` (criteria = ordered list), `choice`, `noul` |
| Bots | `discord.py` (slash commands, `defer()`), Slack Bolt for Python in Socket Mode (`ack()` then `respond()`) |
| Demo UI | Streamlit |
| Orchestration | LangGraph `StateGraph` for the query pipeline and catch-up map-reduce; LangChain (`langchain-openai`) for chat-model and embedding calls — see "Framework usage" |
| Evals | Plain Python + pandas over the LangGraph run state; results as JSONL + Markdown table |
| Tests | pytest |

Secrets come only from environment / `.env` (git-ignored): `OPENAI_API_KEY`,
`DISCORD_BOT_TOKEN`, `SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN`, `DATABASE_URL`.

## Token budget (free daily tiers on this OpenAI project)

- 2.5M tokens/day on mini models: corpus generation (~150 channel-day calls ≈ 0.5–0.7M), answer
  generation and catch-up during eval runs (40 queries × ~8k ≈ 0.3M per run). Cache everything.
- 250k tokens/day on `gpt-5.4`: story bible + small judge spot-checks only.
- Paid but tiny: embeddings, Decisions API (`gpt-6-luna`).
- These complimentary tokens appear to come from OpenAI's data-sharing program (traffic on that
  project may be used for training). Fine for synthetic data; do NOT send real people's private chats
  through this project.

## Framework usage — LangChain / LangGraph where they help, plain code where they don't

Install current stable `langchain`, `langchain-core`, `langchain-openai`, `langgraph` (pin via `uv.lock`) and
check the current docs before use — these APIs change between versions.

| Area | Use | Why |
| --- | --- | --- |
| Chat calls (corpus generation, answers, catch-up summaries, query drafting) | `ChatOpenAI(...).with_structured_output(PydanticModel)`; `.batch(inputs, config={"max_concurrency": N})` for fan-out | Typed outputs + retries + concurrency with little code; one place to swap models |
| Embeddings | `OpenAIEmbeddings` behind our `embed()`; later `HuggingFaceEmbeddings` (`langchain-huggingface`) for local `bge-m3` | The planned local swap becomes a config change |
| Prompts | `ChatPromptTemplate` kept in `generation/prompts.py` | Versionable prompts |
| Query pipeline | LangGraph `StateGraph`: `parse_filters → route → (lexical ∥ dense) → fuse → rerank → assemble → generate → validate_citations → END`, conditional edge to `abstain` | Graph state keeps every intermediate (branch ranks, RRF list, rerank scores, context ids) for evals and the demo; parallel branches; clean place for a later bounded rewrite loop |
| Catch-up | LangGraph map-reduce with `Send`: one `summarize_group` node per thread/window, then `merge` | The textbook LangGraph pattern for this exact workload |
| Retriever interface | Our SQL search wrapped as a small `BaseRetriever` subclass (optional) | Usable as a LangChain/LangGraph tool later |
| Tracing (optional) | LangSmith via env vars (`LANGSMITH_TRACING=true`) — synthetic data only | Per-node traces and screenshots for the README; check current free-tier terms |

Keep as plain code (frameworks add burden or hide what we measure here):

- **Schema, ingestion, normalization, thread-aware chunking** — specific to Slack/Discord data.
- **Retrieval SQL** (pgvector + FTS + filters in one query) — do **not** use `langchain-postgres` `PGVector`;
  it owns its own tables/metadata layout and doesn't do our filtered hybrid query. Nodes call our SQL.
- **RRF** (≈10 lines, an interview talking point), **metrics** (Recall/MRR/nDCG), the **eval harness**.
- **OpenAI Decisions reranker** — no LangChain integration; call `client.decisions.create` directly inside the
  `rerank` node. Cross-encoder via `sentence-transformers` directly (we need the raw scores logged).
- **Bots** — `discord.py` / Slack Bolt call `graph.ainvoke(...)`.
- No LangGraph checkpointer/memory for v1 (no multi-turn state needed); no agents in the core path.

## Core data model (shared by every source)

All sources (synthetic, Discord, Slack, optional public dataset) normalize into one message shape.
Platform IDs are **strings** (Slack `ts` and Discord snowflakes must never pass through float/int math).

```text
messages
  id               text pk      -- "{source}:{channel_id}:{source_message_id}"
  source           text         -- synthetic | discord | slack | public
  platform_style   text         -- slack | discord   (synthetic channels are tagged with one)
  workspace_id     text
  channel_id       text
  channel_name     text
  source_message_id text
  thread_root_id   text null    -- messages.id of the thread root; null for top-level
  author_id        text
  author_name      text
  text             text
  created_at       timestamptz
  permalink        text null
  metadata         jsonb        -- e.g. planted fact ids for synthetic data
  unique (source, channel_id, source_message_id)

chunks
  id               text pk      -- deterministic: sha256(kind + chunker_version + ordered message ids)
  kind             text         -- message | thread | window
  chunker_version  text
  channel_id       text
  message_ids      text[]
  start_at, end_at timestamptz
  text             text         -- rendered "[2026-09-02 14:05] Priya: ..." lines
  embedding        vector(1536)
  embedding_model  text
  tsv              tsvector generated always as (to_tsvector('simple', text)) stored
```

Relevance labels point at **message ids**, not chunk ids, so chunking experiments can be compared
fairly (a chunk "hits" a label when it contains a labeled message).

## Evaluation spec

`evals/queries.yaml`, one query per entry. Relevance points to **message ids** and uses
grades 3 (verified plant), 2 (verified ref), and 1 (unverified ref for that fact or the
parent of a short approval reply). Candidate messages come from plant/ref tags;
`gpt-5.4-mini` checks each candidate against each query part, with results cached in
`evals/ref-verifications.jsonl`. Only verified messages enter `evidence_groups`, with
one group per answer part. A short reply and its parent are separate groups when they
answer different parts.

```yaml
- id: Q27
  type: no_decision
  split: test
  fact_ids: [F35]
  tags: [F35]
  query: Who owns paid ticketing after the pilot?
  request_time: 2026-10-05T10:00:00+05:30
  filters: {channel: null, author: null, after: null, before: null}
  answerable: true
  answer_type: no_decision  # fact | no_decision | unanswerable
  parts:
    - {id: p1, fact_ids: [F35], claim: Paid ticketing was discussed for after the pilot, with no decision and no owner}
  evidence_groups:
    - {part: p1, message_ids: ["synthetic:product:20260922-09"]}
  relevant: {"synthetic:product:20260922-09": 3}
  lexical_overlap: 0.75
```

`request_time` defaults to 2026-10-05T10:00:00+05:30; as-of queries use their own
historical time. `filters` has `channel`, `author`, inclusive `after`, and exclusive
`before` fields. `lexical_overlap` is the share of unique query content tokens found
in grade-3 message text; tag `paraphrase` below 0.3. Tag `easy` if any query fact has
more than 15 corpus refs. `exact_target` identifies the grade-3 message for a
search/exact-message query.

Coverage of the ≥44 queries (split by fact so paraphrases share a split):
exact identifiers (error codes, commands, URLs), paraphrases, reversed decisions ("current" answer is the
newest), person + time filters, short replies needing thread context, Hinglish, multi-message evidence,
≥10 low-overlap paraphrases, six never-discussed unanswerable questions, two
`no_decision` paid-ticketing questions, and ≥3 catch-up windows with key-fact lists.

Report metrics for **all, easy, and non-easy** slices: Recall@20, Recall@50,
MRR@10, nDCG@10 (graded 0–3, gain = grade), citation precision, refusal rate
on `unanswerable` versus unnecessary refusals on answerable and `no_decision`
queries, catch-up key-fact recall, p50/p95 latency per stage, and cost per
query. Never-discussed unanswerables are excluded from recall/nDCG; `no_decision`
queries retain the F35 plant as grade-3 evidence.

Experiment ladder (identical corpus/queries; record git sha, corpus hash, models, k values):

| Run | Config |
| --- | --- |
| E0 | Lexical (FTS `simple`, `ts_rank_cd`) |
| E1 | Dense (cosine, exact search) |
| E2 | Hybrid RRF, `1/(60+rank)`, top 50 per branch |
| E3 | E2 + cross-encoder rerank of top 30 |
| E3b | E2 + GPT-6 Luna Decisions (via OpenRouter) rerank of the same top 30 (fallback to RRF order on any error) |
| E3c | E2 + Jev 1.13 (via OpenRouter) rerank of the same top 30, same rubric/state/fallback |
| E4 | Message-only chunks vs. thread-aware chunks (on the best of E2/E3) |

## Day-by-day

### Day 1 — Data foundation
- Repo scaffold (`uv`, `src/recallhq/`, `tests/`, `evals/`, `data/`, `compose.yaml`, `.env.example`).
- Postgres + pgvector via Docker Compose; SQL migration for `messages` and `chunks`.
- **Story bible** (`data/synthetic/story.yaml`): 6 personas with distinct writing styles (one Hinglish,
  one terse, one emoji-heavy, one pastes code), a 6-week student/startup project, 5 channels
  (3 tagged `slack`, 2 tagged `discord`), ~30 planted facts with ids (decisions, reversals, bugs +
  fixes with exact error codes/commands, owners + deadlines, a schedule change).
- **Generator** (`scripts/generate_corpus.py`): one OpenAI structured-output call per channel-day; given
  that day's facts + filler topics, returns messages with author, time, thread parent, text, and
  `plants: [fact_id]`. Cache raw responses; fixed seed; output `data/synthetic/corpus.jsonl`
  (~1.5–2.5k messages). Inject noise (lol, +1, typos, off-topic, links, code blocks).
- Validate: every fact planted ≥1 time, thread parents exist, timestamps monotonic per thread.
- Importer → `messages`; chunker → `message` and `thread` chunks (thread = root + replies, split
  >600 tokens with 1-message overlap); embed with batching + retry; FTS column populated.
- Draft ≥40 queries from planted facts (LLM-drafted, **human-reviewed**), write `evals/queries.jsonl`,
  and a validator that checks every labeled id exists in the DB.
- Exit: `docker compose up -d && uv run python -m recallhq.cli ingest data/synthetic/corpus.jsonl`
  loads + embeds everything; counts printed; `pytest` green; queries validated.

### Day 2 — Retrieval + eval harness
- `retrieval/lexical.py`, `retrieval/dense.py`, `retrieval/fusion.py` (RRF written by hand, stable ties).
- Filters (channel, author, time range) applied **inside** every SQL query, never post-filtered.
- Build the LangGraph query graph skeleton (`pipeline/graph.py`) with a typed `State`; configs E0–E2
  select which retrieval nodes run. Retrieval nodes call our SQL functions.
- `evals/run.py --config E0|E1|E2` invokes the graph per query and reads the final state → per-query JSONL
  + summary Markdown table.
- Unit tests: RRF math on a tiny example, filter correctness, metric functions on hand-computed cases.
- Stretch: import ~2k messages from a public dev-chat dataset (e.g. MSR'20 disentangled Slack chats or
  DISCO Discord dataset — verify license) + 10 hand-labeled queries as a "real data" slice.
- Exit: E0–E2 table committed in `evals/reports/`.

### Day 3 — Rerank + grounded answers
- Cross-encoder reranker (E3) and one OpenRouter Decisions adapter (E3b Luna, E3c Jev; model id from config) behind one `rerank(query, candidates)` interface. Pin dated model ids, log the response `model`, and never reuse a threshold across models (their score scales differ).
  Decisions: one request per candidate (input = query + candidate text + thread context), one `score`
  question with a shared 4-level relevance rubric (`levels` low→high); sort by the returned expected
  `score`, ties by RRF rank then id. Bounded concurrency, timeout/refusal/429 → RRF order for the whole
  query, log degraded mode. Optionally compare a `predicate` question ("contains evidence that answers
  the question") and an all-candidates-in-one-request variant for cost/latency.
- Optional: a Decisions `predicate` as the evidence-sufficiency gate for abstention (threshold tuned on
  dev split only).
- Context assembly: expand top hits to their thread (root + neighbors), ~6k-token evidence budget,
  stable citation ids `[S1]..[Sn]`.
- Add `rerank`, `assemble`, `generate`, `validate_citations`, `abstain` nodes to the graph.
- Answer generation: `with_structured_output` → `{answer, claims:[{text, source_ids}], abstain, reason}`;
  validate every cited id was in the context; build links from DB, never from model text; abstain when
  evidence is insufficient.
- Exit: full eval table E0–E3b (+ E4 if time), citation precision and refusal metrics, cost/latency
  columns.

### Day 4 — Bots + catch-up
- Catch-up graph: enumerate **all** messages in `[start, end)` for allowed channels → group by thread/window
  → `Send` one `summarize_group` per group (structured summary (decisions, actions w/ owner only if stated, blockers, open questions,
  source ids)) → `merge` node with citations + coverage line.
- Discord bot: `/recall search|ask|catchup`, `interaction.response.defer(ephemeral=True)` then
  followup; only channels the invoker can see (`channel.permissions_for(member)`); live `on_message`
  ingestion that does **not** drop our own webhook's seeded messages.
- Slack bot (Bolt, Socket Mode): `/recall <subcommand>`, `ack()` immediately, `respond()` ephemeral;
  restrict to channels the invoker is a member of; author from `username` for seeded bot messages.
- Seeding scripts: post ~150 messages / 2 channels / a few threads to each platform
  (Discord webhook with `username`; Slack `chat.postMessage` with `chat:write.customize`, `thread_ts`),
  save synthetic-id → platform-id maps.
- Exit: both bots answer a question with a working source link in a private server/workspace.

### Day 5 — Package + buffer
- Streamlit app: search / ask / catch-up tabs on the synthetic corpus, showing retrieved candidates,
  rerank scores, and citations (read straight from the graph state); include the graph diagram
  (`graph.get_graph().draw_mermaid()`).
- Stretch after day 5: bounded agentic loop — Decisions `predicate` "evidence sufficient?" → if not,
  one query rewrite + re-retrieve (max 1 loop), evaluated against the straight pipeline (E7).
- README: problem, architecture diagram, how to run, eval table, 3–4 failure cases (what broke, which
  metric showed it, what fixed it), limitations, "production roadmap" link to `generation-plan.md`.
- Record a 2–3 minute demo video. Keep half the day as buffer.

## Fallbacks if behind schedule

- Behind on day 2 → skip public-dataset slice.
- Behind on day 3 → keep E3 (cross-encoder); make Decisions E3b a stretch.
- Behind on day 4 → Discord bot live, Slack demonstrated via Streamlit on Slack-tagged channels.
- Never cut: labeled queries, E0–E3 table, citations + abstention, README with honest numbers.

## Interview talking points to prepare

1. Exact error code vs. paraphrase → why hybrid (show E0/E1/E2 rows).
2. RRF by hand on 3 candidates; why ranks not raw scores.
3. Missing from top-50 (retrieval failure) vs. present but ranked low (reranking fixes it).
4. Bi-encoder vs. cross-encoder vs. LLM-judge (OpenAI Decisions) reranking: cost, latency, measured gain;
   why a probability-weighted score sorts better than a hard yes/no.
5. "yes, do that" → thread-aware chunking (E4).
6. Why catch-up is enumeration + map-reduce, not top-k.
7. Synthetic vs. real data gap; why labels point at messages, not chunks.
8. Why LangGraph for the pipeline/catch-up but hand-written SQL retrieval, RRF and metrics (what each
   framework piece bought, what it would have hidden).
9. What production would add (from `generation-plan.md`): ACLs, idempotent ingestion, versioned
   embedding rollouts, deletion propagation.
