import { Database } from 'lucide-react';
import type { CSSProperties, ReactNode } from 'react';

import styles from './site.module.css';

type Step = { kicker: string; title: string; body: ReactNode; accent?: boolean; extra?: ReactNode };

function Flow({ steps, columns, columnsMd = 3 }: { steps: Step[]; columns?: number; columnsMd?: number }) {
  const style = { '--steps': columns ?? steps.length, '--steps-md': columnsMd } as CSSProperties;
  return (
    <ol className={styles.flow} style={style} data-wrap={columns && columns < steps.length ? '' : undefined}>
      {steps.map((step) => (
        <li key={step.title} className={styles.flowStep} data-accent={step.accent ? '' : undefined}>
          <span className={styles.flowKicker}>{step.kicker}</span>
          <h3>{step.title}</h3>
          <p>{step.body}</p>
          {step.extra}
        </li>
      ))}
    </ol>
  );
}

/** Five-step overview used on the home page and the docs overview. */
export function HowItWorks({ columns, columnsMd }: { columns?: number; columnsMd?: number }) {
  return (
    <Flow
      columns={columns}
      columnsMd={columnsMd}
      steps={[
        {
          kicker: '01 · Capture',
          title: 'Invite the bot',
          body: 'RecallHQ imports the channel history Slack exposes, then follows new messages, edits, and deletions.',
        },
        {
          kicker: '02 · Index',
          title: 'Chunk by thread',
          body: 'Each message, and each thread in pieces of up to 600 tokens, gets an embedding and a full-text index.',
        },
        {
          kicker: '03 · Retrieve',
          title: 'Two searches, fused',
          body: 'Vector and keyword search return 30 chunks each. Reciprocal rank fusion merges them.',
        },
        {
          kicker: '04 · Rerank',
          title: 'Judge relevance',
          body: 'A decision model scores the top 10 messages for how well each one answers your question.',
        },
        {
          kicker: '05 · Answer',
          title: 'Cite or stay quiet',
          body: 'The answer must cite message IDs from the evidence. If a citation doesn’t check out, no answer is shown.',
          accent: true,
        },
      ]}
    />
  );
}

/** Ingestion lane, shared store, and query lane, as implemented in src/recallhq. */
export function ArchitectureDiagram() {
  return (
    <figure className={styles.diagram} aria-label="RecallHQ ingestion and query pipeline">
      <div className={styles.flowLane}>
        <div className={styles.flowLaneHead}>
          <strong>Ingestion</strong>
          <span>Slack worker · background jobs</span>
        </div>
        <Flow
          columnsMd={2}
          steps={[
            {
              kicker: 'Source',
              title: 'Slack events & history',
              body: 'Live events, plus paged conversations.history and conversations.replies imports.',
            },
            {
              kicker: 'Normalize',
              title: 'Clean messages',
              body: 'Skip RecallHQ’s own posts and system events. Keep thread root and revision.',
            },
            {
              kicker: 'Chunk',
              title: 'Thread-aware chunks',
              body: (
                <>
                  One chunk per message, plus thread chunks of ≤600 tokens (<code>o200k_base</code>).
                </>
              ),
            },
            {
              kicker: 'Embed',
              title: 'text-embedding-3-small',
              body: '1536-dimension vectors. Only chunks whose text changed are re-embedded.',
            },
          ]}
        />
      </div>
      <div className={styles.flowStore}>
        <Database size={18} aria-hidden="true" />
        <span>
          <strong>Postgres</strong> · chunks with <code>vector(1536)</code> and a <code>tsvector(&apos;simple&apos;)</code> · row-level
          security per workspace and channel
        </span>
      </div>
      <div className={styles.flowLane}>
        <div className={styles.flowLaneHead}>
          <strong>Query</strong>
          <span>/recall ask · /ask on the demo</span>
        </div>
        <Flow
          columnsMd={2}
          steps={[
            {
              kicker: 'Retrieve',
              title: 'Hybrid search',
              body: 'Both arms run inside the requester’s allowed channels.',
              extra: (
                <div className={styles.flowSplit}>
                  <div>
                    <strong>Dense</strong>
                    pgvector cosine, top 30
                  </div>
                  <div>
                    <strong>Lexical</strong>
                    content words ORed, ts_rank top 30
                  </div>
                </div>
              ),
            },
            {
              kicker: 'Fuse',
              title: 'Reciprocal rank fusion',
              body: (
                <>
                  Each chunk adds <code>1/(rank+10)</code> to every message it contains. Top 12 messages survive.
                </>
              ),
            },
            {
              kicker: 'Rerank',
              title: 'Decisions API, top 10',
              body: 'Jev 1.13, then GPT-6 Luna Decisions, else RRF order. 4-level relevance rubric.',
            },
            {
              kicker: 'Generate',
              title: 'gpt-5.4-mini',
              body: 'Answers only from the 12 evidence messages and cites each claim with [message-id].',
            },
            {
              kicker: 'Verify',
              title: 'Check citations',
              body: 'Every cited ID must be in the evidence.',
              accent: true,
              extra: (
                <div className={styles.flowOutcome}>
                  <span>✓ Answer + source links</span>
                  <span>✗ “I couldn’t verify an answer”</span>
                </div>
              ),
            },
          ]}
        />
      </div>
      <figcaption>Ingestion writes chunks; queries read them through a separate, read-only database role.</figcaption>
    </figure>
  );
}

/** How the HTTP API and the worker split Slack work. */
export function SystemDiagram() {
  return (
    <figure className={styles.diagram} aria-label="Slack API and worker split">
      <div className={styles.system}>
        <div className={styles.systemNode}>
          <span className={styles.flowKicker}>Slack</span>
          <h3>Workspaces</h3>
          <ul>
            <li>Message and channel events</li>
            <li>
              <code>/recall</code> slash commands
            </li>
            <li>OAuth installs</li>
          </ul>
        </div>
        <div className={styles.systemNode}>
          <span className={styles.flowKicker}>API · FastAPI</span>
          <h3>Verify, persist, acknowledge</h3>
          <ul>
            <li>Checks Slack’s request signature</li>
            <li>Writes a deduplicated job row, then replies “working on it”</li>
            <li>Never calls a model while Slack waits</li>
          </ul>
        </div>
        <div className={styles.systemNode} data-accent="">
          <span className={styles.flowKicker}>Worker · 3 lanes</span>
          <h3>Durable jobs</h3>
          <ul>
            <li>
              <strong>Ingestion:</strong> events, history, replies, deletions
            </li>
            <li>
              <strong>Commands:</strong> retrieve, rerank, answer, deliver
            </li>
            <li>
              <strong>Embeddings:</strong> fill the vector backlog
            </li>
          </ul>
        </div>
        <div className={styles.systemStack}>
          <div className={styles.systemNode}>
            <span className={styles.flowKicker}>Storage</span>
            <h3>Postgres + pgvector</h3>
            <p>Messages, chunks, jobs, encrypted installs.</p>
          </div>
          <div className={styles.systemNode}>
            <span className={styles.flowKicker}>Models</span>
            <h3>OpenAI · OpenRouter</h3>
            <p>Embeddings and answers; Decisions API reranking.</p>
          </div>
        </div>
      </div>
      <figcaption>Commands, embeddings, and ingestion run in separate lanes, so a slow model call never delays a deletion.</figcaption>
    </figure>
  );
}
