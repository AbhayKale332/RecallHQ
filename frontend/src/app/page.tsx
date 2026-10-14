import { ArrowRight, ArrowUpRight, BadgeCheck, CalendarRange, FlaskConical, Lock, Search, ShieldCheck } from 'lucide-react';
import Link from 'next/link';
import { FaGithub } from 'react-icons/fa6';

import { HowItWorks } from '@/components/pipeline-diagram';
import { InstallLink, SiteShell } from '@/components/site-shell';
import styles from '@/components/site.module.css';
import { DEMO_COMMANDS } from '@/lib/demo-answers';
import { GITHUB_URL } from '@/lib/docs-nav';
import { DEMO_URL, PUBLIC_BASE_PATH } from '@/lib/public-api';

const features = [
  {
    icon: BadgeCheck,
    title: 'Cited, or not shown',
    body: (
      <>
        Every claim cites a message ID like <code>[slack:…]</code>. If the model cites anything it wasn’t given, you get “I couldn’t verify
        an answer” instead of a guess.
      </>
    ),
  },
  {
    icon: Search,
    title: 'Finds the exact error code',
    body: (
      <>
        Vector search catches paraphrases; keyword search catches <code>28P01</code>. Both run on every question and are fused by rank.
      </>
    ),
  },
  {
    icon: CalendarRange,
    title: 'Catch up on a date range',
    body: 'Recap up to 32 days of a channel as updates, decisions, blockers, and next steps. Partial coverage is flagged, not hidden.',
  },
  {
    icon: Lock,
    title: 'Only channels you’re in',
    body: 'Membership is checked before retrieval and again before delivery. Replies are private to you, and link back to Slack.',
  },
  {
    icon: ShieldCheck,
    title: 'Isolation in the database',
    body: 'Postgres row-level security scopes every query to one workspace and your channels. Bot tokens are stored encrypted.',
  },
  {
    icon: FlaskConical,
    title: 'Measured in the open',
    body: '44 hand-labeled questions over a synthetic team archive. Results are published as they are run, including what isn’t measured yet.',
  },
];

export default function HomePage() {
  const example = DEMO_COMMANDS.eng;
  return (
    <SiteShell>
      <main id="main-content" className={styles.container}>
        <section className={styles.hero}>
          <div>
            <p className={styles.eyebrow}>
              <span className={styles.eyebrowDot} /> A Slack bot for your team’s memory
            </p>
            <h1>
              Ask your team chat. <span>Get grounded, cited answers.</span>
            </h1>
            <p className={styles.lead}>
              RecallHQ reads the channels you invite it to. Ask why a decision was made or what you missed, and get a short answer that
              links to the exact messages behind it.
            </p>
            <div className={styles.actions}>
              <InstallLink label="Install in Slack" />
              <Link href="/playground" className={styles.secondaryButton}>
                Try the playground <ArrowRight size={16} aria-hidden="true" />
              </Link>
              <Link href={DEMO_URL} className={styles.secondaryButton}>
                Demo
              </Link>
              <a href={GITHUB_URL} className={styles.secondaryButton}>
                <FaGithub size={16} aria-hidden="true" /> GitHub
              </a>
            </div>
            <p className={styles.finePrint}>
              The playground and demo use a fictional team’s archive. No sign-in. <Link href="/docs/self-hosting">Self-host it</Link>{' '}
              instead.
            </p>
          </div>
          <div className={styles.conversation} aria-label="Recorded example from the synthetic Beacon archive">
            <div className={styles.conversationHeader}>
              <strong># eng</strong>
              <span>Beacon · synthetic demo</span>
            </div>
            <div className={styles.chatLine}>
              <div className={styles.chatAvatar} aria-hidden="true">
                Y
              </div>
              <div>
                <p className={styles.chatName}>You</p>
                <p className={styles.chatCommand}>/recall ask Why did the team switch from MongoDB to Postgres for the pilot?</p>
              </div>
            </div>
            <div className={`${styles.chatLine} ${styles.botLine}`}>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={`${PUBLIC_BASE_PATH}/recallhq-bot.png`}
                alt=""
                width={33}
                height={33}
                className={`${styles.chatAvatar} ${styles.botAvatar}`}
              />
              <div>
                <p className={styles.chatName}>
                  RecallHQ <span>APP</span>
                </p>
                <p className={styles.chatAnswer}>
                  {example.result.answer}
                  {example.result.sources.map((_, i) => (
                    <span key={i} className={styles.cite}>
                      {i + 1}
                    </span>
                  ))}
                </p>
                {example.result.sources.map((source, i) => (
                  <Link
                    key={source.id}
                    className={styles.sourcePill}
                    href={`/workspace/beacon/channel/${source.channel}?message=${encodeURIComponent(source.id)}`}
                  >
                    <b>{i + 1}</b> #{source.channel} · {source.author_name} · Sep {new Date(source.created_at).getDate()}
                  </Link>
                ))}
              </div>
            </div>
            <div className={styles.conversationFooter}>
              <span>Recorded answer · fictional team conversations</span>
              <Link href="/playground">Ask your own question ↗</Link>
            </div>
          </div>
        </section>

        <div className={styles.stackStrip} aria-label="Built with">
          <strong>Under the hood</strong>
          <span>Postgres + pgvector</span>
          <span>Full-text search</span>
          <span>Reciprocal rank fusion</span>
          <span>OpenRouter Decisions rerank</span>
          <span>gpt-5.4-mini</span>
        </div>

        <section className={styles.section} aria-labelledby="how-title">
          <div className={styles.sectionTitle}>
            <div>
              <p className={styles.eyebrow}>How it works</p>
              <h2 id="how-title">From a Slack thread to an answer you can check.</h2>
            </div>
            <Link className={styles.textLink} href="/docs/architecture">
              Read the architecture <ArrowRight size={15} aria-hidden="true" />
            </Link>
          </div>
          <HowItWorks />
        </section>

        <section className={styles.section} aria-labelledby="features-title">
          <div className={styles.sectionTitle}>
            <div>
              <p className={styles.eyebrow}>Why teams use it</p>
              <h2 id="features-title">Less scrolling. Answers you can trust.</h2>
            </div>
            <Link className={styles.textLink} href="/docs/evaluation">
              See the evaluation <ArrowRight size={15} aria-hidden="true" />
            </Link>
          </div>
          <div className={styles.featureGrid}>
            {features.map(({ icon: Icon, title, body }) => (
              <div key={title} className={styles.feature}>
                <Icon size={20} aria-hidden="true" />
                <h3>{title}</h3>
                <p>{body}</p>
              </div>
            ))}
          </div>
        </section>

        <section className={styles.section} aria-labelledby="commands-title">
          <div className={styles.sectionTitle}>
            <div>
              <p className={styles.eyebrow}>One command</p>
              <h2 id="commands-title">Everything starts with /recall.</h2>
            </div>
            <Link className={styles.textLink} href="/docs/commands">
              All commands <ArrowRight size={15} aria-hidden="true" />
            </Link>
          </div>
          <div className={styles.commandList}>
            {[
              ['ask', 'Why did we change the data model? Get a grounded answer.'],
              ['search', 'Find the original conversation, even when you forget the wording.'],
              ['catchup', 'Turn a date range into updates, decisions, blockers, and next steps.'],
              ['summarize', 'Paste a Slack message link to get the indexed thread’s summary.'],
            ].map(([command, description]) => (
              <Link className={styles.commandRow} key={command} href={`/docs/commands#${command}`}>
                <code>/recall {command}</code>
                <p>{description}</p>
                <ArrowUpRight size={14} aria-hidden="true" />
              </Link>
            ))}
          </div>
          <div className={styles.startBanner}>
            <div>
              <h3>Try it before adding it to Slack.</h3>
              <p>The Beacon playground uses a fictional campus pilot team. No account needed.</p>
            </div>
            <div>
              <Link href="/playground" className={styles.primaryButton}>
                Open playground <ArrowRight size={15} aria-hidden="true" />
              </Link>
              <Link href="/docs" className={styles.secondaryButton}>
                Read the docs
              </Link>
            </div>
          </div>
        </section>
      </main>
    </SiteShell>
  );
}
