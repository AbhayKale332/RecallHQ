import Link from 'next/link';

import { commandDocs } from '@/lib/commands';

import { Code, Note, Table, Toc } from './docs-ui';

export function SlackBotDoc() {
  return (
    <>
      <Note>
        Just want RecallHQ in your workspace? Use the hosted app instead: <Link href="/docs/installation">Add to Slack</Link>. This guide is
        for running your own copy of the bot.
      </Note>
      <Toc
        items={[
          ['register', 'Register & run locally'],
          ['commands', 'Commands'],
          ['limits', 'Limits'],
          ['production', 'Production'],
          ['distribution', 'Distribution'],
        ]}
      />

      <h2 id="register">Register and run locally</h2>
      <p>
        Complete the <Link href="/docs/self-hosting">local backend setup</Link> first. You will also need{' '}
        <a href="https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/">cloudflared</a> or another HTTPS tunnel.
      </p>
      <ol>
        <li>
          Create a disposable free workspace at <a href="https://slack.com/get-started">slack.com/get-started</a>.
        </li>
        <li>
          At <a href="https://api.slack.com/apps">api.slack.com/apps</a>, choose <strong>Create New App → From scratch</strong>, name it
          RecallHQ, and select the workspace.
        </li>
        <li>
          Copy <code>slack/env.example</code> to <code>.env.slack</code>. From <strong>Basic Information → App Credentials</strong>, copy
          the client ID, client secret, and signing secret into it. Keep <code>OPENAI_API_KEY</code> in <code>.env</code>.
        </li>
        <li>Migrate the database, then start the API and a tunnel in separate terminals:</li>
      </ol>
      <Code label="Shell">{`uv sync --locked
docker compose up -d db
uv run python -m recallhq.cli migrate

uv run uvicorn recallhq.api:app --host 127.0.0.1 --port 8001 --reload
cloudflared tunnel --url http://127.0.0.1:8001 --no-autoupdate`}</Code>
      <ol start={5}>
        <li>With the HTTPS URL the tunnel prints, set the public URL and encryption key, generate the manifest, and start the worker:</li>
      </ol>
      <Code label="Shell">{`uv run python -m recallhq.cli slack-init --base-url https://your-tunnel.trycloudflare.com
uv run python -m recallhq.cli slack-manifest --base-url https://your-tunnel.trycloudflare.com > manifest.json
uv run python -m recallhq.cli slack-worker`}</Code>
      <ol start={6}>
        <li>
          Paste <code>manifest.json</code> into the app’s <strong>App Manifest</strong> page and save. It configures OAuth, events,
          interactivity, and <code>/recall</code>. Keep the API running so Slack can verify the request URL.
        </li>
        <li>
          Visit <code>https://your-tunnel.trycloudflare.com/slack/install</code> and authorize. Use this link even if you already installed
          from Slack’s dashboard: the OAuth callback is what stores the installation in your database.
        </li>
        <li>
          Invite <code>@RecallHQ</code> to a test channel, run <code>/recall status</code>, post a test fact, and ask about it with{' '}
          <code>/recall ask</code>.
        </li>
      </ol>
      <Note>
        <code>slack-init</code> writes <code>SLACK_PUBLIC_URL</code> and a new <code>SLACK_ENCRYPTION_KEY</code> to <code>.env.slack</code>{' '}
        without printing the key. Keep that key: losing it means every workspace must reinstall. Quick tunnels are temporary, so regenerate
        the manifest and update <code>SLACK_PUBLIC_URL</code> when the hostname changes, then restart the API and worker.
      </Note>

      <h2 id="commands">Commands</h2>
      <Table
        head={['Command', 'Result']}
        rows={commandDocs.map((command) => [
          <code key="c">{command.syntax}</code>,
          <>
            {command.admin && <strong>Admin/owner: </strong>}
            {command.summary}
          </>,
        ])}
      />
      <p>
        Channel mentions are resolved to IDs. Searches default to all ingested channels the requester belongs to, including private
        channels. Results are private, and current membership is checked before retrieval and again before delivery. Full details are in the{' '}
        <Link href="/docs/commands">command reference</Link>.
      </p>

      <h2 id="limits">Limits and what is imported</h2>
      <ul>
        <li>
          Default command limits: 5 per user per minute and 200 per workspace per UTC day (<code>SLACK_USER_COMMANDS_PER_MINUTE</code>,{' '}
          <code>SLACK_WORKSPACE_COMMANDS_PER_DAY</code>).
        </li>
        <li>
          Commercially distributed apps outside the Marketplace get one <code>conversations.history</code> and one{' '}
          <code>conversations.replies</code> request per minute per workspace, with up to 15 messages per page. The defaults match that, and
          the scheduler honours <code>Retry-After</code>. Large imports take time.
        </li>
        <li>
          Imported: channel text and thread replies, including text from other bots. Not imported: RecallHQ’s own output, system events,
          file contents, DMs, Slack Connect channels, and org-wide installs.
        </li>
      </ul>

      <h2 id="production">Production</h2>
      <p>
        Apply migrations as the schema owner before starting the new API and worker. The migration owner must be able to create the NOLOGIN
        roles <code>recallhq_reader</code> and <code>recallhq_ingestor</code>. Then grant them to separate runtime logins:
      </p>
      <Code label="SQL">{`GRANT recallhq_reader TO your_query_login;
GRANT recallhq_ingestor TO your_slack_service_login;`}</Code>
      <p>
        Runtime logins must not be superusers, schema owners, or have BYPASSRLS. Set <code>DATABASE_URL</code> to the query login,{' '}
        <code>DATABASE_WRITE_URL</code> to the Slack service login, and <code>DATABASE_MIGRATION_URL</code> only when migrating. Keep Slack
        secrets and the encryption key in the server’s runtime environment file, outside the repository.
      </p>
      <p>One image runs both the API and the worker:</p>
      <Code label="Shell">{`docker build -t recallhq-slack .
docker run --rm --env-file /path/to/migration.env recallhq-slack python -m recallhq.cli migrate
# API container: default image command
# Worker container: python -m recallhq.cli slack-worker

# Or, locally after migrating:
docker compose --profile slack up -d --build api slack-worker`}</Code>
      <p>
        Keep the API behind a reverse proxy and the worker internal. Generate the manifest from the externally visible API base URL
        (including a path prefix such as <code>/recallhq/api</code> if the proxy strips it), and update the manifest and{' '}
        <code>SLACK_PUBLIC_URL</code> together.
      </p>

      <h2 id="distribution">Distribution</h2>
      <p>
        To install into workspaces other than the one where the app was created, enable{' '}
        <strong>Manage Distribution → Activate Public Distribution</strong>, complete Slack’s requirements, and share your hosted{' '}
        <code>/slack/install</code> link. Workspace admins may still need to approve it. Before a Marketplace submission, publish privacy
        and support pages that describe external model processing and deletion and backup behaviour.
      </p>
    </>
  );
}
