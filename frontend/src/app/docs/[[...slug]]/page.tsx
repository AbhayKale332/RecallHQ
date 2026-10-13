import type { Metadata } from 'next';
import Link from 'next/link';
import { notFound } from 'next/navigation';
import type { ReactNode } from 'react';

import { InstallLink, SiteShell, docsLinks } from '@/components/site-shell';
import styles from '@/components/site.module.css';
import { DEMO_URL } from '@/lib/public-api';

const pages = {
  introduction: [
    'Introduction',
    'RecallHQ turns your Slack conversations into a searchable team memory, with answers you can trace back to the original messages.',
  ],
  installation: [
    'Add RecallHQ to Slack',
    'Install the app, invite it to a channel, and check that your team’s available history is being indexed.',
  ],
  quickstart: ['Your first answer', 'Go from a channel conversation to a grounded answer in a few steps.'],
  commands: ['Command reference', 'Use /recall in Slack. Answers and search results are private to you and include source links.'],
  permissions: [
    'Permissions & data',
    'RecallHQ searches ingested channels you currently belong to. Workspace data stays separate from the public demo.',
  ],
  troubleshooting: [
    'Troubleshooting',
    'Check channel access and import coverage first. /recall status shows what RecallHQ can currently search.',
  ],
} as const;

const commandDocs = [
  {
    name: 'ask',
    syntax: '/recall ask <question> [in:#channel]',
    description: 'Ask a question in plain English. RecallHQ retrieves relevant messages and produces an answer grounded in that evidence.',
    example: '/recall ask Why did we switch to Postgres? in:#eng',
  },
  {
    name: 'search',
    syntax: '/recall search <terms> [in:#channel]',
    description: 'Return ranked message excerpts with links to the original Slack messages.',
    example: '/recall search pilot success criteria in:#product',
  },
  {
    name: 'catchup',
    syntax: '/recall catchup YYYY-MM-DD YYYY-MM-DD [in:#channel]',
    description:
      'Recap updates, decisions, blockers, and next steps over an inclusive date range of up to 32 days. Dates use your Slack timezone, with UTC as fallback. Large ranges or incomplete imports carry a partial-coverage notice.',
    example: '/recall catchup 2026-09-14 2026-09-18 in:#eng',
  },
  {
    name: 'summarize',
    syntax: '/recall summarize <Slack-message-link>',
    description:
      'Summarize an indexed thread. Paste the message link from Slack’s Copy link action; the channel must be indexed and accessible to you.',
    example: '/recall summarize https://your-workspace.slack.com/archives/C1234567890/p1726300000000000',
  },
  {
    name: 'decisions',
    syntax: '/recall decisions [in:#channel]',
    description: 'Find explicit decisions from the last seven days in your accessible, ingested channels.',
    example: '/recall decisions in:#product',
  },
  {
    name: 'status',
    syntax: '/recall status',
    description: 'Inspect accessible channels, message counts, history coverage, embedding backlog, and import errors.',
    example: '/recall status',
  },
  {
    name: 'sync',
    syntax: '/recall sync #channel',
    description: 'Workspace admins and owners can retry a full history import for a channel. Slack’s history limits still apply.',
    example: '/recall sync #eng',
    admin: true,
  },
  {
    name: 'forget',
    syntax: '/recall forget #channel',
    description:
      'Workspace admins and owners can disable ingestion and purge a channel’s indexed content. The bot asks for confirmation before removal. Inviting the bot again explicitly re-enables a disabled channel.',
    example: '/recall forget #eng',
    admin: true,
  },
  { name: 'help', syntax: '/recall help', description: 'Show command usage and access rules.', example: '/recall help' },
];

function Note({ children }: { children: ReactNode }) {
  return (
    <aside className={styles.note}>
      <p>{children}</p>
    </aside>
  );
}
function Code({ children }: { children: string }) {
  return (
    <div className={styles.codeBlock}>
      <code>{children}</code>
    </div>
  );
}

function Documentation({ page }: { page: keyof typeof pages }) {
  switch (page) {
    case 'introduction':
      return (
        <>
          <h2>Find the context behind the conversation</h2>
          <p>
            Your team has already discussed the plan, the tradeoff, and the fix. RecallHQ helps you find that context without remembering
            the exact wording or who posted it.
          </p>
          <ul>
            <li>
              <strong>Ask:</strong> get an answer with supporting message links.
            </li>
            <li>
              <strong>Search:</strong> retrieve ranked excerpts from conversations.
            </li>
            <li>
              <strong>Catch up:</strong> recap a date range with decisions and next steps.
            </li>
            <li>
              <strong>Summarize:</strong> turn an indexed Slack thread into a concise summary.
            </li>
          </ul>
          <h2>How it works</h2>
          <p>
            Add RecallHQ to your workspace and invite it into selected public or private channels. It imports the history Slack makes
            available and indexes new messages and thread replies.
          </p>
          <p>
            Commands search ingested channels you belong to. Your membership is checked before retrieval and again before the answer is
            delivered. Replies stay private and link back to Slack.
          </p>
          <Note>
            The public Beacon demo and playground use synthetic conversations only. Installing RecallHQ never makes your Slack messages
            available on this website.
          </Note>
          <div className={styles.docsCards}>
            <Link href="/docs/installation">
              <strong>Install in your workspace →</strong>
              <span>Authorize the app and invite it to a channel.</span>
            </Link>
            <Link href="/playground">
              <strong>Try the playground →</strong>
              <span>Ask questions about the fictional Beacon pilot.</span>
            </Link>
            <Link href="/docs/commands">
              <strong>Explore the commands →</strong>
              <span>Examples, syntax, and admin controls.</span>
            </Link>
            <Link href="/docs/permissions">
              <strong>Understand data access →</strong>
              <span>Channel permissions, processing, and deletion.</span>
            </Link>
          </div>
        </>
      );
    case 'installation':
      return (
        <>
          <h2>1. Authorize RecallHQ</h2>
          <p>
            Open the installation link, select your Slack workspace, and review the permissions before authorizing. Your workspace may
            require an admin’s approval.
          </p>
          <InstallLink />
          <Note>
            RecallHQ is available as a hosted pilot. If Slack says the app cannot be installed in your workspace, the app owner needs to
            enable distribution or your admin needs to approve it. The installation button starts OAuth; it does not bypass Slack’s approval
            rules.
          </Note>
          <h2>2. Invite the bot to a channel</h2>
          <p>
            In the channel you want RecallHQ to index, invite <strong>@RecallHQ</strong> using Slack’s Add people action or this command:
          </p>
          <Code>/invite @RecallHQ</Code>
          <p>
            Repeat for each public or private channel you want to include. Installing the app alone does not start indexing every channel.
          </p>
          <h2>3. Check history coverage</h2>
          <Code>/recall status</Code>
          <p>
            Check that the channel appears, then look at history coverage and the embedding backlog. Imports continue in the background; a
            new installation may take time to populate.
          </p>
          <h2>4. Ask a question</h2>
          <Code>/recall ask What has the team decided about the pilot?</Code>
          <p>
            For a quick check, post a specific test fact in the invited channel, wait for indexing, and ask about that fact. Open the
            returned source link to verify it.
          </p>
          <h2>What can be imported?</h2>
          <p>
            Channel text and thread replies, including textual posts from other bots. File contents, personal or group DMs, Slack Connect
            channels, and organization-wide installations are outside the current scope.
          </p>
          <p>
            Slack retention, plan limits, scopes, and admin policy determine how much history is available. Initial imports can take
            substantial time when Slack applies restrictive history and replies limits.
          </p>
        </>
      );
    case 'quickstart':
      return (
        <>
          <h2>Start with a fact you can verify</h2>
          <ol>
            <li>
              <Link href="/docs/installation">Install RecallHQ</Link> and invite <strong>@RecallHQ</strong> to your test channel.
            </li>
            <li>
              Post a message such as <em>“The pilot will run in Seminar Hall B on October 2. Zoya owns the venue booking.”</em>
            </li>
            <li>
              Run <code>/recall status</code> to confirm the channel is indexed. Allow time for live capture and embeddings.
            </li>
            <li>
              Ask <code>/recall ask Who owns the venue booking?</code>
            </li>
            <li>Open the source link and check that the answer matches the original message.</li>
          </ol>
          <h2>Narrow the channel</h2>
          <p>
            Commands default to all ingested channels you currently belong to. Add a channel filter when you want to focus on one
            conversation.
          </p>
          <Code>/recall ask What is included in the pilot? in:#product</Code>
          <h2>Find messages directly</h2>
          <Code>/recall search venue booking in:#ops</Code>
          <p>Search returns excerpts rather than a generated answer. Use it when you want to read the original wording.</p>
          <h2>Catch up after time away</h2>
          <Code>/recall catchup 2026-09-14 2026-09-18 in:#eng</Code>
          <p>Choose dates that contain messages in your workspace. The range is inclusive and limited to 32 days.</p>
          <Note>
            Trying this without installing? The <Link href="/playground">playground</Link> supports ask, search, and catchup over the
            fictional Beacon corpus. The website demo uses /ask, /search, and /catchup; your Slack workspace uses /recall followed by the
            subcommand.
          </Note>
        </>
      );
    case 'commands':
      return (
        <>
          <Note>
            Channel filters use <code>in:#channel</code> in Slack. Defaults are five commands per user per minute and 200 per workspace per
            UTC day; the hosted configuration may vary. The anonymous playground has separate limits.
          </Note>
          {commandDocs.map((command) => (
            <section key={command.name} id={command.name} className={styles.commandDoc}>
              <h2>
                <code>/recall {command.name}</code>
                {command.admin && <span className={styles.adminTag}>ADMIN / OWNER</span>}
              </h2>
              <p>{command.description}</p>
              <Code>{command.syntax}</Code>
              <h3>Example</h3>
              <Code>{command.example}</Code>
            </section>
          ))}
        </>
      );
    case 'permissions':
      return (
        <>
          <h2>Channel membership is the boundary</h2>
          <p>
            The bot indexes only channels it has been invited to. A query can retrieve evidence only from ingested channels the requester
            currently belongs to, including private channels.
          </p>
          <p>
            Membership is checked before retrieval and again before delivery. Changed or deleted evidence suppresses the answer.
            Cross-channel results are never posted publicly; answers and searches are private to the requester.
          </p>
          <h2>What RecallHQ processes</h2>
          <p>
            RecallHQ stores channel text, thread replies, message metadata, and derived search chunks and embeddings. It excludes its own
            output, non-content system events, file contents, DMs, and Slack Connect channels.
          </p>
          <p>
            Retrieved message content is supplied to the configured embedding and generation providers and, when enabled, the reranking
            provider. RecallHQ does not use Slack API data to train models.
          </p>
          <h2>Edits, deletion, and removal</h2>
          <ul>
            <li>Message edits rebuild affected search content.</li>
            <li>Deletion events remove source text and derived chunks.</li>
            <li>
              Confirmed <code>/recall forget #channel</code> disables ingestion and purges indexed channel content.
            </li>
            <li>Bot removal, channel archive or deletion, token revocation, and app uninstall disable access and queue content cleanup.</li>
          </ul>
          <p>
            There is no automatic age expiry for indexed data. Removing content from the running database does not erase pre-existing
            backups. Ask your app owner about the active backup and retention policy before sharing sensitive data.
          </p>
          <h2>A separate public demo</h2>
          <p>
            The Beacon workspace is a fictional dataset. The public demo and playground have anonymous access to that synthetic corpus only.
            They do not accept Slack tokens, read your installation, or retrieve real workspace data.
          </p>
          <Note>
            History coverage depends on what Slack exposes through its APIs. A completed import cannot recover messages hidden by your
            workspace’s retention policy, plan, or admin restrictions.
          </Note>
        </>
      );
    case 'troubleshooting':
      return (
        <>
          <h2>The installation link shows an error</h2>
          <p>
            Check that you selected the intended workspace. Slack may require admin approval, and installation in another workspace requires
            the app owner to enable distribution. If the hosted pilot is unavailable, try again later or ask the app owner to check the
            service.
          </p>
          <h2>My channel is missing</h2>
          <p>
            Invite <strong>@RecallHQ</strong> to that channel and confirm you are a member. Then run <code>/recall status</code>. The bot
            does not discover or ingest every workspace channel automatically.
          </p>
          <h2>Old messages aren’t searchable yet</h2>
          <p>
            Use <code>/recall status</code> to inspect coverage and import errors. Slack can limit history and replies to one request per
            minute per method and workspace, with small pages. Imports can therefore take substantial time.
          </p>
          <p>
            An admin or owner can retry a failed import with <code>/recall sync #channel</code>. Messages unavailable through Slack’s APIs
            cannot be imported.
          </p>
          <h2>A new message is missing</h2>
          <p>
            Live capture and embedding run asynchronously. Check the backlog in <code>/recall status</code> and wait for indexing. Ensure
            the message is channel text, rather than a file attachment or DM.
          </p>
          <h2>The answer says there is not enough evidence</h2>
          <p>
            Try a more specific question or use <code>/recall search</code> to inspect the original messages. Check your channel filter and
            history coverage. RecallHQ may suppress an answer when its evidence was edited, deleted, or became inaccessible.
          </p>
          <h2>The recap is partial</h2>
          <p>
            Catch-up ranges are capped at 32 days. Large message counts, unusually long messages, context limits, or unfinished history
            imports trigger a coverage notice. Narrow the dates or channel to make the recap more complete.
          </p>
          <h2>The playground has reached its limit</h2>
          <p>
            Anonymous demo limits are three commands per minute and 20 per day per visitor IP, with a shared daily cap. Wait before
            retrying. You can still <Link href={DEMO_URL}>browse the synthetic archive</Link>.
          </p>
        </>
      );
  }
}

type Props = { params: Promise<{ slug?: string[] }> };
function pageKey(slug?: string[]): keyof typeof pages {
  if (!slug?.length) return 'introduction';
  if (slug.length !== 1 || !Object.hasOwn(pages, slug[0]) || slug[0] === 'introduction') notFound();
  return slug[0] as keyof typeof pages;
}

export function generateStaticParams() {
  return [
    { slug: [] },
    ...Object.keys(pages)
      .filter((key) => key !== 'introduction')
      .map((key) => ({ slug: [key] })),
  ];
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const key = pageKey((await params).slug);
  return { title: `${pages[key][0]} | RecallHQ`, description: pages[key][1] };
}

export default async function DocsPage({ params }: Props) {
  const key = pageKey((await params).slug);
  const index = key === 'introduction' ? 0 : docsLinks.findIndex((link) => link.href === `/docs/${key}`);
  return (
    <SiteShell active="docs">
      <div className={styles.docsLayout}>
        <aside className={styles.docsSidebar}>
          <p className={styles.sidebarLabel}>Documentation</p>
          <nav className={styles.docsNav} aria-label="Documentation">
            {docsLinks.map((link, i) => (
              <Link key={link.href} href={link.href} aria-current={index === i ? 'page' : undefined}>
                {link.label}
              </Link>
            ))}
          </nav>
          <div className={styles.sidebarTry}>
            <p className={styles.sidebarLabel}>Try RecallHQ</p>
            <nav className={styles.docsNav} aria-label="Try RecallHQ">
              <Link href="/playground">Synthetic playground ↗</Link>
              <Link href={DEMO_URL}>Beacon workspace demo ↗</Link>
            </nav>
          </div>
        </aside>
        <main id="main-content" className={styles.docsArticle}>
          <p className={styles.breadcrumbs}>Docs / {pages[key][0]}</p>
          <h1>{pages[key][0]}</h1>
          <p className={styles.docsIntro}>{pages[key][1]}</p>
          <div className={styles.docsBody}>
            <Documentation page={key} />
          </div>
          <nav className={styles.docsNext} aria-label="Adjacent documentation pages">
            {index > 0 ? <Link href={docsLinks[index - 1].href}>← {docsLinks[index - 1].label}</Link> : <span />}
            {index < docsLinks.length - 1 && <Link href={docsLinks[index + 1].href}>{docsLinks[index + 1].label} →</Link>}
          </nav>
        </main>
      </div>
    </SiteShell>
  );
}
