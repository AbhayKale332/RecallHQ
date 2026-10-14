// Docs navigation. Order here is the sidebar order and the previous/next order.
export type DocsPage = { slug: string; label: string; title: string; description: string };

export const docsSections: { title: string; pages: DocsPage[] }[] = [
  {
    title: 'Get started',
    pages: [
      {
        slug: '',
        label: 'Overview',
        title: 'RecallHQ documentation',
        description:
          'RecallHQ turns your Slack conversations into a searchable team memory, with answers you can trace back to the original messages.',
      },
      {
        slug: 'installation',
        label: 'Add to Slack',
        title: 'Add RecallHQ to Slack',
        description: 'Install the hosted app, invite it to a channel, and check that your team’s available history is being indexed.',
      },
      {
        slug: 'quickstart',
        label: 'Your first answer',
        title: 'Your first answer',
        description: 'Go from a channel conversation to a grounded answer in a few steps.',
      },
    ],
  },
  {
    title: 'Using RecallHQ',
    pages: [
      {
        slug: 'commands',
        label: 'Command reference',
        title: 'Command reference',
        description: 'Use /recall in Slack. Answers and search results are private to you and include source links.',
      },
      {
        slug: 'permissions',
        label: 'Permissions & data',
        title: 'Permissions & data',
        description: 'RecallHQ searches ingested channels you currently belong to. Workspace data stays separate from the public demo.',
      },
      {
        slug: 'troubleshooting',
        label: 'Troubleshooting',
        title: 'Troubleshooting',
        description: 'Check channel access and import coverage first. /recall status shows what RecallHQ can currently search.',
      },
    ],
  },
  {
    title: 'Install & self-host',
    pages: [
      {
        slug: 'self-hosting',
        label: 'Run locally',
        title: 'Run RecallHQ locally',
        description:
          'Start Postgres with pgvector, load the synthetic Beacon corpus, run the API and tests, and point the docs site at your local API.',
      },
      {
        slug: 'slack-bot',
        label: 'Slack bot setup',
        title: 'Set up your own Slack bot',
        description:
          'Register a Slack app, connect it to your RecallHQ API through a tunnel, run the worker, and install it into a workspace.',
      },
    ],
  },
  {
    title: 'How it works',
    pages: [
      {
        slug: 'architecture',
        label: 'Model architecture',
        title: 'Model architecture',
        description:
          'How a Slack message becomes searchable, and how a question becomes a cited answer: chunking, hybrid retrieval, reranking, generation, and tenant isolation.',
      },
      {
        slug: 'evaluation',
        label: 'Evaluations',
        title: 'Evaluations',
        description: 'How retrieval and answers are measured, on what data, and which results exist so far.',
      },
    ],
  },
];

export const docsPages = docsSections.flatMap((section) => section.pages);

export const docsHref = (slug: string) => (slug ? `/docs/${slug}` : '/docs');

export const GITHUB_URL = 'https://github.com/AbhayKale332/RecallHQ';
