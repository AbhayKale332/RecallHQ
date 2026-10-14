// Evaluation results shown on /docs/evaluation. Source of truth: docs/evaluation.md and evals/results/.
// To update after a new run: replace `null` with the measured value and change EVAL_STATUS.
// `null` renders as "Not yet measured". Never fill a cell with an estimate.

export const EVAL_STATUS = {
  date: '2026-10-15',
  label: 'Full run',
  summary:
    'All four retrieval configurations and the end-to-end answer evaluation were run on 2026-10-15 with OpenAI text-embedding-3-small, gpt-5.4-mini and Jev 1.13 (Jev served all 44 reranks; the fallback was never needed). Raw rows: evals/results/2026-10-15-openai-*.',
};

export type Metric = number | null;

export type RetrievalRow = {
  config: string;
  description: string;
  recall10: Metric;
  recall20: Metric;
  mrr20: Metric;
  p50ms: Metric;
  p95ms: Metric;
  note?: string;
};

export const retrievalResults: RetrievalRow[] = [
  {
    config: 'a) Dense-only',
    description: 'pgvector cosine top 30 chunks, no lexical arm',
    recall10: 0.849,
    recall20: 0.882,
    mrr20: 0.657,
    p50ms: 637.0,
    p95ms: 1188.0,
  },
  {
    config: 'b) Lexical-only',
    description: 'ts_rank top 30 chunks over the query’s content words joined with OR',
    recall10: 0.616,
    recall20: 0.675,
    mrr20: 0.46,
    p50ms: 15.7,
    p95ms: 21.8,
  },
  {
    config: 'b) Lexical-only, before fix',
    description: 'Previous websearch_to_tsquery: every word ANDed, stop words kept',
    recall10: 0,
    recall20: 0,
    mrr20: 0,
    p50ms: 12.9,
    p95ms: 16.5,
    note: 'superseded',
  },
  {
    config: 'c) Hybrid RRF',
    description: 'Production default: both arms fused with score += 1/(rank+10)',
    recall10: 0.768,
    recall20: 0.829,
    mrr20: 0.625,
    p50ms: 617.3,
    p95ms: 740.2,
  },
  {
    config: 'd) Hybrid + rerank',
    description: 'Decisions API rerank of the top 10 (Jev 1.13 → GPT-6 Luna Decisions → RRF order)',
    recall10: 0.768,
    recall20: 0.829,
    mrr20: 0.782,
    p50ms: 1425.0,
    p95ms: 2443.7,
  },
];

export type SplitRow = {
  config: string;
  split: string;
  queries: number;
  recall10: Metric;
  recall20: Metric;
  mrr20: Metric;
  p50ms: Metric;
  p95ms: Metric;
};

export const splitResults: SplitRow[] = [
  { config: 'a) Dense-only', split: 'dev', queries: 20, recall10: 0.838, recall20: 0.875, mrr20: 0.614, p50ms: 623.3, p95ms: 1168.7 },
  { config: 'a) Dense-only', split: 'test', queries: 18, recall10: 0.861, recall20: 0.889, mrr20: 0.706, p50ms: 648.6, p95ms: 1172.8 },
  { config: 'b) Lexical-only', split: 'dev', queries: 20, recall10: 0.596, recall20: 0.608, mrr20: 0.54, p50ms: 16.2, p95ms: 21.8 },
  { config: 'b) Lexical-only', split: 'test', queries: 18, recall10: 0.639, recall20: 0.75, mrr20: 0.372, p50ms: 15.4, p95ms: 19.3 },
  { config: 'c) Hybrid RRF', split: 'dev', queries: 20, recall10: 0.733, recall20: 0.775, mrr20: 0.681, p50ms: 658.7, p95ms: 740.3 },
  { config: 'c) Hybrid RRF', split: 'test', queries: 18, recall10: 0.806, recall20: 0.889, mrr20: 0.564, p50ms: 611.2, p95ms: 710.9 },
  { config: 'd) Hybrid + rerank', split: 'dev', queries: 20, recall10: 0.733, recall20: 0.775, mrr20: 0.757, p50ms: 1445.7, p95ms: 2459.4 },
  { config: 'd) Hybrid + rerank', split: 'test', queries: 18, recall10: 0.806, recall20: 0.889, mrr20: 0.809, p50ms: 1389.4, p95ms: 2127.6 },
];

export type EndToEndRow = { metric: string; all: Metric; dev: Metric; test: Metric };

export const endToEndResults: EndToEndRow[] = [
  { metric: 'Citation validity rate', all: 1.0, dev: 1.0, test: 1.0 },
  { metric: 'Answer rate, answerable', all: 1.0, dev: 1.0, test: 1.0 },
  { metric: 'Correct abstention rate, unanswerable (strict: formal refusal)', all: 0.167, dev: 0.333, test: 0 },
  { metric: 'Unanswerable handled correctly (LLM-judged: says it is not in the chat)', all: 0.833, dev: 0.667, test: 1.0 },
  { metric: 'Citation precision, strict (micro)', all: 0.574, dev: 0.63, test: 0.521 },
  { metric: 'Citation precision, lenient (micro)', all: 0.734, dev: 0.783, test: 0.688 },
  { metric: 'LLM-judged correctness, answerable (mean score)', all: 0.803, dev: 0.825, test: 0.778 },
];
