# Evaluation

Status (2026-10-15): **full run.** All four retrieval configurations and the
end-to-end answer evaluation were run with OpenAI `text-embedding-3-small` query
embeddings, `gpt-5.4-mini` for answers and judging, and Jev 1.13 for reranking. No
number on this page is estimated. An earlier run the same day, with the same
embedding model served through OpenRouter, gave near-identical numbers
(`evals/results/2026-10-15-full-*`).

**Key findings**

- **Reranking is the biggest win.** MRR@20 goes from 0.625 (hybrid) to 0.782, and the
  top result is relevant for 74% of questions instead of 53%.
- **Hybrid does not beat dense-only yet.** Dense-only Recall@10 is 0.849, hybrid is
  0.768. With equal RRF weights, keyword hits push some good vector hits out of the top
  10. Down-weighting the lexical arm is the next experiment.
- **Every citation is valid** (100%), and all 38 answerable questions got an answer,
  29 judged correct and 3 partly correct.
- **Abstention mostly happens in prose.** 5 of 6 unanswerable questions got an answer
  saying the chat doesn't contain it, but only 1 took the formal "I couldn't verify"
  path.

## What is measured

Script: `scripts/run_eval.py`. It calls the production functions in
`src/recallhq/retrieval/service.py` (`retrieve`, `rerank`, `answer`) and wraps the
OpenAI and OpenRouter clients only to record token usage, the raw model output and
which rerank model answered. It does not change ranking or answering.

Retrieval configurations:

| Config | What runs |
| --- | --- |
| a) dense-only | `retrieve(q, limit=20, mode="dense")`: pgvector cosine top 30 chunks, no lexical arm |
| b) lexical-only | `retrieve(q, limit=20, mode="lexical")`: `ts_rank` top 30 chunks over the query's content words joined with OR (`lexical_query`), no embedding call |
| c) hybrid RRF | `retrieve(q, limit=20)`: production default, both arms fused with `score += 1/(rank+10)` |
| d) hybrid + rerank | `rerank(q, retrieve(q, limit=20))`: production Decisions API rerank of the top 10 (Jev 1.13, then GPT-6 Luna Decisions, then plain RRF order) |

`mode` is a keyword argument added to `retrieve` for this evaluation. Its default,
`"hybrid"`, is the unchanged production behaviour. In a and b, chunk scores are still
summed per message with `1/(rank+10)`, so a message that appears in both its own
chunk and a thread chunk is ranked the same way production would rank it.

The questions are sent exactly as `/ask` sends them: the query text only, with no
date or channel filters applied, even for the "filtered", "as_of" and "catch_up"
queries whose YAML has `filters`. This matches the current `/ask` endpoint, which
does not parse filters out of the question.

End-to-end (config d only): the top 12 messages of the reranked list go to
`answer()`. This is the same evidence `/ask` uses (`rerank(retrieve(q, limit=12))`
reranks the same top 10 and keeps the same two RRF hits after them).

## Dataset

- Corpus: `data/synthetic/corpus.jsonl`, 2,233 synthetic Slack-style messages from a
  fictional student team ("Beacon") across 5 channels. Ingest produces 2,233 message
  chunks and 158 thread chunks.
- Queries: `evals/queries.yaml`, 44 hand-designed questions. 38 are answerable and 6
  are unanswerable (nothing in the corpus answers them). Split: dev 23 (20 answerable,
  3 unanswerable), test 21 (18 answerable, 3 unanswerable).
- Each answerable query lists `evidence_groups`. A group is one part of the answer
  (for example "who owns it" and "when is it due") with every message that was
  verified to support that part. There are 68 groups in total (dev 41, test 27).
- Each query also has a graded `relevant` map (grade 1 to 3). Every evidence-group
  message is in it; grade 1 messages mention the topic but were not verified as
  supporting the claim.
- `uv run python scripts/validate_queries.py` checks the set (it reports "Valid: 44
  queries").

## Metric definitions

Only the 38 answerable queries are scored for retrieval. Latency is timed on all 44.

- **Recall@k (query-averaged).** For each query, the share of its evidence groups
  with at least one message in the top k retrieved messages. Then the mean over
  queries. A query with 3 groups and 2 hit scores 0.667.
- **Group recall@k (micro).** Groups hit in the top k, divided by all 68 groups.
  Queries with more parts weigh more.
- **Full coverage@k.** Share of queries where every group is hit in the top k.
- **MRR@20.** For each query, 1 / rank of the first retrieved message that is in any
  of its evidence groups, or 0 if none is in the top 20. Then the mean.
- **Latency.** Wall-clock time of the retrieval call (and the rerank call for d), in
  milliseconds, p50 and p95 with linear interpolation. It includes the query
  embedding request to OpenAI for a, c and d and the Decisions request for d. The
  database is local Docker Postgres, so database time is lower than in production.
- **Rerank usage.** Per query, whether Jev answered ("primary"), the fallback model
  answered ("fallback"), both failed and RRF order was kept, or reranking was off.

Reranking only reorders the top 10, so Recall@10 and Recall@20 are identical for c
and d by construction. Rerank changes MRR, hit@1 and Recall@5. The summary JSON also
reports Recall@5 and Recall@12 (12 is what the LLM sees).

End-to-end metrics (config d):

- **Citation validity rate.** Share of LLM outputs whose cited IDs (`[synthetic:...]`)
  are all in the 12 evidence messages it was given. Invalid outputs are replaced by
  "I couldn't verify an answer" in production.
- **Answer rate (answerable).** Share of the 38 answerable questions where the final
  response has at least one verified source.
- **Correct abstention rate (unanswerable).** Share of the 6 unanswerable questions
  where the final response has no sources (the model declined, or verification
  failed).
- **Citation precision (strict).** Over answered questions, cited message IDs that
  are in that query's evidence groups, divided by all cited IDs (micro), and the
  per-answer mean (macro). A lenient variant counts any ID in the `relevant` map.
- **LLM-judged correctness (optional).** `gpt-5.4-mini` compares the final answer
  with the reference `answer`: correct = 1, partially correct = 0.5, incorrect = 0.
  The judge does not see the evidence. This is an LLM opinion, not a human grade.

## Results

### Retrieval, all 38 answerable queries (latency over 44)

| Config | Recall@10 | Recall@20 | MRR@20 | Hit@1 | p50 ms | p95 ms |
| --- | --- | --- | --- | --- | --- | --- |
| a) dense-only | **0.849** | **0.882** | 0.657 | 0.579 | 637 | 1188 |
| b) lexical-only | 0.616 | 0.675 | 0.460 | 0.342 | 16 | 22 |
| b) lexical-only, before fix | 0.000 | 0.000 | 0.000 | 0.000 | 13 | 17 |
| c) hybrid RRF | 0.768 | 0.829 | 0.625 | 0.526 | 617 | 740 |
| d) hybrid + rerank (production) | 0.768 | 0.829 | **0.782** | **0.737** | 1425 | 2444 |

Latency includes the query-embedding API call (dense, hybrid, rerank) and the
Decisions API call (rerank).

### By split

| Config | Split | Queries | Recall@10 | Recall@20 | MRR@20 |
| --- | --- | --- | --- | --- | --- |
| a) dense-only | dev | 20 | 0.838 | 0.875 | 0.614 |
| a) dense-only | test | 18 | 0.861 | 0.889 | 0.706 |
| b) lexical-only | dev | 20 | 0.596 | 0.608 | 0.540 |
| b) lexical-only | test | 18 | 0.639 | 0.750 | 0.372 |
| c) hybrid RRF | dev | 20 | 0.733 | 0.775 | 0.681 |
| c) hybrid RRF | test | 18 | 0.806 | 0.889 | 0.564 |
| d) hybrid + rerank | dev | 20 | 0.733 | 0.775 | 0.757 |
| d) hybrid + rerank | test | 18 | 0.806 | 0.889 | 0.809 |

Raw rows: `evals/results/2026-10-15-openai-retrieval.jsonl`. Summary:
`evals/results/2026-10-15-openai-summary.json`. The before-fix lexical run is kept in
`evals/results/2026-10-14-lexical-only-*`.

### Fixed: the lexical arm used to return nothing

Before 2026-10-15 the lexical arm returned **zero chunks for all 44 questions**. The query
went through `websearch_to_tsquery('simple', q)`, which joins every word with AND and keeps
stop words, so "Which command fixed the local 28P01 Postgres failure?" required a chunk to
contain "which", "the" and every other word. No chat message does. In effect, production
"hybrid" retrieval ranked exactly like dense-only.

The fix (`lexical_query` in `src/recallhq/retrieval/service.py`) drops common English stop
words and ORs the remaining terms (`command | fixed | local | 28p01 | postgres | failure`);
`ts_rank` still ranks chunks that match more terms higher. Lexical-only Recall@10 went from
0.000 to 0.616 on the same 38 answerable questions, with no API calls.

### Rerank usage

Jev 1.13 answered all 44 rerank requests. The GPT-6 Luna fallback and the plain RRF
path were never used. Total Decisions API cost for the run: about $0.004.

### End-to-end answers (config d)

| Metric | All | Dev | Test |
| --- | --- | --- | --- |
| Citation validity rate | 1.000 | 1.000 | 1.000 |
| Answer rate, answerable | 1.000 | 1.000 | 1.000 |
| Correct abstention, unanswerable (strict: formal "couldn't verify") | 0.167 | 0.333 | 0.000 |
| Unanswerable handled correctly (LLM-judged: says it's not in the chat) | 0.833 | 0.667 | 1.000 |
| Citation precision, strict (micro) | 0.574 | 0.630 | 0.521 |
| Citation precision, strict (macro) | 0.653 | 0.683 | 0.619 |
| Citation precision, lenient (micro) | 0.734 | 0.783 | 0.688 |
| Answers with at least one gold citation | 0.789 | 0.800 | 0.778 |
| LLM-judged correctness, answerable (mean score) | 0.803 | 0.825 | 0.778 |
| LLM judge: correct / partial / incorrect | 29 / 3 / 6 | 15 / 3 / 2 | 14 / 0 / 4 |
| Answer latency p50 / p95 (ms) | 1540 / 2662 | 1581 / 2445 | 1522 / 3034 |

Raw rows: `evals/results/2026-10-15-openai-e2e.jsonl`. The LLM judge is
`gpt-5.4-mini`, the same model that writes the answers, so treat its scores as a rough
signal, not ground truth.

## Limitations

- The data is synthetic: one fictional team, 2,233 messages, written by an LLM from a
  planted fact list. Real Slack history is messier, larger and more varied.
- 44 queries (38 answerable, 6 unanswerable) is small. One query moves Recall by about
  2.6 points overall and by 5 points within the 20-query dev split. The 6
  unanswerable questions give a very coarse abstention rate.
- The queries and gold evidence were written by the same project that built the
  system, and the dev split was available while the pipeline was being built. The
  test split is the fairer number, but it is not a blind benchmark.
- Gold evidence was verified with `gpt-5.4-mini` (`scripts/verify_query_refs.py`), so
  labels can contain model errors.
- Generation and reranking are remote LLM calls and are not deterministic. A single run
  is reported; repeated runs can differ slightly.
- The LLM judge uses the same model family as the generator and does not see the
  evidence. Treat its score as a rough signal, not as accuracy.
- Latency is measured from one laptop against local Docker Postgres and remote APIs.
  It mostly reflects network and API time and will differ in deployment.
- Filters in the YAML are not applied, matching `/ask` today. Filtered and date-bound
  questions therefore test whether retrieval finds the right period from text alone.

## Reproduce

```bash
docker compose up -d db
uv run python -m recallhq.cli migrate
uv run python -m recallhq.cli ingest data/synthetic/corpus.jsonl   # re-uses stored embeddings
uv run python scripts/validate_queries.py

# Full run: 4 retrieval configs, end-to-end answers, LLM judge.
# Needs OPENAI_API_KEY with access to text-embedding-3-small and gpt-5.4-mini
# (or --embed-provider openrouter for query embeddings),
# and OPEN_ROUTER for reranking.
uv run python scripts/run_eval.py

# Cheaper variants
uv run python scripts/run_eval.py --no-judge               # skip the LLM judge
uv run python scripts/run_eval.py --no-e2e                 # retrieval only
uv run python scripts/run_eval.py --configs lexical --no-e2e --stamp 2026-10-15-lexical-fixed   # no API calls

# Tests (41 with the database integration tests, which create and drop their own database)
RECALLHQ_TEST_DATABASE_URL=postgresql://recallhq:recallhq@localhost:5432/recallhq uv run pytest -q
```

Outputs go to `evals/results/<stamp>-retrieval.jsonl` (one row per query and config,
with the ranked IDs), `<stamp>-e2e.jsonl` (raw model output, citations, status and
judge verdict per query) and `<stamp>-summary.json` (all metrics, per split, plus
token usage). `<stamp>` defaults to today's date.

`--embed-provider openrouter` fetches query embeddings for the same model
(`openai/text-embedding-3-small`) through OpenRouter instead of OpenAI. It is off by
default, differs from production, and was not used for any number on this page. In a
one-off check, OpenRouter vectors for 20 stored chunks had cosine similarity 0.9998 on
average (minimum 0.9970) with the vectors written at ingest. If you use it, record
that in the results, and note that latency then includes OpenRouter instead of OpenAI.

A full run makes about 44 x 3 embedding calls (a few thousand tokens), 44 Decisions
calls (about 2,300 input tokens each in a smoke test), 44 generation calls and 44
judge calls. Token counts are written to the summary under `usage`.
