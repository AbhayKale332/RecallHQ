import Link from 'next/link';

import styles from '@/components/site.module.css';
import { EVAL_STATUS, type Metric, endToEndResults, retrievalResults, splitResults } from '@/lib/evaluation-results';

import { Code, Note, Table, Toc } from './docs-ui';

function score(value: Metric) {
  return value === null ? <span className={styles.pending}>Not yet measured</span> : value.toFixed(3);
}
function ms(value: Metric) {
  return value === null ? <span className={styles.pending}>Not yet measured</span> : value.toFixed(1);
}

export function EvaluationDoc() {
  const lexical = retrievalResults.find((row) => row.config === 'b) Lexical-only');
  const beforeFix = retrievalResults.find((row) => row.note === 'superseded');
  return (
    <>
      <p>
        <span className={styles.statusBadge}>
          {EVAL_STATUS.label} · {EVAL_STATUS.date}
        </span>
      </p>
      <p>{EVAL_STATUS.summary} No number on this page is estimated.</p>
      <Toc
        items={[
          ['dataset', 'Dataset'],
          ['configs', 'Configurations'],
          ['metrics', 'Metrics'],
          ['results', 'Results'],
          ['lexical-fix', 'Lexical fix'],
          ['limitations', 'Limitations'],
          ['reproduce', 'Reproduce'],
        ]}
      />

      <h2 id="dataset">Dataset</h2>
      <div className={styles.stats}>
        <div className={styles.stat}>
          <b>2,233</b>
          <span>synthetic messages, 5 channels</span>
        </div>
        <div className={styles.stat}>
          <b>44</b>
          <span>hand-labeled queries</span>
        </div>
        <div className={styles.stat}>
          <b>6</b>
          <span>of them unanswerable</span>
        </div>
        <div className={styles.stat}>
          <b>68</b>
          <span>evidence groups</span>
        </div>
      </div>
      <ul>
        <li>
          <strong>Corpus:</strong> <code>data/synthetic/corpus.jsonl</code>, Slack-style messages from a fictional student team (“Beacon”).
          Ingestion produces 2,233 message chunks and 158 thread chunks.
        </li>
        <li>
          <strong>Queries:</strong> <code>evals/queries.yaml</code>. 38 answerable and 6 unanswerable (nothing in the corpus answers them).
          Split into dev (23: 20 answerable, 3 unanswerable) and test (21: 18 answerable, 3 unanswerable).
        </li>
        <li>
          <strong>Evidence groups:</strong> each answerable query lists the parts of its answer (for example “who owns it” and “when is it
          due”), each with every message verified to support that part. 68 groups in total (dev 41, test 27).
        </li>
        <li>
          <strong>Graded relevance:</strong> each query also has a <code>relevant</code> map with grades 1 to 3. Grade 1 messages mention
          the topic but were not verified as supporting the claim.
        </li>
      </ul>

      <h2 id="configs">Configurations</h2>
      <p>
        <code>scripts/run_eval.py</code> calls the production functions in <code>retrieval/service.py</code> (<code>retrieve</code>,{' '}
        <code>rerank</code>, <code>answer</code>). It only wraps the API clients to record token usage, raw output, and which rerank model
        answered. Questions are sent exactly as <code>/ask</code> sends them, with no date or channel filters.
      </p>
      <Table
        head={['Config', 'What runs']}
        rows={[
          ['a) Dense-only', <code key="c">retrieve(q, limit=20, mode=&quot;dense&quot;)</code>],
          ['b) Lexical-only', <code key="c">retrieve(q, limit=20, mode=&quot;lexical&quot;)</code>],
          ['c) Hybrid RRF', <code key="c">retrieve(q, limit=20)</code>],
          ['d) Hybrid + rerank', <code key="c">rerank(q, retrieve(q, limit=20))</code>],
        ]}
      />
      <p>
        In a and b, chunk scores are still summed per message with <code>1/(rank+10)</code>, as in production. End-to-end answers use config
        d: the top 12 reranked messages go to <code>answer()</code>, the same evidence <code>/ask</code> uses.
      </p>

      <h2 id="metrics">Metrics</h2>
      <p>Retrieval is scored on the 38 answerable queries; latency is timed on all 44.</p>
      <Table
        head={['Metric', 'Definition']}
        rows={[
          [
            'Recall@k',
            'Per query, the share of its evidence groups with at least one message in the top k; then the mean over queries. 3 groups with 2 hit scores 0.667.',
          ],
          ['Group recall@k (micro)', 'Groups hit in the top k divided by all 68 groups. Queries with more parts weigh more.'],
          ['Full coverage@k', 'Share of queries where every group is hit in the top k.'],
          ['MRR@20', 'Mean of 1 / rank of the first retrieved message in any evidence group, or 0 if none is in the top 20.'],
          [
            'Latency p50 / p95',
            'Wall-clock time of the retrieval call (plus rerank for d), in ms, with linear interpolation. Includes the query embedding request for a, c, d.',
          ],
          ['Citation validity rate', 'Share of model outputs whose cited IDs are all among the 12 evidence messages.'],
          ['Answer rate', 'Share of the 38 answerable questions whose final response has at least one verified source.'],
          ['Correct abstention rate', 'Share of the 6 unanswerable questions whose final response has no sources.'],
          ['Citation precision', 'Cited IDs that are in the query’s evidence groups, divided by all cited IDs (strict, micro).'],
          [
            'LLM-judged correctness',
            'gpt-5.4-mini compares the answer with the reference: 1, 0.5, or 0. An LLM opinion, not a human grade.',
          ],
        ]}
      />
      <p>Reranking only reorders the top 10, so Recall@10 and Recall@20 are identical for c and d by construction.</p>

      <h2 id="results">Results</h2>
      <h3>Retrieval, 38 answerable queries</h3>
      <Table
        head={['Config', 'Recall@10', 'Recall@20', 'MRR@20', 'p50 ms', 'p95 ms']}
        numeric={[1, 2, 3, 4, 5]}
        rows={retrievalResults.map((row) => [
          <>
            <strong>{row.config}</strong>
            <br />
            <small>{row.description}</small>
          </>,
          score(row.recall10),
          score(row.recall20),
          score(row.mrr20),
          ms(row.p50ms),
          ms(row.p95ms),
        ])}
      />
      <h3>By split</h3>
      <Table
        head={['Config', 'Split', 'Queries', 'Recall@10', 'Recall@20', 'MRR@20', 'p50 ms', 'p95 ms']}
        numeric={[2, 3, 4, 5, 6, 7]}
        rows={[
          ...splitResults.map((row) => [
            row.config,
            row.split,
            row.queries,
            score(row.recall10),
            score(row.recall20),
            score(row.mrr20),
            ms(row.p50ms),
            ms(row.p95ms),
          ]),
          ['a, c, d', 'dev / test', '', score(null), score(null), score(null), ms(null), ms(null)],
        ]}
      />
      <p>
        The test split is the fairer number: the dev split was available while the pipeline was built. Raw rows are in{' '}
        <code>evals/results/2026-10-15-lexical-fixed-retrieval.jsonl</code>.
      </p>
      <h3>End-to-end answers (config d)</h3>
      <Table
        head={['Metric', 'All', 'Dev', 'Test']}
        numeric={[1, 2, 3]}
        rows={endToEndResults.map((row) => [row.metric, score(row.all), score(row.dev), score(row.test)])}
      />
      <p>Rerank usage (how often Jev, the fallback, or plain RRF order was used) has not been measured either.</p>

      <h2 id="lexical-fix">The lexical fix</h2>
      <p>
        Before 2026-10-15 the lexical arm returned <strong>zero chunks for all 44 questions</strong>. The query went through{' '}
        <code>websearch_to_tsquery(&apos;simple&apos;, q)</code>, which joins every word with AND and keeps stop words, so a chunk had to
        contain “which”, “the”, and every other word of the question. In effect, “hybrid” retrieval ranked exactly like dense-only.
      </p>
      <p>
        <code>lexical_query()</code> now drops common English stop words and ORs the remaining terms, while <code>ts_rank</code> still ranks
        chunks that match more terms higher. On the same 38 answerable questions, with no API calls:
      </p>
      <Table
        head={['Lexical-only', 'Recall@10', 'Recall@20', 'MRR@20']}
        numeric={[1, 2, 3]}
        rows={[
          ['Before', score(beforeFix?.recall10 ?? null), score(beforeFix?.recall20 ?? null), score(beforeFix?.mrr20 ?? null)],
          ['After', score(lexical?.recall10 ?? null), score(lexical?.recall20 ?? null), score(lexical?.mrr20 ?? null)],
        ]}
      />
      <p>
        How the two arms are fused is described in <Link href="/docs/architecture#retrieval">Model architecture</Link>.
      </p>

      <h2 id="limitations">Limitations</h2>
      <ul>
        <li>The data is synthetic: one fictional team, written by an LLM from a planted fact list. Real Slack history is messier.</li>
        <li>
          44 queries is small. One query moves Recall by about 2.6 points overall and 5 points within the dev split. Six unanswerable
          questions give a very coarse abstention rate.
        </li>
        <li>The queries and gold evidence were written by the same project that built the system. It is not a blind benchmark.</li>
        <li>Gold evidence was verified with gpt-5.4-mini, so labels can contain model errors.</li>
        <li>Generation and reranking are remote, non-deterministic calls. A single run is reported.</li>
        <li>Latency was measured from one laptop against local Docker Postgres and will differ in deployment.</li>
        <li>Filters in the query file are not applied, matching /ask today.</li>
      </ul>

      <h2 id="reproduce">Reproduce</h2>
      <Code label="Shell">{`docker compose up -d db
uv run python -m recallhq.cli migrate
uv run python -m recallhq.cli ingest data/synthetic/corpus.jsonl
uv run python scripts/validate_queries.py

# Full run: 4 retrieval configs, end-to-end answers, LLM judge
uv run python scripts/run_eval.py

# Cheaper variants
uv run python scripts/run_eval.py --no-judge
uv run python scripts/run_eval.py --no-e2e
uv run python scripts/run_eval.py --configs lexical --no-e2e   # no API calls`}</Code>
      <p>
        A full run needs <code>OPENAI_API_KEY</code> with access to <code>text-embedding-3-small</code> and <code>gpt-5.4-mini</code>, and{' '}
        <code>OPEN_ROUTER</code> for reranking. Outputs go to <code>evals/results/&lt;stamp&gt;-*.jsonl</code> and a summary JSON with all
        metrics and token usage.
      </p>
      <Note>
        Updating this page: edit <code>frontend/src/lib/evaluation-results.ts</code>. Replace a <code>null</code> with the measured value
        from the summary JSON and update the status line. Cells left as <code>null</code> keep showing “Not yet measured”.
      </Note>
    </>
  );
}
