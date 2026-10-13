'use client';

import { ArrowUpRight, MessageSquareText, Search, Terminal } from 'lucide-react';
import Link from 'next/link';
import { type FormEvent, useState } from 'react';

import { PUBLIC_API_URL } from '@/lib/public-api';

import styles from './site.module.css';

type Source = { id: string; channel: string; author_name: string; text: string; created_at: string };
type Result = { kind: 'answer'; answer: string; sources: Source[] } | { kind: 'search'; hits: Source[] };
type Command = 'ask' | 'search' | 'catchup';
const examples = [
  { label: 'Why did the team choose Postgres?', question: 'Why did the team switch from MongoDB to Postgres for the pilot?' },
  { label: 'What does a successful pilot look like?', question: 'What is included in the pilot, and how will success be measured?' },
  { label: 'Who owns the venue booking?', question: 'Where is the pilot being held, and who owns the venue booking?' },
];

function SourceCard({ source }: { source: Source }) {
  return (
    <Link
      className={styles.sourceResult}
      href={`/workspace/beacon/channel/${encodeURIComponent(source.channel)}?message=${encodeURIComponent(source.id)}`}
    >
      <div className={styles.sourceMeta}>
        <strong># {source.channel}</strong>
        <span>{source.author_name}</span>
        <time dateTime={source.created_at}>
          {new Date(source.created_at).toLocaleDateString('en-US', {
            month: 'short',
            day: 'numeric',
            year: 'numeric',
            timeZone: 'Asia/Kolkata',
          })}
        </time>
        <ArrowUpRight size={13} aria-hidden="true" />
      </div>
      <p>{source.text}</p>
    </Link>
  );
}

export function BeaconPlayground() {
  const [command, setCommand] = useState<Command>('ask');
  const [question, setQuestion] = useState(examples[0].question);
  const [start, setStart] = useState('2026-09-14');
  const [end, setEnd] = useState('2026-09-18');
  const [channel, setChannel] = useState('eng');
  const [result, setResult] = useState<Result | null>(null);
  const [submitted, setSubmitted] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const input = command === 'catchup' ? `/catchup ${start} ${end}${channel ? ` #${channel}` : ''}` : `/${command} ${question.trim()}`;
  const invalidRange = !start || !end || end < start || (Date.parse(end) - Date.parse(start)) / 86400000 > 31;
  const canSubmit = !loading && (command === 'catchup' ? !invalidRange : !!question.trim());

  async function execute(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canSubmit) return;
    setLoading(true);
    setError('');
    setResult(null);
    setSubmitted(input);
    try {
      // This is the existing anonymous, synthetic-only endpoint. No Slack credentials are sent.
      const response = await fetch(`${PUBLIC_API_URL}/commands`, {
        method: 'POST',
        credentials: 'omit',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ input }),
        signal: AbortSignal.timeout(90000),
      });
      const payload = await response.json().catch(() => null);
      if (!response.ok) {
        if (response.status === 429)
          throw new Error(
            'The public demo limit has been reached. Wait a minute before retrying. Daily limits may require waiting until tomorrow; the archive is still available.',
          );
        throw new Error(
          typeof payload?.detail === 'string' ? payload.detail : 'The demo service is temporarily unavailable. Please try again.',
        );
      }
      if (
        !payload ||
        !(
          (payload.kind === 'answer' && typeof payload.answer === 'string' && Array.isArray(payload.sources)) ||
          (payload.kind === 'search' && Array.isArray(payload.hits))
        )
      )
        throw new Error('The demo returned an unexpected response. Please try again.');
      setResult(payload as Result);
    } catch (failure) {
      setError(
        failure instanceof Error && failure.name === 'TimeoutError'
          ? 'This request took too long. Try a shorter question or a smaller date range.'
          : failure instanceof TypeError
            ? 'Unable to reach the demo service. Check your connection and try again.'
            : failure instanceof Error
              ? failure.message
              : 'Unable to run this command. Please try again.',
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <div className={styles.playgroundGrid}>
        <form className={styles.commandForm} onSubmit={execute}>
          <div className={styles.commandTabs} aria-label="Choose a demo command">
            {(['ask', 'search', 'catchup'] as const).map((name) => (
              <button
                key={name}
                type="button"
                aria-pressed={command === name}
                disabled={loading}
                onClick={() => {
                  setCommand(name);
                  setError('');
                }}
              >
                /{name}
              </button>
            ))}
          </div>
          {command === 'catchup' ? (
            <>
              <label htmlFor="start-date">From</label>
              <input
                id="start-date"
                type="date"
                value={start}
                onChange={(event) => setStart(event.target.value)}
                required
                disabled={loading}
              />
              <label htmlFor="end-date">Through</label>
              <input id="end-date" type="date" value={end} onChange={(event) => setEnd(event.target.value)} required disabled={loading} />
              <label htmlFor="channel">Channel</label>
              <select id="channel" value={channel} onChange={(event) => setChannel(event.target.value)} disabled={loading}>
                <option value="">All demo channels</option>
                {['eng', 'product', 'ops', 'build-help', 'random'].map((name) => (
                  <option key={name} value={name}>
                    # {name}
                  </option>
                ))}
              </select>
              {invalidRange && (
                <p className={styles.formHint} role="alert">
                  Choose an inclusive range of 1–32 days, with the end date on or after the start.
                </p>
              )}
            </>
          ) : (
            <>
              <label htmlFor="question">{command === 'ask' ? 'Your question' : 'Search terms'}</label>
              <textarea
                id="question"
                value={question}
                maxLength={1100}
                onChange={(event) => setQuestion(event.target.value)}
                placeholder={command === 'ask' ? 'What did the team decide?' : 'pilot venue booking'}
                required
                disabled={loading}
              />
            </>
          )}
          <div className={styles.commandPreview} aria-label="Command preview">
            {input}
          </div>
          <button className={styles.primaryButton} type="submit" disabled={!canSubmit}>
            {loading ? 'Searching Beacon…' : 'Run command'}
            <Terminal size={14} aria-hidden="true" />
          </button>
          <p className={styles.formHint}>
            Live requests · 3 per minute, 20 per day per visitor IP.
            <br />
            The public demo also has a shared daily limit.
          </p>
          <p className={styles.exampleLabel}>{command === 'catchup' ? 'About this archive' : 'Try a question'}</p>
          {command === 'catchup' ? (
            <p className={styles.formHint}>
              Beacon’s fictional campus pilot conversations span August–September 2026. Demo dates use Asia/Kolkata.
            </p>
          ) : (
            <div className={styles.examples}>
              {examples.map((example) => (
                <button type="button" disabled={loading} key={example.label} onClick={() => setQuestion(example.question)}>
                  {example.label} ↗
                </button>
              ))}
            </div>
          )}
        </form>
        <section className={styles.output} aria-label="Command result" aria-busy={loading}>
          <div className={styles.outputHeader}>
            Response<span>{loading ? 'SEARCHING' : result ? 'LIVE RESULT' : 'BEACON / SYNTHETIC'}</span>
          </div>
          <div aria-live="polite" aria-atomic="true">
            {loading ? (
              <div className={styles.emptyOutput} role="status">
                <div>
                  <Search size={26} aria-hidden="true" />
                  <h2>Finding the conversation…</h2>
                  <p>RecallHQ is searching the synthetic archive. This can take a little time.</p>
                </div>
              </div>
            ) : error ? (
              <div className={styles.error} role="alert">
                <strong>Couldn’t run this command</strong>
                {error}
                <p className="mt-3">
                  <Link href="/docs/troubleshooting" className="underline">
                    Troubleshooting
                  </Link>{' '}
                  ·{' '}
                  <Link href="/workspace/beacon/channel/eng" className="underline">
                    Browse the archive
                  </Link>
                </p>
              </div>
            ) : result ? (
              <>
                <p className={styles.formHint}>
                  Ran: <code>{submitted}</code>
                </p>
                {result.kind === 'answer' ? (
                  <>
                    <p className={styles.answer}>{result.answer}</p>
                    <p className={styles.sourcesLabel}>
                      {result.sources.length ? `${result.sources.length} supporting sources` : 'No supporting sources returned'}
                    </p>
                    {result.sources.map((source) => (
                      <SourceCard key={source.id} source={source} />
                    ))}
                  </>
                ) : (
                  <>
                    <p className={styles.sourcesLabel}>{result.hits.length} matching messages</p>
                    {result.hits.length ? (
                      result.hits.map((source) => <SourceCard key={source.id} source={source} />)
                    ) : (
                      <p className={styles.answer}>No matching messages. Try different terms or a broader question.</p>
                    )}
                  </>
                )}
              </>
            ) : (
              <div className={styles.emptyOutput}>
                <div>
                  <MessageSquareText size={28} aria-hidden="true" />
                  <h2>Ask the team’s memory.</h2>
                  <p>Run a command to see a live answer and the conversations behind it. Source links open in the Beacon demo.</p>
                </div>
              </div>
            )}
          </div>
        </section>
      </div>
      <div className={styles.playgroundInfo}>
        <p>Fictional team. Real retrieval. This playground never searches Slack workspace data.</p>
        <Link href="/docs/commands" className={styles.textLink}>
          Slack uses /recall + subcommand ↗
        </Link>
      </div>
    </>
  );
}
