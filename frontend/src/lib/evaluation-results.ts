// Evaluation results shown on /docs/evaluation. Source of truth: docs/evaluation.md and evals/results/.
// To update after a new run: replace `null` with the measured value and change EVAL_STATUS.
// `null` renders as "Not yet measured". Never fill a cell with an estimate.

export const EVAL_STATUS = {
  date: '2026-10-15',
  label: 'Partial run',
  summary:
    'Only the lexical-only retrieval configuration has been measured. Dense, hybrid, hybrid + rerank, and the end-to-end answer evaluation need query embeddings and have not been run yet.',
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
    recall10: null,
    recall20: null,
    mrr20: null,
    p50ms: null,
    p95ms: null,
  },
  {
    config: 'b) Lexical-only',
    description: 'ts_rank top 30 chunks over the query’s content words joined with OR',
    recall10: 0.616,
    recall20: 0.675,
    mrr20: 0.46,
    p50ms: 39.3,
    p95ms: 42.7,
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
    recall10: null,
    recall20: null,
    mrr20: null,
    p50ms: null,
    p95ms: null,
  },
  {
    config: 'd) Hybrid + rerank',
    description: 'Decisions API rerank of the top 10 (Jev 1.13 → GPT-6 Luna Decisions → RRF order)',
    recall10: null,
    recall20: null,
    mrr20: null,
    p50ms: null,
    p95ms: null,
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
  { config: 'b) Lexical-only', split: 'dev', queries: 20, recall10: 0.596, recall20: 0.608, mrr20: 0.54, p50ms: 39.8, p95ms: 42.3 },
  { config: 'b) Lexical-only', split: 'test', queries: 18, recall10: 0.639, recall20: 0.75, mrr20: 0.372, p50ms: 38.0, p95ms: 42.7 },
];

export type EndToEndRow = { metric: string; all: Metric; dev: Metric; test: Metric };

export const endToEndResults: EndToEndRow[] = [
  { metric: 'Citation validity rate', all: null, dev: null, test: null },
  { metric: 'Answer rate, answerable', all: null, dev: null, test: null },
  { metric: 'Correct abstention rate, unanswerable', all: null, dev: null, test: null },
  { metric: 'Citation precision, strict (micro)', all: null, dev: null, test: null },
  { metric: 'LLM-judged correctness, answerable', all: null, dev: null, test: null },
];
