# RecallHQ frontend

This public chat frontend is adapted from [Sanidhya Kumar Verma’s Slack clone](https://github.com/sanidhyy/slack-clone). Its MIT license is retained in [LICENSE](LICENSE).

Run with Node 22 or newer:

```bash
corepack pnpm install --frozen-lockfile
corepack pnpm dev
```

Set `NEXT_PUBLIC_API_URL` in `.env.local` to the RecallHQ API base URL. The deployed Vercel project is `recallhq`; its production URL is https://recallhq-black.vercel.app. The visitor sees the seeded Beacon chat without signing in. Commands call the Azure-hosted API, while plain visitor messages remain in page memory until refresh.
