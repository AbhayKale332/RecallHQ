# RecallHQ frontend

This public chat frontend is adapted from [Sanidhya Kumar Verma’s Slack clone](https://github.com/sanidhyy/slack-clone). Its MIT license is retained in [LICENSE](LICENSE).

Run with Node 22 or newer:

```bash
corepack pnpm install --frozen-lockfile
corepack pnpm dev
```

The site includes installation docs at `/docs`, a live synthetic playground at
`/playground`, and the Beacon chat demo at `/workspace/beacon/channel/eng`.
`/demo` redirects to that workspace. Visitors can use the demo without signing
in; real Slack messages are available only through the installed Slack bot.

Set `NEXT_PUBLIC_API_URL` in `.env.local` to the RecallHQ API base URL. The Vercel
project is `recallhq`, live at https://recall.abhaykale.me. Azure also hosts the
site at https://recova.indiasouthcentral.cloudapp.azure.com/recallhq. Azure builds
set `NEXT_PUBLIC_BASE_PATH=/recallhq`; Vercel and local builds leave it empty.
See the [Azure runbook](../deploy/azure/README.md) for the standalone Docker image.

With the production server running, check routes, responsive layouts, and
playground states using installed Chrome:

```sh
node scripts/check-docs-site.cjs
# Optional: test the hosted site and make one live synthetic search request.
SITE_CHECK_URL=https://recall.abhaykale.me SITE_CHECK_LIVE=1 node scripts/check-docs-site.cjs
```
