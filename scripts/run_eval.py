"""Retrieval and end-to-end evaluation on evals/queries.yaml.

Retrieval configs (all use production `retrieve`/`rerank` from recallhq.retrieval.service):
  dense    - semantic arm only (pgvector cosine top 30)
  lexical  - lexical arm only (tsvector ts_rank top 30)
  hybrid   - production RRF of both arms
  rerank   - hybrid + production Decisions API rerank of the top 10 (Jev, then fallback)

End-to-end (config "rerank", exactly as /ask): evidence = top 12, then `answer()`.
Optional LLM judge (gpt-5.4-mini) compares the final answer with the reference answer.

Usage:
  uv run python scripts/run_eval.py                 # retrieval + end-to-end + judge
  uv run python scripts/run_eval.py --embed-provider openrouter   # query embeddings via OpenRouter (same model)
  uv run python scripts/run_eval.py --no-e2e        # retrieval only (embeddings + rerank calls)
  uv run python scripts/run_eval.py --no-judge      # skip the LLM judge
Writes evals/results/<date>-retrieval.jsonl, <date>-e2e.jsonl and <date>-summary.json.
"""

import argparse
import io
import json
import re
import statistics
import sys
import time
import urllib.request
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import yaml
from openai import OpenAI

from recallhq.retrieval import service

ROOT = Path(__file__).resolve().parents[1]
QUERIES = ROOT / "evals/queries.yaml"
CONFIGS = ("dense", "lexical", "hybrid", "rerank")
DEPTH = 20  # ranked list depth used for Recall@20 and MRR
EVIDENCE_K = 12  # messages /ask passes to the LLM
KS = (5, 10, 12, 20)
CITATION = re.compile(r"\[((?:slack|synthetic):[^\[\]\s]+)\]")  # same pattern as service.answer
JUDGE_MODEL = "gpt-5.4-mini"

# ---------------------------------------------------------------- instrumentation
USAGE = {"embedding_tokens": 0, "embedding_calls": 0, "generation_input_tokens": 0, "generation_output_tokens": 0,
         "generation_reasoning_tokens": 0, "generation_calls": 0, "judge_input_tokens": 0, "judge_output_tokens": 0,
         "judge_calls": 0, "decisions_calls": 0, "decisions_usage": []}
RAW_GENERATIONS: list[str] = []
RERANK_EVENTS: list[dict] = []
_RealOpenAI = service.OpenAI
EMBED = {"provider": "openai"}


class TrackedOpenAI:
    """Wraps the OpenAI client used inside service.py to record token usage and raw model output."""

    def __init__(self, *args, **kwargs):
        self._client = _RealOpenAI(*args, **kwargs)
        self.embeddings = SimpleNamespace(create=self._embed)
        self.responses = SimpleNamespace(create=self._respond)

    def _embed(self, **kwargs):
        if EMBED["provider"] == "openrouter":
            response = openrouter_client().embeddings.create(**{**kwargs, "model": f"openai/{kwargs['model']}"})
        else:
            response = self._client.embeddings.create(**kwargs)
        USAGE["embedding_calls"] += 1
        USAGE["embedding_tokens"] += response.usage.total_tokens
        return response

    def _respond(self, **kwargs):
        response = self._client.responses.create(**kwargs)
        USAGE["generation_calls"] += 1
        USAGE["generation_input_tokens"] += response.usage.input_tokens
        USAGE["generation_output_tokens"] += response.usage.output_tokens
        details = getattr(response.usage, "output_tokens_details", None)
        USAGE["generation_reasoning_tokens"] += getattr(details, "reasoning_tokens", 0) or 0
        RAW_GENERATIONS.append(response.output_text)
        return response


def openrouter_client() -> OpenAI:
    """Same OpenAI embedding model served through OpenRouter; used only with --embed-provider openrouter."""
    if "client" not in EMBED:
        EMBED["client"] = _RealOpenAI(api_key=service.SETTINGS.open_router, base_url="https://openrouter.ai/api/v1",
                                      timeout=20, max_retries=0)
    return EMBED["client"]


def check_embedding_equivalence(sample: int = 20) -> dict:
    """Re-embed stored chunks through OpenRouter and compare with the vectors written at ingest (OpenAI direct)."""
    with service.db() as conn:
        rows = conn.execute("SELECT id, text, embedding::text AS vector FROM chunks WHERE embedding IS NOT NULL "
                            "ORDER BY md5(id) LIMIT %s", (sample,)).fetchall()
    response = openrouter_client().embeddings.create(model=f"openai/{service.SETTINGS.embedding_model}",
                                                     dimensions=service.SETTINGS.embedding_dimension,
                                                     encoding_format="float", input=[row["text"] for row in rows])
    USAGE["embedding_calls"] += 1
    USAGE["embedding_tokens"] += response.usage.total_tokens
    cosines = []
    for row, item in zip(rows, response.data):
        stored, fresh = json.loads(row["vector"]), item.embedding
        dot = sum(a * b for a, b in zip(stored, fresh))
        cosines.append(dot / (sum(a * a for a in stored) ** 0.5 * sum(b * b for b in fresh) ** 0.5))
    return {"chunks_compared": len(cosines), "min_cosine": round(min(cosines), 6), "mean_cosine": round(statistics.mean(cosines), 6)}


_real_decide = service.decide_scores
_real_urlopen = urllib.request.urlopen


def tracked_decide(model, state, questions):
    started = time.perf_counter()
    try:
        scores, served_by = _real_decide(model, state, questions)
    except Exception as error:  # recorded, then re-raised so production fallback logic runs unchanged
        RERANK_EVENTS.append({"model": model, "ok": False, "error": f"{type(error).__name__}: {error}"[:300],
                              "ms": round((time.perf_counter() - started) * 1000, 1)})
        raise
    RERANK_EVENTS.append({"model": model, "ok": True, "served_by": served_by,
                          "ms": round((time.perf_counter() - started) * 1000, 1)})
    return scores, served_by


def tracked_urlopen(request, *args, **kwargs):
    """Only service.decide_scores uses urllib; capture the Decisions response's usage block if present."""
    with _real_urlopen(request, *args, **kwargs) as response:
        raw = response.read()
    USAGE["decisions_calls"] += 1
    try:
        usage = json.loads(raw).get("usage")
        if usage:
            USAGE["decisions_usage"].append(usage)
    except (ValueError, AttributeError):
        pass
    return io.BytesIO(raw)


service.OpenAI = TrackedOpenAI
service.decide_scores = tracked_decide
urllib.request.urlopen = tracked_urlopen


# ---------------------------------------------------------------- metrics
def group_hits(ranked: list[str], groups: list[list[str]], k: int) -> list[bool]:
    top = set(ranked[:k])
    return [bool(top & set(group)) for group in groups]


def first_relevant_rank(ranked: list[str], gold: set[str]) -> int | None:
    return next((i + 1 for i, mid in enumerate(ranked[:DEPTH]) if mid in gold), None)


def percentile(values: list[float], pct: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return float("nan")
    index = (len(ordered) - 1) * pct / 100  # linear interpolation (numpy default)
    low, high = int(index), min(int(index) + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (index - low)


def r4(value):
    return None if value is None else round(value, 4)


def summarize_retrieval(rows: list[dict]) -> dict:
    scored = [row for row in rows if row["answerable"]]
    out = {"queries_scored": len(scored), "queries_timed": len(rows), "groups": sum(row["n_groups"] for row in scored)}
    for k in KS:
        out[f"recall@{k}"] = r4(statistics.mean(row[f"recall@{k}"] for row in scored))
        out[f"group_recall_micro@{k}"] = r4(sum(row[f"groups_hit@{k}"] for row in scored) / out["groups"])
        out[f"full_coverage@{k}"] = r4(statistics.mean(row[f"recall@{k}"] == 1.0 for row in scored))
    out["mrr@20"] = r4(statistics.mean(row["rr"] for row in scored))
    out["hit@1"] = r4(statistics.mean(row["rr"] == 1.0 for row in scored))
    latencies = [row["latency_ms"] for row in rows]
    out["latency_ms_p50"] = round(percentile(latencies, 50), 1)
    out["latency_ms_p95"] = round(percentile(latencies, 95), 1)
    out["latency_ms_mean"] = round(statistics.mean(latencies), 1)
    return out


# ---------------------------------------------------------------- runs
def run_config(config: str, query: str) -> tuple[list[dict], float, list[dict]]:
    RERANK_EVENTS.clear()
    started = time.perf_counter()
    if config == "rerank":
        hits = service.rerank(query, service.retrieve(query, limit=DEPTH))
    else:
        hits = service.retrieve(query, limit=DEPTH, mode=config)
    return hits, (time.perf_counter() - started) * 1000, list(RERANK_EVENTS)


def rerank_status(events: list[dict]) -> str:
    if not service.SETTINGS.open_router:
        return "disabled_no_key"
    if not events:
        return "skipped_fewer_than_2_hits"
    if events[0]["ok"]:
        return "primary"
    if len(events) > 1 and events[1]["ok"]:
        return "fallback"
    return "rrf_order_both_failed"


def retrieval_stage(queries: list[dict], stamp: str, out_dir: Path, configs: tuple[str, ...]) -> tuple[dict, dict]:
    for mode in [c for c in configs if c != "rerank"] or ["hybrid"]:  # warm-up: connection setup, HTTP keep-alive caches, PG buffers
        service.retrieve("warm up query", limit=DEPTH, mode=mode)
    rows, rerank_lists = [], {}
    for query in queries:
        groups = [group["message_ids"] for group in query["evidence_groups"]]
        gold = {mid for group in groups for mid in group}
        for config in configs:
            hits, latency, events = run_config(config, query["query"])
            ranked = [hit["id"] for hit in hits]
            row = {"id": query["id"], "split": query["split"], "type": query["type"], "answerable": query["answerable"],
                   "config": config, "latency_ms": round(latency, 1), "n_groups": len(groups), "ranked": ranked}
            if query["answerable"]:
                for k in KS:
                    hit = group_hits(ranked, groups, k)
                    row[f"groups_hit@{k}"] = sum(hit)
                    row[f"recall@{k}"] = sum(hit) / len(hit)
                rank = first_relevant_rank(ranked, gold)
                row["first_relevant_rank"] = rank
                row["rr"] = 1 / rank if rank else 0.0
            if config == "rerank":
                row["rerank_status"] = rerank_status(events)
                row["rerank_calls"] = events
                rerank_lists[query["id"]] = hits
            rows.append(row)
        print(f"retrieval {query['id']} done", file=sys.stderr, flush=True)
    with (out_dir / f"{stamp}-retrieval.jsonl").open("w") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")
    summary = {}
    for config in configs:
        summary[config] = {}
        for split in ("all", "dev", "test"):
            subset = [row for row in rows if row["config"] == config and (split == "all" or row["split"] == split)]
            summary[config][split] = summarize_retrieval(subset)
    statuses = [row["rerank_status"] for row in rows if row["config"] == "rerank"]
    if "rerank" in configs:
        summary["rerank_usage"] = {status: statuses.count(status) for status in sorted(set(statuses))}
        summary["rerank_usage"]["total_queries"] = len(statuses)
    return summary, rerank_lists


def judge(client: OpenAI, query: dict, final_answer: str) -> dict:
    reference = query["answer"] if query["answerable"] else (
        "The chat history does not contain this information. The correct behaviour is to say it cannot be answered "
        "from the available messages, without inventing an answer.")
    schema = {"type": "object", "additionalProperties": False, "required": ["verdict", "abstained", "reason"],
              "properties": {"verdict": {"type": "string", "enum": ["correct", "partially_correct", "incorrect"]},
                             "abstained": {"type": "boolean"}, "reason": {"type": "string"}}}
    response = client.responses.create(
        model=JUDGE_MODEL,
        instructions=("You grade a question-answering system against a reference answer. "
                      "verdict=correct if the system answer conveys all key facts of the reference and contradicts none; "
                      "partially_correct if it conveys some key facts and contradicts none; otherwise incorrect. "
                      "Extra correct detail and citation markers like [synthetic:...] are fine. "
                      "abstained=true if the system answer declines or says it could not find/verify an answer. "
                      "If the reference says the information is absent, an abstention is correct and any invented answer is incorrect. "
                      "Reply in one short sentence of reason."),
        input=f"Question: {query['query']}\n\nReference answer: {reference}\n\nSystem answer: {final_answer}",
        text={"format": {"type": "json_schema", "name": "grade", "schema": schema, "strict": True}},
    )
    USAGE["judge_calls"] += 1
    USAGE["judge_input_tokens"] += response.usage.input_tokens
    USAGE["judge_output_tokens"] += response.usage.output_tokens
    return json.loads(response.output_text)


def e2e_stage(queries: list[dict], rerank_lists: dict, stamp: str, out_dir: Path, use_judge: bool) -> dict:
    judge_client = OpenAI(api_key=service.SETTINGS.openai_api_key, timeout=60, max_retries=1) if use_judge else None
    rows = []
    for query in queries:
        evidence = rerank_lists[query["id"]][:EVIDENCE_K]  # identical to rerank(retrieve(q, limit=12)) in /ask
        before = len(RAW_GENERATIONS)
        started = time.perf_counter()
        result = service.answer(query["query"], evidence)
        latency = (time.perf_counter() - started) * 1000
        raw = RAW_GENERATIONS[before] if len(RAW_GENERATIONS) > before else None
        evidence_ids = {row["id"] for row in evidence}
        raw_cited = sorted(set(CITATION.findall(raw))) if raw is not None else []
        sources = [row["id"] for row in result["sources"]]
        if not evidence:
            status = "no_evidence"
        elif sources:
            status = "answered"
        elif result["answer"].startswith("I couldn't verify"):
            status = "verification_failed"
        else:
            status = "declined"  # model said it couldn't find / not enough, without citations
        strict = {mid for group in query["evidence_groups"] for mid in group["message_ids"]}
        lenient = set(query.get("relevant") or {})
        row = {"id": query["id"], "split": query["split"], "type": query["type"], "answerable": query["answerable"],
               "question": query["query"], "reference_answer": query["answer"], "evidence_ids": [r["id"] for r in evidence],
               "raw_output": raw, "raw_cited": raw_cited, "raw_citations_valid": set(raw_cited) <= evidence_ids,
               "final_answer": result["answer"], "cited": sources, "status": status, "answer_latency_ms": round(latency, 1),
               "cited_in_strict_gold": sum(mid in strict for mid in sources),
               "cited_in_lenient_gold": sum(mid in lenient for mid in sources)}
        if judge_client is not None:
            row["judge"] = judge(judge_client, query, result["answer"])
        rows.append(row)
        print(f"e2e {query['id']} {status}", file=sys.stderr, flush=True)
    with (out_dir / f"{stamp}-e2e.jsonl").open("w") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")
    return {split: summarize_e2e([row for row in rows if split == "all" or row["split"] == split], use_judge)
            for split in ("all", "dev", "test")}


def summarize_e2e(rows: list[dict], use_judge: bool) -> dict:
    answerable = [row for row in rows if row["answerable"]]
    unanswerable = [row for row in rows if not row["answerable"]]
    generated = [row for row in rows if row["raw_output"] is not None]
    answered = [row for row in answerable if row["status"] == "answered"]
    cited_total = sum(len(row["cited"]) for row in answered)
    out = {
        "queries": len(rows), "answerable": len(answerable), "unanswerable": len(unanswerable),
        "llm_generations": len(generated),
        "citation_validity_rate": r4(statistics.mean(row["raw_citations_valid"] for row in generated)) if generated else None,
        "verification_failed": sum(row["status"] == "verification_failed" for row in rows),
        "answer_rate_answerable": r4(len(answered) / len(answerable)) if answerable else None,
        "correct_abstention_rate_unanswerable": r4(statistics.mean(row["status"] != "answered" for row in unanswerable)) if unanswerable else None,
        "citations_in_answered": cited_total,
        "citation_precision_strict_micro": r4(sum(row["cited_in_strict_gold"] for row in answered) / cited_total) if cited_total else None,
        "citation_precision_strict_macro": r4(statistics.mean(row["cited_in_strict_gold"] / len(row["cited"]) for row in answered)) if answered else None,
        "citation_precision_lenient_micro": r4(sum(row["cited_in_lenient_gold"] for row in answered) / cited_total) if cited_total else None,
        "answers_with_at_least_one_gold_citation": r4(statistics.mean(row["cited_in_strict_gold"] > 0 for row in answered)) if answered else None,
        "status_counts": {status: sum(row["status"] == status for row in rows) for status in sorted({row["status"] for row in rows})},
        "answer_latency_ms_p50": round(percentile([row["answer_latency_ms"] for row in generated], 50), 1) if generated else None,
        "answer_latency_ms_p95": round(percentile([row["answer_latency_ms"] for row in generated], 95), 1) if generated else None,
    }
    if use_judge:
        points = {"correct": 1.0, "partially_correct": 0.5, "incorrect": 0.0}
        verdicts = [row["judge"]["verdict"] for row in answerable]
        out["llm_judge_answerable"] = {
            "mean_score": r4(statistics.mean(points[v] for v in verdicts)) if verdicts else None,
            "correct": verdicts.count("correct"), "partially_correct": verdicts.count("partially_correct"),
            "incorrect": verdicts.count("incorrect")}
        out["llm_judge_unanswerable_correct"] = sum(row["judge"]["verdict"] == "correct" for row in unanswerable)
        out["llm_judge_abstained_on_answerable"] = sum(row["judge"]["abstained"] for row in answerable)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--configs", default=",".join(CONFIGS),
                        help="comma-separated subset of dense,lexical,hybrid,rerank (end-to-end needs rerank)")
    parser.add_argument("--no-e2e", action="store_true", help="skip answer generation")
    parser.add_argument("--no-judge", action="store_true", help="skip the LLM judge")
    parser.add_argument("--out-dir", type=Path, default=ROOT / "evals/results")
    parser.add_argument("--embed-provider", choices=("openai", "openrouter"), default="openai",
                        help="where query embeddings come from (same model either way); default matches production")
    parser.add_argument("--stamp", default=date.today().isoformat(), help="file name prefix (default: today)")
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    configs = tuple(c for c in CONFIGS if c in args.configs.split(","))
    if not configs:
        parser.error("no valid --configs")
    if "rerank" not in configs:
        args.no_e2e = True
    queries = yaml.safe_load(QUERIES.read_text())["queries"]
    started = time.time()
    EMBED["provider"] = args.embed_provider
    equivalence = check_embedding_equivalence() if args.embed_provider == "openrouter" else None
    retrieval, rerank_lists = retrieval_stage(queries, args.stamp, args.out_dir, configs)
    summary = {"date": args.stamp, "queries": len(queries),
               "models": {"embedding": service.SETTINGS.embedding_model, "generation": service.SETTINGS.generation_model,
                          "rerank": service.SETTINGS.rerank_model, "rerank_fallback": service.SETTINGS.rerank_fallback_model,
                          "judge": None if args.no_judge or args.no_e2e else JUDGE_MODEL},
               "query_embeddings": {"provider": args.embed_provider, "equivalence_check": equivalence},
               "settings": {"configs": list(configs), "depth": DEPTH, "evidence_k": EVIDENCE_K, "rerank_top_k": service.SETTINGS.rerank_top_k,
                            "filters_applied": False},
               "retrieval": retrieval}
    if not args.no_e2e:
        summary["end_to_end"] = e2e_stage(queries, rerank_lists, args.stamp, args.out_dir, not args.no_judge)
    summary["usage"] = USAGE
    summary["wall_clock_s"] = round(time.time() - started, 1)
    (args.out_dir / f"{args.stamp}-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
