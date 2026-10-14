import { BookOpen, FlaskConical, Network, Play, Rocket, ShieldCheck, Terminal, Wrench } from 'lucide-react';
import type { Metadata } from 'next';
import Link from 'next/link';
import { notFound } from 'next/navigation';
import { FaGithub } from 'react-icons/fa6';

import { ArchitectureDoc } from '@/components/docs/architecture';
import { Code, Note } from '@/components/docs/docs-ui';
import { EvaluationDoc } from '@/components/docs/evaluation';
import { SelfHostingDoc } from '@/components/docs/self-hosting';
import { SlackBotDoc } from '@/components/docs/slack-bot';
import { HowItWorks } from '@/components/pipeline-diagram';
import { InstallLink, SiteShell } from '@/components/site-shell';
import styles from '@/components/site.module.css';
import { commandDocs } from '@/lib/commands';
import { GITHUB_URL, docsHref, docsPages, docsSections } from '@/lib/docs-nav';
import { DEMO_URL } from '@/lib/public-api';

function Overview() {
  return (
    <>
      <h2>Start here</h2>
      <div className={styles.docsCards}>
        <Link href="/docs/installation">
          <Rocket size={18} aria-hidden="true" />
          <strong>Add RecallHQ to Slack →</strong>
          <span>Authorize the hosted app, invite it to a channel, ask your first question.</span>
        </Link>
        <Link href="/docs/self-hosting">
          <Wrench size={18} aria-hidden="true" />
          <strong>Run it locally →</strong>
          <span>Postgres + pgvector in Docker, the synthetic corpus, the API, and tests.</span>
        </Link>
        <Link href="/docs/architecture">
          <Network size={18} aria-hidden="true" />
          <strong>Model architecture →</strong>
          <span>Chunking, hybrid retrieval, reranking, cited generation, and isolation.</span>
        </Link>
        <Link href="/docs/evaluation">
          <FlaskConical size={18} aria-hidden="true" />
          <strong>Evaluations →</strong>
          <span>44 labeled questions, metric definitions, and what has been measured so far.</span>
        </Link>
        <Link href="/docs/commands">
          <Terminal size={18} aria-hidden="true" />
          <strong>Command reference →</strong>
          <span>ask, search, catchup, summarize, decisions, and admin controls.</span>
        </Link>
        <Link href="/docs/permissions">
          <ShieldCheck size={18} aria-hidden="true" />
          <strong>Permissions & data →</strong>
          <span>Channel membership, what is processed, and how deletion works.</span>
        </Link>
      </div>

      <h2>How an answer is made</h2>
      <HowItWorks columns={3} columnsMd={2} />

      <h2>Find the context behind the conversation</h2>
      <p>
        Your team has already discussed the plan, the tradeoff, and the fix. RecallHQ helps you find that context without remembering the
        exact wording or who posted it.
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
      <p>
        Add RecallHQ to your workspace and invite it into selected public or private channels. It imports the history Slack makes available
        and indexes new messages and thread replies. Commands search ingested channels you belong to. Your membership is checked before
        retrieval and again before the answer is delivered. Replies stay private and link back to Slack.
      </p>
      <Note>
        The public Beacon demo and playground use synthetic conversations only. Installing RecallHQ never makes your Slack messages
        available on this website.
      </Note>
    </>
  );
}

function Documentation({ page }: { page: string }) {
  switch (page) {
    case '':
      return <Overview />;
    case 'architecture':
      return <ArchitectureDoc />;
    case 'evaluation':
      return <EvaluationDoc />;
    case 'self-hosting':
      return <SelfHostingDoc />;
    case 'slack-bot':
      return <SlackBotDoc />;
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
            rules. To run your own copy instead, see <Link href="/docs/slack-bot">Slack bot setup</Link>.
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
              <Code label="Syntax">{command.syntax}</Code>
              <Code label="Example">{command.example}</Code>
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
            Cross-channel results are never posted publicly; answers and searches are private to the requester. The database enforces the
            same boundary with row-level security; see <Link href="/docs/architecture#isolation">tenant isolation</Link>.
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
            history coverage. RecallHQ may suppress an answer when its evidence was edited, deleted, or became inaccessible, or when the
            model cites a message it was not given.
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
    default:
      return null;
  }
}

type Props = { params: Promise<{ slug?: string[] }> };
function pageIndex(slug?: string[]): number {
  if (!slug?.length) return 0;
  const index = slug.length === 1 && slug[0] ? docsPages.findIndex((page) => page.slug === slug[0]) : -1;
  if (index < 0) notFound();
  return index;
}

export function generateStaticParams() {
  return docsPages.map((page) => ({ slug: page.slug ? [page.slug] : [] }));
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const page = docsPages[pageIndex((await params).slug)];
  return { title: `${page.slug ? page.title : 'Documentation'} | RecallHQ`, description: page.description };
}

function SidebarGroups({ current }: { current: string }) {
  return (
    <>
      {docsSections.map((section) => (
        <div key={section.title} className={styles.sidebarGroup}>
          <p className={styles.sidebarLabel}>{section.title}</p>
          <nav className={styles.docsNav} aria-label={section.title}>
            {section.pages.map((page) => (
              <Link key={page.slug} href={docsHref(page.slug)} aria-current={page.slug === current ? 'page' : undefined}>
                {page.label}
              </Link>
            ))}
          </nav>
        </div>
      ))}
    </>
  );
}

export default async function DocsPage({ params }: Props) {
  const index = pageIndex((await params).slug);
  const page = docsPages[index];
  const section = docsSections.find((group) => group.pages.includes(page));
  const previous = docsPages[index - 1];
  const next = docsPages[index + 1];
  return (
    <SiteShell active="docs">
      <div className={styles.docsLayout}>
        <aside className={styles.docsSidebar}>
          <SidebarGroups current={page.slug} />
          <div className={styles.sidebarTry}>
            <p className={styles.sidebarLabel}>Try RecallHQ</p>
            <nav className={styles.docsNav} aria-label="Try RecallHQ">
              <Link href="/playground">Synthetic playground ↗</Link>
              <Link href={DEMO_URL}>Beacon workspace demo ↗</Link>
              <a href={GITHUB_URL}>Source on GitHub ↗</a>
            </nav>
          </div>
        </aside>
        <main id="main-content" className={styles.docsArticle}>
          <details className={styles.mobileDocsNav}>
            <summary>
              Documentation <span>{page.label} ▾</span>
            </summary>
            <SidebarGroups current={page.slug} />
          </details>
          {page.slug ? (
            <>
              <p className={styles.breadcrumbs}>
                Docs / {section?.title} / {page.label}
              </p>
              <h1>{page.title}</h1>
              <p className={styles.docsIntro}>{page.description}</p>
            </>
          ) : (
            <header className={styles.docsHero}>
              <p className={styles.eyebrow}>
                <BookOpen size={14} aria-hidden="true" /> Documentation
              </p>
              <h1>Ask your team chat. Get grounded, cited answers.</h1>
              <p className={styles.docsIntro}>
                RecallHQ is a Slack bot that answers questions from your team’s own conversations. It searches the channels you can see, and
                every answer links to the messages it came from.
              </p>
              <div className={styles.actions}>
                <InstallLink />
                <Link href="/playground" className={styles.secondaryButton}>
                  <Play size={15} aria-hidden="true" /> Playground
                </Link>
                <Link href={DEMO_URL} className={styles.secondaryButton}>
                  Demo workspace
                </Link>
                <a href={GITHUB_URL} className={styles.secondaryButton}>
                  <FaGithub size={15} aria-hidden="true" /> GitHub
                </a>
              </div>
            </header>
          )}
          <div className={styles.docsBody}>
            <Documentation page={page.slug} />
          </div>
          <nav className={styles.docsNext} aria-label="Adjacent documentation pages">
            {previous ? (
              <Link href={docsHref(previous.slug)}>
                <span>Previous</span>← {previous.label}
              </Link>
            ) : (
              <span />
            )}
            {next && (
              <Link href={docsHref(next.slug)}>
                <span>Next</span>
                {next.label} →
              </Link>
            )}
          </nav>
        </main>
      </div>
    </SiteShell>
  );
}
