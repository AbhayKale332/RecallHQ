import Link from 'next/link';

import { GITHUB_URL } from '@/lib/docs-nav';

import { Code, Note, Table, Toc } from './docs-ui';

export function SelfHostingDoc() {
  return (
    <>
      <Toc
        items={[
          ['requirements', 'Requirements'],
          ['backend', 'Backend quickstart'],
          ['environment', 'Environment'],
          ['try-it', 'Try the API'],
          ['tests', 'Tests'],
          ['frontend', 'Frontend'],
        ]}
      />
      <h2 id="requirements">Requirements</h2>
      <ul>
        <li>
          Python 3.12 and <a href="https://docs.astral.sh/uv/">uv</a>
        </li>
        <li>Docker, for Postgres 16 with pgvector</li>
        <li>Node 22 or newer with corepack, for the docs site and demo</li>
        <li>
          An OpenAI API key with access to <code>text-embedding-3-small</code> and <code>gpt-5.4-mini</code>. An OpenRouter key is optional
          and turns on reranking.
        </li>
      </ul>

      <h2 id="backend">Backend quickstart</h2>
      <p>
        Clone <a href={GITHUB_URL}>the repository</a>, add your keys to <code>.env</code> (see below), then run from the repository root:
      </p>
      <Code label="Shell">{`uv sync --locked
docker compose up -d
uv run python -m recallhq.cli migrate
uv run python -m recallhq.cli ingest data/synthetic/corpus.jsonl
uv run uvicorn recallhq.api:app --reload
uv run pytest -q`}</Code>
      <ol>
        <li>
          <code>uv sync</code> installs the Python dependencies from the lockfile.
        </li>
        <li>
          <code>docker compose up -d</code> starts <code>pgvector/pgvector:pg16</code> on port 5432. The API and Slack worker containers sit
          behind the <code>slack</code> profile and do not start here.
        </li>
        <li>
          <code>migrate</code> applies <code>migrations/*.sql</code> once each, under an advisory lock, and creates the{' '}
          <code>recallhq_reader</code> and <code>recallhq_ingestor</code> roles.
        </li>
        <li>
          <code>ingest</code> loads the synthetic Beacon corpus, builds message and thread chunks, and embeds them. It is re-runnable:
          unchanged chunks keep their embeddings.
        </li>
        <li>
          <code>uvicorn</code> serves the public API on <code>http://127.0.0.1:8000</code>.
        </li>
      </ol>

      <h2 id="environment">Environment</h2>
      <p>
        Settings are read from <code>.env</code> (and <code>.env.slack</code> for the bot). Local defaults match <code>compose.yaml</code>.
      </p>
      <Table
        head={['Variable', 'Required', 'Purpose']}
        rows={[
          [<code key="v">OPENAI_API_KEY</code>, 'Yes', 'Embeddings for ingest and queries, and answer generation'],
          [
            <code key="v">DATABASE_URL</code>,
            'No',
            <>
              Query login. Defaults to <code>postgresql://recallhq:recallhq@localhost:5432/recallhq</code>
            </>,
          ],
          [<code key="v">OPEN_ROUTER</code>, 'No', 'OpenRouter key for Decisions API reranking. Without it, results keep RRF order'],
          [<code key="v">DATABASE_WRITE_URL</code>, 'Production', 'Slack service login (ingestor role). Falls back to DATABASE_URL'],
          [<code key="v">DATABASE_MIGRATION_URL</code>, 'Production', 'Schema owner, used only by migrate'],
        ]}
      />
      <Note>Keep keys in your local env files only. They are not needed by the frontend, and nothing in the site reads them.</Note>

      <h2 id="try-it">Try the API</h2>
      <p>
        The public endpoint accepts the same three commands as the <Link href="/playground">playground</Link>, scoped to the synthetic
        corpus.
      </p>
      <Code label="Shell">{`curl -s http://127.0.0.1:8000/commands \\
  -H 'Content-Type: application/json' \\
  -d '{"input": "/ask Why did the team switch from MongoDB to Postgres for the pilot?"}'`}</Code>
      <p>
        <code>/search &lt;terms&gt;</code> returns ranked hits, and <code>/catchup YYYY-MM-DD YYYY-MM-DD [#channel]</code> recaps a date
        range of up to 32 days. Anonymous commands are limited to 3 per minute and 20 per day per IP, plus 200 per day site-wide.
      </p>

      <h2 id="tests">Tests</h2>
      <p>
        The default suite runs offline. Postgres integration tests need a disposable PG16 + pgvector admin URL; they create and drop their
        own database and never touch <code>DATABASE_URL</code>.
      </p>
      <Code label="Shell">{`uv run pytest -q
RECALLHQ_TEST_DATABASE_URL=postgresql://recallhq:recallhq@localhost:5432/recallhq uv run pytest -q`}</Code>
      <p>
        To measure retrieval quality, see <Link href="/docs/evaluation#reproduce">Evaluations</Link>.
      </p>

      <h2 id="frontend">Frontend</h2>
      <p>
        The docs, playground, and Beacon demo are a Next.js app in <code>frontend/</code>, adapted from an MIT-licensed Slack clone.
      </p>
      <Code label="Shell">{`cd frontend
echo 'NEXT_PUBLIC_API_URL=http://127.0.0.1:8000' > .env.local
corepack pnpm install --frozen-lockfile
corepack pnpm dev`}</Code>
      <p>
        Open <code>http://localhost:3000</code>, which the API already allows through CORS. Without <code>NEXT_PUBLIC_API_URL</code>, the
        site uses the hosted API.
      </p>
      <Table
        head={['Variable', 'Purpose']}
        rows={[
          [<code key="v">NEXT_PUBLIC_API_URL</code>, 'RecallHQ API base URL for the playground and demo'],
          [
            <code key="v">NEXT_PUBLIC_BASE_PATH</code>,
            <>
              Serve the site under a sub-path, for example <code>/recallhq</code>. Leave empty at the domain root
            </>,
          ],
        ]}
      />
      <p>Before shipping a change to the site, check it against a production build:</p>
      <Code label="Shell">{`corepack pnpm lint
corepack pnpm build && corepack pnpm start
node scripts/check-docs-site.cjs   # routes, overflow, playground states`}</Code>
      <p>
        Next: <Link href="/docs/slack-bot">connect your own Slack bot</Link>.
      </p>
    </>
  );
}
