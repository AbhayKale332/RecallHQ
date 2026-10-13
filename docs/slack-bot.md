# RecallHQ Slack bot

RecallHQ supports multiple workspace installations through OAuth. Inviting the bot
into a public or private channel starts live ingestion and imports the history
Slack makes available. Queries search only ingested channels the requester
currently belongs to; answers and search results are private and link to Slack
source messages.

The repository's public Beacon demo continues to serve synthetic data only.

## Register and run locally

1. Create a disposable free workspace at <https://slack.com/get-started>.
2. At <https://api.slack.com/apps>, choose **Create New App → From scratch**, name
   it RecallHQ, and select the workspace.
3. Copy `slack/env.example` to `.env.slack`. In **Basic Information → App
   Credentials**, copy the client ID, client secret, and signing secret into the
   matching entries. Keep `OPENAI_API_KEY` in `.env`.
4. Install dependencies and migrate the local database:

   ```bash
   uv sync --locked
   docker compose up -d db
   uv run python -m recallhq.cli migrate
   ```

5. Start the API and an HTTPS tunnel in separate terminals:

   ```bash
   uv run uvicorn recallhq.api:app --host 127.0.0.1 --port 8001 --reload
   cloudflared tunnel --url http://127.0.0.1:8001 --no-autoupdate
   ```

6. Using the HTTPS URL printed by the tunnel, initialize local settings and
   generate the manifest in the repository root:

   ```bash
   uv run python -m recallhq.cli slack-init --base-url https://your-tunnel.trycloudflare.com
   uv run python -m recallhq.cli slack-manifest --base-url https://your-tunnel.trycloudflare.com > manifest.json
   uv run python -m recallhq.cli slack-worker
   ```

7. Paste `manifest.json` into the app dashboard's **App Manifest** page and save.
   It configures OAuth, events, interactivity, and `/recall`. Keep the API running
   so Slack can verify the request URL.
8. Visit `https://your-tunnel.trycloudflare.com/slack/install`, click **Add to
   Slack**, and authorize. Use this installation link even if you already clicked
   Slack's dashboard install button: the OAuth callback stores the installation
   with this backend.
9. Invite `@RecallHQ` into a disposable channel. Run `/recall status`, post a test
   fact, and ask a question with `/recall ask`.

The app uses each installation's encrypted OAuth bot token. Global `Bot_token`,
`User_token`, and `App_token` entries are not needed by the integration.

The Slack desktop app and Slack developer CLI are separate programs. To install
the CLI without colliding with the desktop app's `slack` command:

```bash
curl -fsSL https://downloads.slack-edge.com/slack-cli/install.sh | bash -s slack-cli
slack-cli version
slack-cli login
```

Registration can also be completed entirely through the app dashboard and OAuth
flow above; CLI authentication is independent of OAuth installation storage.
See [Slack CLI installation](https://docs.slack.dev/tools/slack-cli/guides/installing-the-slack-cli-for-mac-and-linux/).

Quick tunnels are temporary. Regenerate the manifest and update
`SLACK_PUBLIC_URL` whenever the tunnel hostname changes; restart the API and
worker after configuration changes. Use a stable HTTPS URL for the hosted pilot.
See [Cloudflare Quick Tunnels](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/).

## Commands

| Command | Result |
| --- | --- |
| `/recall help` | Usage and access rules |
| `/recall ask <question> [in:#channel]` | Grounded answer with source links |
| `/recall search <terms> [in:#channel]` | Ranked message excerpts |
| `/recall catchup YYYY-MM-DD YYYY-MM-DD [in:#channel]` | Recap updates, decisions, blockers, and next steps |
| `/recall summarize <Slack-message-link>` | Summary of the indexed thread |
| `/recall decisions [in:#channel]` | Explicit decisions from the last seven days |
| `/recall status` | Accessible channels, message counts, history coverage, embedding backlog, and errors |
| `/recall sync #channel` | Admin/owner: retry a full history import |
| `/recall forget #channel` | Admin/owner: confirm disabling ingestion and purging channel data |

Channel mentions are resolved to IDs. Searches default to all ingested channels
the requester belongs to, including private channels. No cross-channel result is
posted publicly. Current membership is checked before retrieval and again before
delivery; changed or deleted evidence suppresses the answer.

Catch-up ranges are inclusive and limited to 32 days. Dates use the requester's
Slack timezone, with UTC as fallback. Recaps scan chronological messages and
summarize in bounded batches. More than 2,000 matching messages, unusually long
messages, or the eight-batch context budget produce an explicit partial-coverage
notice. An unfinished history import also produces a coverage notice.

Default command limits are five per user per minute and 200 per workspace per
UTC day. They are independent of anonymous demo limits and configurable through
the entries in `slack/env.example`.

## Ingestion and recovery

- Verified HTTP requests are persisted before acknowledgement. Model and history
  calls run in a separate worker. Worker lanes keep commands and embeddings from
  blocking message/deletion processing.
- Durable jobs have deduplication keys, leases, renewal, bounded retries, and
  sanitized errors. Completed payloads are removed; failed jobs remain available
  for diagnosis. `/recall sync` retries history with a new import boundary.
- History and reply pagination checkpoints survive restarts. Live capture runs
  alongside imports; original timestamp strings remain part of canonical IDs.
- Message edits rebuild affected chunks. Deletion tombstones prevent older API
  responses or delayed events from restoring a deleted message. Embedding writes
  compare the underlying text before committing results.
- Completed channels receive a full reconciliation after worker restart and
  every 24 hours. Missing/inaccessible historical sources are removed only after
  every history and reply page succeeds. Failed or partial imports never trigger
  that cleanup.
- Bot removal, channel archive/deletion, token revocation, and app uninstall
  disable access immediately and enqueue content cleanup. Explicit reinvitation
  re-enables a disabled channel; reinstalling OAuth alone preserves disabled
  channel choices.

New commercially distributed apps outside the Marketplace have restrictive
history/reply limits: one request per minute per method/workspace and 15 objects
per page. Imports across many channels can take substantial time. The scheduler
honors `Retry-After`; change its defaults only when the app's Slack rate tier
permits it. [History reference](https://docs.slack.dev/reference/methods/conversations.history/),
[Replies reference](https://docs.slack.dev/reference/methods/conversations.replies/).

V1 ingests channel text and thread replies, including textual posts from other
bots. It excludes RecallHQ's own output, non-content system events, file contents,
personal/group DMs, Slack Connect channels, and organization-wide installations.
Slack can restrict history through workspace retention, plan limits, scopes, or
admin policy. The bot cannot import messages the APIs do not expose.

## Database and deployment

Migrations are recorded once in `schema_migrations` and serialized with an
advisory lock. Apply them as the schema owner before starting the new API and
worker. The migration owner needs permission to create the two NOLOGIN roles
`recallhq_reader` and `recallhq_ingestor` and grant them to runtime accounts.

For production, use separate LOGIN accounts and grant role membership:

```sql
GRANT recallhq_reader TO your_query_login;
GRANT recallhq_ingestor TO your_slack_service_login;
```

The runtime logins must not be superusers, schema owners, or have BYPASSRLS.
The application explicitly selects a restricted role on each new connection.
Read policies enforce source, workspace, authorized channels, and active Slack
installation/channel status. Reader grants exclude OAuth credentials. The Slack
service can manage installation/job records and write content within the current
workspace; it must not be exposed as a public query credential.

Set `DATABASE_URL` to the query login, `DATABASE_WRITE_URL` to the Slack service
login, and `DATABASE_MIGRATION_URL` only for migration execution. Use verified
TLS and the existing VM-only database firewall. Keep Slack secrets and the
encryption key in the VM's runtime environment file, outside the repository.
Preserve the encryption key across restarts; losing it requires reinstalling
workspaces.

The same image supports the API and worker:

```bash
docker build -t recallhq-slack .
docker run --rm --env-file /path/to/migration.env recallhq-slack python -m recallhq.cli migrate
# API container: default image command
# Worker container: python -m recallhq.cli slack-worker
```

For a local container-based pilot after migration:

```bash
docker compose --profile slack up -d --build api slack-worker
```

On the existing Azure VM, deploy both containers to the existing Docker network.
Keep the API behind Caddy and the worker internal. Generate the manifest using
the externally visible API base URL, including `/recallhq/api` if Caddy strips
that prefix. Update Slack's manifest and `SLACK_PUBLIC_URL` together, then install
through the hosted OAuth URL. Stop the local tunnel/worker when moving the pilot
to the hosted instance.

## Validation

The default test suite runs offline. Postgres integration tests require a
disposable PG16/pgvector administrator URL; they create and drop their own test
database and never use the application's `DATABASE_URL`:

```bash
RECALLHQ_TEST_DATABASE_URL=postgresql://postgres:recallhq-test@127.0.0.1:55432/postgres uv run pytest -q
```

The integration suite covers OAuth replay/expiry, encrypted tokens, signed
requests, command quotas, workspace/channel isolation, anonymous demo isolation,
edit/deletion ordering, oversized threads/messages, stale embeddings, expired
leases, history/reply pagination, reconciliation, uninstall cleanup, private
responses, and access revocation before delivery.

For the live pilot, test installation into two workspaces, public and private
channel invitations, edits/deletions, thread summaries, and admin removal. Check
message-to-index lag, query latency, history coverage, failed jobs, and model
usage without enabling HTTP debug logs or logging source text.

## Retention and distribution

There is no automatic age expiry. Deletion events remove source text and derived
chunks; confirmed channel removal and uninstall also cancel queued work and
purge the affected data. Local development has no automatic backup. For the Azure
pilot, configure a seven-day backup retention window and publish that window in
the app's data-handling policy; deletion from the running database does not erase
existing backups. Before restoring backups to service, reconcile removals and
revocations.

To install into workspaces beyond the one where the app was created, enable
**Manage Distribution → Activate Public Distribution** in the app dashboard,
complete Slack's requirements, and share the hosted `/slack/install` link.
Workspace admins may still require approval. Use unlisted distribution for the
pilot; commercial public distribution should proceed through Marketplace review.
See [Slack app distribution](https://docs.slack.dev/app-management/distribution/).

Before Marketplace submission, use a stable hosted URL, publish accurate privacy
and support pages describing external model processing and deletion/backup
behavior, verify two-workspace access boundaries, and complete Slack's submission
requirements. API data is supplied to the configured embedding/generation
provider and, when enabled, the reranking provider; it is not used by RecallHQ to
train models.
