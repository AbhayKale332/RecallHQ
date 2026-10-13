# Azure pilot

RecallHQ uses the existing `recova-vm` VM and managed PostgreSQL service
`recallhq-pg-abhay`. No new VM or database server is required.

| Endpoint | URL |
| --- | --- |
| Site | https://recova.indiasouthcentral.cloudapp.azure.com/recallhq |
| Docs | https://recova.indiasouthcentral.cloudapp.azure.com/recallhq/docs |
| Playground | https://recova.indiasouthcentral.cloudapp.azure.com/recallhq/playground |
| Install | https://recova.indiasouthcentral.cloudapp.azure.com/recallhq/api/slack/install |
| Health | https://recova.indiasouthcentral.cloudapp.azure.com/recallhq/api/health |

## Runtime

The deployment directory is `/home/azureuser/recallhq`. Copy `compose.yaml`
there as `compose.slack.yaml`. It joins the existing `recova_default` network;
Caddy terminates HTTPS. There are no additional public container ports.

`slack-runtime.env` is a mode-600 file outside Git. It contains:

- `DATABASE_URL`: verified-TLS connection for the read-only `recallhq_app` login.
- `DATABASE_WRITE_URL`: verified-TLS connection for the `recallhq_slack` login.
- `OPENAI_API_KEY`, optional `OPEN_ROUTER`.
- `SLACK_CLIENT_ID`, `SLACK_CLIENT_SECRET`, `SLACK_SIGNING_SECRET`,
  `SLACK_ENCRYPTION_KEY`.
- `SLACK_PUBLIC_URL=https://recova.indiasouthcentral.cloudapp.azure.com/recallhq/api`.
- `QUOTA_DB=/data/quotas.sqlite3`.

URLs in Docker env files are literal single-line values; do not surround them
with quotes. Encode URL credential characters. The certificate is mounted at
`/data/azure-ca.crt`. Keep the encryption key backed up securely: it decrypts
stored workspace installations. The runtime does not receive database admin
credentials or global Slack user/app tokens.

The API and worker each have a 256 MiB limit; the site has 192 MiB. Docker
restarts them after a reboot. This small VM is suitable for a pilot; inspect
memory and queue latency as workspace traffic grows.

## Release

Build on the development machine rather than this small VM:

```sh
docker build -t YOUR_REGISTRY/recallhq-api:RELEASE .
docker build --build-arg NEXT_PUBLIC_BASE_PATH=/recallhq \
  -t YOUR_REGISTRY/recallhq-docs:RELEASE frontend
docker push YOUR_REGISTRY/recallhq-api:RELEASE
docker push YOUR_REGISTRY/recallhq-docs:RELEASE
```

Update image references in the compose file and copy it to the deployment
directory. Before schema changes, take a custom-format `pg_dump` using the schema
owner, with verified TLS. Azure's existing burstable PostgreSQL tier does not
support customer on-demand snapshots. The pre-Slack dump is stored privately
at `backups/before-slack-20261014.dump`; its archive listing was verified. Managed
database backups also retain seven days.

Run migrations once with a temporary mode-600 admin env file and remove it
afterward. Never add admin credentials to `slack-runtime.env`:

```sh
cd /home/azureuser/recallhq
docker run --rm --network recova_default --env-file slack-admin.env \
  -v "$PWD/data:/data:ro" YOUR_REGISTRY/recallhq-api:RELEASE \
  python -m recallhq.cli migrate
rm slack-admin.env
docker compose -f compose.slack.yaml pull
docker compose -f compose.slack.yaml up -d
```

The schema owner grants `recallhq_reader` to `recallhq_app` and
`recallhq_ingestor` to `recallhq_slack`. Both runtime logins lack superuser,
role-creation, and RLS-bypass privileges. Public demo requests are limited to
the synthetic Beacon corpus; real Slack content requires workspace and channel
context.

Caddy keeps the existing application's routes and adds these handlers inside
its existing site block:

```caddyfile
handle_path /recallhq/api/* {
    reverse_proxy recallhq-slack-api:8001 {
        header_up X-Real-IP {remote_host}
    }
}
handle /recallhq {
    reverse_proxy recallhq-docs:3000
}
handle /recallhq/* {
    reverse_proxy recallhq-docs:3000
}
```

Back up the Caddyfile, validate, then reload Caddy. Copy the generated root
`manifest.json` into Slack's **App Manifest** dashboard and save to move event,
slash-command, interactivity, and OAuth URLs to Azure. The existing workspace
installation has been transferred with the same encryption key; it needs no
fresh OAuth installation. Once a real command succeeds through Azure, stop the
old local API, worker, and temporary tunnel.

## Operations

```sh
cd /home/azureuser/recallhq
docker compose -f compose.slack.yaml ps
docker compose -f compose.slack.yaml logs --tail 50 worker
docker stats --no-stream
curl -fsS https://recova.indiasouthcentral.cloudapp.azure.com/recallhq/api/health
```

Run `/recall status` to check history coverage and indexing backlog; an admin
can retry an import with `/recall sync #channel`. The worker reconciles stored
messages against Slack after restarts and every day.

For an application-only rollback, use the last compatible image and restart
the affected service. The pre-Slack image is incompatible with the new RLS
schema, so a rollback to it also requires a coordinated database restore and
maintenance window. Its stopped container is retained on the VM with automatic
restart disabled. The original proxy config is backed up at
`/home/azureuser/recova/Caddyfile.before-slack-20261014`.
