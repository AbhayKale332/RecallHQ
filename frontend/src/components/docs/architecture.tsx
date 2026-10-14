import Link from 'next/link';

import { ArchitectureDiagram, SystemDiagram } from '@/components/pipeline-diagram';

import { Code, Note, Table, Toc } from './docs-ui';

export function ArchitectureDoc() {
  return (
    <>
      <Toc
        items={[
          ['overview', 'Overview'],
          ['ingestion', 'Ingestion'],
          ['retrieval', 'Retrieval'],
          ['reranking', 'Reranking'],
          ['generation', 'Generation'],
          ['worker', 'API & worker'],
          ['isolation', 'Tenant isolation'],
          ['settings', 'Settings'],
        ]}
      />

      <h2 id="overview">Overview</h2>
      <p>
        RecallHQ is retrieval-augmented generation over chat. A background worker turns Slack messages into chunks with two indexes, a
        vector and a full-text one. A question searches both, fuses the rankings, asks a decision model to rerank the best candidates, and
        lets a language model answer only from that evidence. The answer is shown only if every citation points at a message the model was
        actually given.
      </p>
      <ArchitectureDiagram />
      <p>
        The same <code>retrieve → rerank → answer</code> functions serve the Slack bot and the public demo. The only difference is the query
        context: the demo is pinned to the synthetic Beacon workspace, while a Slack query carries the requester’s workspace and the
        channels they currently belong to.
      </p>

      <h2 id="ingestion">Ingestion</h2>
      <h3>What becomes a chunk</h3>
      <p>
        Each message is rendered with its context, as <code>[#channel · timestamp · author]</code> followed by the text, and becomes a{' '}
        <strong>message chunk</strong>. Each thread also becomes one or more <strong>thread chunks</strong>: the root message followed by
        its replies in time order.
      </p>
      <ul>
        <li>
          Thread chunks are capped at <strong>600 tokens</strong>, counted with tiktoken’s <code>o200k_base</code> encoding.
        </li>
        <li>
          When a thread crosses the limit, the next chunk starts again with the root and the previous reply, so every piece keeps the
          question it is answering. If even that cannot fit, the piece restarts from the root alone.
        </li>
        <li>For Slack content, any single chunk that is still over 600 tokens is split into 600-token pieces.</li>
        <li>
          Chunk IDs are a hash of the chunker version, kind, and message IDs, so re-running ingestion is idempotent and only changed text is
          re-embedded.
        </li>
      </ul>
      <h3>Two indexes per chunk</h3>
      <Table
        head={['Index', 'How', 'Used for']}
        rows={[
          [
            'Dense vector',
            <>
              OpenAI <code>text-embedding-3-small</code>, 1536 dimensions, stored in a pgvector <code>vector(1536)</code> column
            </>,
            'Paraphrases and questions that don’t share words with the answer',
          ],
          [
            'Full text',
            <>
              Generated column <code>to_tsvector(&apos;simple&apos;, text)</code> with a GIN index
            </>,
            'Exact terms: error codes, commands, names, dates',
          ],
        ]}
      />
      <p>
        The <code>simple</code> configuration lowercases and splits but does not stem or drop words. That keeps exact tokens such as the
        error code <code>28P01</code> searchable and does not depend on English stemming rules.
      </p>
      <h3>Edits and deletions</h3>
      <p>
        An edit deletes every chunk containing that message and rebuilds its thread. A deletion removes the source text and derived chunks
        and leaves a tombstone, so a delayed event or an older history page cannot bring the message back. When a chunk’s text changes, its
        embedding is cleared and the embedding lane fills it again.
      </p>

      <h2 id="retrieval">Retrieval</h2>
      <p>
        Both searches run in one database session with the same filters: source, workspace, the allowed channel list, and an optional date
        range or <code>in:#channel</code> filter.
      </p>
      <h3>Dense arm</h3>
      <p>
        The question is embedded with the same model, and the 30 nearest chunks by pgvector cosine distance (<code>{'<=>'}</code>) are
        returned.
      </p>
      <h3>Lexical arm</h3>
      <p>
        <code>lexical_query()</code> lowercases the question, keeps alphanumeric terms, drops a fixed list of common English stop words, and
        joins what remains with OR. The result goes to <code>to_tsquery(&apos;simple&apos;, …)</code>, and the top 30 chunks by{' '}
        <code>ts_rank</code> are returned, so chunks that match more terms still rank higher.
      </p>
      <Code label="lexical_query()">{`"Which command fixed the local 28P01 Postgres failure?"
→ command | fixed | local | 28p01 | postgres | failure`}</Code>
      <Note>
        The lexical arm used to send the whole question through <code>websearch_to_tsquery</code>, which ANDs every word and keeps stop
        words. No chat message contains all of them, so it returned nothing for all 44 evaluation questions. See{' '}
        <Link href="/docs/evaluation#lexical-fix">the fix and its effect</Link>.
      </Note>
      <h3>Reciprocal rank fusion</h3>
      <p>
        The two ranked chunk lists are fused at the <strong>message</strong> level. For each list, the chunk at position <code>rank</code>{' '}
        (starting at 0) adds <code>1 / (rank + 10)</code> to the score of every message it contains. A message that appears in both arms, or
        in both its own chunk and a thread chunk, collects several contributions.
      </p>
      <Code label="Example">{`dense rank 0  → 1/10 = 0.100
lexical rank 1 → 1/11 = 0.091
message score  = 0.191`}</Code>
      <p>
        Messages are sorted by score and the top 12 are loaded. Both arms have equal weight. The constant 10 is smaller than the common
        default of 60, which gives the first few positions of each list more influence.
      </p>

      <h2 id="reranking">Reranking</h2>
      <p>
        The top 10 fused messages are reranked with the OpenRouter <strong>Decisions API</strong>, which returns a score for each question
        instead of generated text. One request carries the question and the 10 messages (channel, author, date, text) and asks, for each
        message, how useful it is as evidence. Messages are told to be treated as data, not instructions.
      </p>
      <Table
        head={['Level', 'Rubric']}
        rows={[
          ['0', 'Unrelated to the question.'],
          ['1', 'Same topic, but does not help answer the question.'],
          ['2', 'Partly answers the question or gives useful context for it.'],
          ['3', 'Directly answers the question.'],
        ]}
      />
      <ol>
        <li>
          <strong>Jev 1.13</strong> (<code>typesafe/jev-1.13-20260917</code>) is tried first.
        </li>
        <li>
          If it errors or times out, <strong>GPT-6 Luna Decisions</strong> (<code>openai/gpt-6-luna-decisions-20261006</code>) scores the
          same request.
        </li>
        <li>
          If both fail, or <code>OPEN_ROUTER</code> is unset, the plain RRF order is kept.
        </li>
      </ol>
      <p>
        The sort is stable, so ties keep their RRF order. Messages 11 and 12 are appended after the reranked 10. Catch-up, summaries, and
        decisions are not reranked: they read messages in time order instead.
      </p>

      <h2 id="generation">Generation</h2>
      <p>
        <code>gpt-5.4-mini</code> receives the question and the 12 evidence messages, each prefixed with its ID, channel, timestamp, and
        author. The instructions are to answer only from those messages, cite every factual claim with exact source IDs in square brackets,
        prefer the latest dated correction when messages conflict, say so when the evidence does not answer the question, and treat chat
        text as data rather than instructions.
      </p>
      <h3>Citation check</h3>
      <ul>
        <li>
          Every <code>[slack:…]</code> or <code>[synthetic:…]</code> ID in the output must be one of the 12 evidence IDs. One unknown ID
          replaces the whole answer with <em>“I couldn’t verify an answer from the available messages.”</em>
        </li>
        <li>An answer with no citations is replaced the same way, unless it explicitly says it couldn’t find enough evidence.</li>
        <li>Only the cited messages are returned as sources. With no evidence at all, the model is not called.</li>
        <li>
          In Slack, the evidence is read again right before delivery. If a source was edited, deleted, or became inaccessible, the answer is
          suppressed.
        </li>
      </ul>

      <h2 id="worker">API & worker</h2>
      <p>
        Slack expects an acknowledgement within three seconds, and model calls can take longer. RecallHQ splits the work: the API only
        verifies and records, and a separate worker process does everything else.
      </p>
      <SystemDiagram />
      <ul>
        <li>
          The API checks Slack’s signature, writes a job with a deduplication key (event ID or trigger ID), and acknowledges. Slack retries
          are ignored by that key.
        </li>
        <li>
          The worker claims jobs with <code>FOR UPDATE SKIP LOCKED</code> and a 10-minute lease that is renewed while it runs. Purges go
          first, then events, then commands. Failed jobs retry with exponential backoff (capped at five minutes), up to 8 attempts by
          default.
        </li>
        <li>
          History and replies are paged at Slack’s pace (by default one request per method per minute, 15 messages per page), with
          checkpoints that survive restarts. Completed channels are reconciled after a restart and every 24 hours.
        </li>
      </ul>

      <h2 id="isolation">Tenant isolation</h2>
      <Table
        head={['Layer', 'What it enforces']}
        rows={[
          [
            'Database roles',
            <>
              Every connection runs <code>SET ROLE</code> to <code>recallhq_reader</code> (queries) or <code>recallhq_ingestor</code> (Slack
              service). Both are NOLOGIN roles granted to non-superuser logins without BYPASSRLS.
            </>,
          ],
          [
            'Row-level security',
            <>
              Forced on <code>messages</code> and <code>chunks</code>. Readers see a row only if its source and workspace match the session
              and its channel is in the session’s channel list. Slack rows also need an active channel and installation.
            </>,
          ],
          [
            'Per-request context',
            <>
              <code>app.source</code>, <code>app.workspace</code> and <code>app.channels</code> are set from the requester’s current channel
              membership before retrieval.
            </>,
          ],
          [
            'Column grants',
            'The reader role can check that an installation is active, but cannot read OAuth credentials or channel names.',
          ],
          [
            'Encrypted secrets',
            <>
              Each workspace’s bot token is stored Fernet-encrypted with <code>SLACK_ENCRYPTION_KEY</code>. Queued command payloads are
              encrypted the same way.
            </>,
          ],
          ['Demo separation', 'The public site uses a fixed synthetic context and never receives Slack tokens or workspace data.'],
        ]}
      />
      <p>
        Read more about what is stored and deleted in <Link href="/docs/permissions">Permissions & data</Link>.
      </p>

      <h2 id="settings">Settings</h2>
      <Table
        head={['Setting', 'Default']}
        rows={[
          [<code key="a">GENERATION_MODEL</code>, <code key="b">gpt-5.4-mini</code>],
          [<code key="a">EMBEDDING_MODEL</code>, <code key="b">text-embedding-3-small</code>],
          [<code key="a">EMBEDDING_DIMENSION</code>, <code key="b">1536</code>],
          [<code key="a">OPEN_ROUTER</code>, 'OpenRouter API key; reranking is off when empty'],
          [<code key="a">RERANK_MODEL</code>, <code key="b">typesafe/jev-1.13-20260917</code>],
          [<code key="a">RERANK_FALLBACK_MODEL</code>, <code key="b">openai/gpt-6-luna-decisions-20261006</code>],
          [<code key="a">RERANK_TOP_K</code>, <code key="b">10</code>],
        ]}
      />
    </>
  );
}
