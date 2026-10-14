// Slack /recall command reference, shared by the command docs and the Slack bot setup guide.
export type CommandDoc = { name: string; syntax: string; summary: string; description: string; example: string; admin?: boolean };

export const commandDocs: CommandDoc[] = [
  {
    name: 'ask',
    syntax: '/recall ask <question> [in:#channel]',
    summary: 'Grounded answer with source links',
    description: 'Ask a question in plain English. RecallHQ retrieves relevant messages and produces an answer grounded in that evidence.',
    example: '/recall ask Why did we switch to Postgres? in:#eng',
  },
  {
    name: 'search',
    syntax: '/recall search <terms> [in:#channel]',
    summary: 'Ranked message excerpts',
    description: 'Return ranked message excerpts with links to the original Slack messages.',
    example: '/recall search pilot success criteria in:#product',
  },
  {
    name: 'catchup',
    syntax: '/recall catchup YYYY-MM-DD YYYY-MM-DD [in:#channel]',
    summary: 'Recap updates, decisions, blockers, and next steps',
    description:
      'Recap updates, decisions, blockers, and next steps over an inclusive date range of up to 32 days. Dates use your Slack timezone, with UTC as fallback. Large ranges or incomplete imports carry a partial-coverage notice.',
    example: '/recall catchup 2026-09-14 2026-09-18 in:#eng',
  },
  {
    name: 'summarize',
    syntax: '/recall summarize <Slack-message-link>',
    summary: 'Summary of the indexed thread',
    description:
      'Summarize an indexed thread. Paste the message link from Slack’s Copy link action; the channel must be indexed and accessible to you.',
    example: '/recall summarize https://your-workspace.slack.com/archives/C1234567890/p1726300000000000',
  },
  {
    name: 'decisions',
    syntax: '/recall decisions [in:#channel]',
    summary: 'Explicit decisions from the last seven days',
    description: 'Find explicit decisions from the last seven days in your accessible, ingested channels.',
    example: '/recall decisions in:#product',
  },
  {
    name: 'status',
    syntax: '/recall status',
    summary: 'Channels, message counts, history coverage, embedding backlog, errors',
    description: 'Inspect accessible channels, message counts, history coverage, embedding backlog, and import errors.',
    example: '/recall status',
  },
  {
    name: 'sync',
    syntax: '/recall sync #channel',
    summary: 'Retry a full history import',
    description: 'Workspace admins and owners can retry a full history import for a channel. Slack’s history limits still apply.',
    example: '/recall sync #eng',
    admin: true,
  },
  {
    name: 'forget',
    syntax: '/recall forget #channel',
    summary: 'Confirm disabling ingestion and purging channel data',
    description:
      'Workspace admins and owners can disable ingestion and purge a channel’s indexed content. The bot asks for confirmation before removal. Inviting the bot again explicitly re-enables a disabled channel.',
    example: '/recall forget #eng',
    admin: true,
  },
  {
    name: 'help',
    syntax: '/recall help',
    summary: 'Usage and access rules',
    description: 'Show command usage and access rules.',
    example: '/recall help',
  },
];
