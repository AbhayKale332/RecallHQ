import { ArrowRight, ArrowUpRight } from 'lucide-react';
import Link from 'next/link';

import { InstallLink, SiteShell } from '@/components/site-shell';
import styles from '@/components/site.module.css';
import { DEMO_COMMANDS } from '@/lib/demo-answers';
import { DEMO_URL, PUBLIC_BASE_PATH } from '@/lib/public-api';

export default function HomePage() {
  const example = DEMO_COMMANDS.eng;
  return (
    <SiteShell>
      <main id="main-content" className={styles.container}>
        <section className={styles.hero}>
          <div>
            <p className={styles.eyebrow}>
              <span className={styles.eyebrowDot} /> Your team’s memory, in Slack
            </p>
            <h1>
              The answer is
              <br />
              in your chat.
              <br />
              <span>Recall it.</span>
            </h1>
            <p className={styles.lead}>
              Find the decision, catch up on the conversation, and get back to work. Ask RecallHQ in plain English. Every answer links back
              to its sources.
            </p>
            <div className={styles.actions}>
              <InstallLink />
              <Link href={DEMO_URL} className={styles.secondaryButton}>
                Explore the demo <ArrowRight size={16} aria-hidden="true" />
              </Link>
            </div>
            <p className={styles.finePrint}>Invite it to a channel. Your workspace permissions stay in control.</p>
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
                <p className={styles.chatAnswer}>{example.result.answer}</p>
                {example.result.sources.map((source) => (
                  <Link
                    key={source.id}
                    className={styles.sourcePill}
                    href={`/workspace/beacon/channel/${source.channel}?message=${encodeURIComponent(source.id)}`}
                  >
                    # {source.channel} · Priya Shah · Sep {new Date(source.created_at).getDate()}
                  </Link>
                ))}
              </div>
            </div>
            <div className={styles.conversationFooter}>
              <span>Recorded answer · fictional team conversations</span>
              <Link href="/playground">Try your own question ↗</Link>
            </div>
          </div>
        </section>
        <section className={styles.workflow} aria-label="How RecallHQ works">
          <div>
            <h2>
              <span>01</span>Invite to a channel
            </h2>
            <p>RecallHQ imports available history and captures new conversations.</p>
          </div>
          <div>
            <h2>
              <span>02</span>Ask what you need
            </h2>
            <p>Find an answer, search messages, or recap a date range.</p>
          </div>
          <div>
            <h2>
              <span>03</span>Check the source
            </h2>
            <p>Private replies include links to the messages behind the answer.</p>
          </div>
        </section>
        <section className={styles.section}>
          <div className={styles.sectionTitle}>
            <div>
              <p className={styles.eyebrow}>One command. Your team’s context.</p>
              <h2>Less scrolling. More knowing.</h2>
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
            <Link href="/playground" className={styles.secondaryButton}>
              Open playground <ArrowRight size={15} aria-hidden="true" />
            </Link>
          </div>
        </section>
      </main>
    </SiteShell>
  );
}
