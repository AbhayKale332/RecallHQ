'use client';

import { format } from 'date-fns';
import { Hash, Loader, MessageSquareText, X } from 'lucide-react';
import dynamic from 'next/dynamic';
import Link from 'next/link';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';

import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { useChatSession } from '@/components/chat-session-provider';
import { ThreadBar } from '@/components/thread-bar';
import { DEMO_COMMANDS } from '@/lib/demo-answers';

const Editor = dynamic(() => import('@/components/editor'), { ssr: false });
const API = process.env.NEXT_PUBLIC_API_URL || 'https://recova.indiasouthcentral.cloudapp.azure.com/recallhq/api';

type Channel = { id: string; name: string; messages: number };
type ChatMessage = {
  id: string;
  channel: string;
  author: string;
  author_name: string;
  text: string;
  created_at: string;
  thread_root_id: string | null;
  reply_count?: number;
  last_reply_at?: string | null;
};
type CommandResult =
  | { kind: 'answer'; answer: string; sources: readonly ChatMessage[] }
  | { kind: 'search'; hits: ChatMessage[] };

function sourceUrl(message: Pick<ChatMessage, 'id' | 'channel'>) {
  return `/workspace/beacon/channel/${message.channel}?message=${encodeURIComponent(message.id)}`;
}

function MessageCard({ message, onThread, highlighted = false }: { message: ChatMessage; onThread?: (id: string) => void; highlighted?: boolean }) {
  return (
    <article id={message.id} className={`group flex gap-3 px-5 py-2 hover:bg-gray-100/60 ${highlighted ? 'bg-amber-50' : ''}`}>
      <Avatar className="mt-0.5 size-9 shrink-0">
        <AvatarFallback>{message.author_name.charAt(0).toUpperCase()}</AvatarFallback>
      </Avatar>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-baseline gap-2">
          <strong className="text-sm">{message.author_name}</strong>
          <time className="text-xs text-muted-foreground" dateTime={message.created_at}>
            {format(new Date(message.created_at), 'MMM d, yyyy · h:mm a')}
          </time>
        </div>
        <p className="whitespace-pre-wrap break-words text-sm leading-[22px]">{message.text}</p>
        {!!message.reply_count && onThread && (
          <ThreadBar count={message.reply_count} name={message.author_name} timestamp={new Date(message.last_reply_at || message.created_at).getTime()} onClick={() => onThread(message.id)} />
        )}
      </div>
    </article>
  );
}

async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`${API}${path}`);
  if (!response.ok) throw new Error(`Unable to load chat (${response.status})`);
  return response.json();
}

export function PublicChat() {
  const params = useParams<{ channelId: string }>();
  const searchParams = useSearchParams();
  const router = useRouter();
  const channelId = params.channelId;
  const demoCommand = DEMO_COMMANDS[channelId as keyof typeof DEMO_COMMANDS];
  const sourceId = searchParams.get('message');
  const [channels, setChannels] = useState<Channel[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const { entries, setEntries } = useChatSession();
  const [source, setSource] = useState<ChatMessage | null>(null);
  const [thread, setThread] = useState<ChatMessage[] | null>(null);
  const [draft, setDraft] = useState<string>(demoCommand?.input || '/ask What has the team discussed in this channel?');
  const [editorKey, setEditorKey] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState('');
  const bottomRef = useRef<HTMLDivElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const scrollSnapshot = useRef<{ height: number; top: number } | null>(null);
  const historyRequest = useRef(false);
  const channelGeneration = useRef(0);

  useEffect(() => {
    apiGet<Channel[]>('/channels').then(setChannels).catch((err) => setError(err.message));
  }, []);

  useEffect(() => {
    let active = true;
    channelGeneration.current += 1;
    historyRequest.current = false;
    scrollSnapshot.current = null;
    setLoadingMore(false);
    setDraft(demoCommand?.input || '/ask What has the team discussed in this channel?');
    setEditorKey((key) => key + 1);
    setLoading(true);
    setMessages([]);
    setNextCursor(null);
    setThread(null);
    apiGet<{ items: ChatMessage[]; next_cursor: string | null }>(`/messages?channel=${encodeURIComponent(channelId)}`)
      .then((page) => {
        if (!active) return;
        setMessages(page.items.reverse());
        setNextCursor(page.next_cursor);
      })
      .catch((err) => active && setError(err.message))
      .finally(() => active && setLoading(false));
    return () => { active = false; };
  }, [channelId, demoCommand]);

  useEffect(() => {
    if (!sourceId) {
      setSource(null);
      return;
    }
    let active = true;
    apiGet<ChatMessage>(`/messages/${encodeURIComponent(sourceId)}`)
      .then((message) => active && setSource(message))
      .catch((err) => active && setError(err.message));
    return () => { active = false; };
  }, [sourceId]);

  useEffect(() => {
    if (!loading && !sourceId) bottomRef.current?.scrollIntoView({ behavior: 'instant' });
  }, [loading, channelId, sourceId]);

  useLayoutEffect(() => {
    const container = scrollRef.current;
    const snapshot = scrollSnapshot.current;
    if (container && snapshot) {
      container.scrollTop = snapshot.top + container.scrollHeight - snapshot.height;
      scrollSnapshot.current = null;
    }
  }, [messages]);

  const loadMore = useCallback(async () => {
    if (!nextCursor || loading || historyRequest.current) return;
    const generation = channelGeneration.current;
    historyRequest.current = true;
    setLoadingMore(true);
    try {
      const page = await apiGet<{ items: ChatMessage[]; next_cursor: string | null }>(`/messages?channel=${encodeURIComponent(channelId)}&before=${encodeURIComponent(nextCursor)}`);
      if (generation !== channelGeneration.current) return;
      const container = scrollRef.current;
      if (container) scrollSnapshot.current = { height: container.scrollHeight, top: container.scrollTop };
      setMessages((previous) => [...page.items.reverse(), ...previous]);
      setNextCursor(page.next_cursor);
    } catch (err) {
      if (generation === channelGeneration.current) setError(err instanceof Error ? err.message : 'Unable to load messages');
    } finally {
      if (generation === channelGeneration.current) {
        historyRequest.current = false;
        setLoadingMore(false);
      }
    }
  }, [channelId, nextCursor, loading]);

  const openThread = async (rootId: string) => {
    try {
      setThread(await apiGet<ChatMessage[]>(`/threads/${encodeURIComponent(rootId)}`));
      setSource(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to load thread');
    }
  };

  const send = async ({ body }: { body: string; image: File | null }) => {
    // Quill adds one required final newline. Preserve all user edits for the exact match.
    const rawValue = (JSON.parse(body).ops as { insert?: string }[]).map((op) => op.insert || '').join('').replace(/\n$/, '');
    const value = rawValue.trim();
    if (!value) return;
    const stamp = new Date().toISOString();
    setEntries((previous) => [...previous, { id: crypto.randomUUID(), channel: channelId, kind: 'visitor', text: value, created_at: stamp }]);
    setDraft('');
    setEditorKey((key) => key + 1);
    if (!value.startsWith('/')) return;
    setSending(true);
    try {
      let command: CommandResult;
      if (rawValue === demoCommand?.input) {
        command = demoCommand.result;
      } else {
        const response = await fetch(`${API}/commands`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ input: value }),
        });
        const result = await response.json();
        if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : 'Command failed');
        command = result as CommandResult;
      }
      setEntries((previous) => [...previous, {
        id: crypto.randomUUID(), channel: channelId, kind: 'assistant',
        text: command.kind === 'answer' ? command.answer : `${command.hits.length} matching messages`,
        created_at: new Date().toISOString(),
        ...(command.kind === 'answer' ? { sources: [...command.sources] } : { hits: command.hits }),
      }]);
    } catch (err) {
      setEntries((previous) => [...previous, {
        id: crypto.randomUUID(), channel: channelId, kind: 'assistant',
        text: err instanceof Error ? err.message : 'Command failed', created_at: new Date().toISOString(),
      }]);
    } finally {
      setSending(false);
      requestAnimationFrame(() => bottomRef.current?.scrollIntoView({ behavior: 'smooth' }));
    }
  };

  const visibleEntries = entries.filter((entry) => entry.channel === channelId);
  const channel = channels.find((item) => item.id === channelId);

  return (
    <div className="flex h-dvh flex-col bg-white text-[#1d1c1d]">
      <nav className="flex h-10 shrink-0 items-center bg-[#481349] px-4 text-white">
        <span className="text-sm font-semibold">RecallHQ</span>
        <span className="mx-auto text-xs text-white/75">Beacon workspace · synthetic team chat</span>
      </nav>
      <div className="flex min-h-0 flex-1">
        <aside className="hidden w-60 shrink-0 flex-col bg-[#5E2C5F] text-white md:flex">
          <div className="border-b border-white/20 px-4 py-4 text-lg font-bold">Beacon</div>
          <p className="px-4 pb-2 pt-5 text-xs font-semibold uppercase tracking-wide text-white/65">Channels</p>
          {channels.map((item) => (
            <Link key={item.id} href={`/workspace/beacon/channel/${item.id}`} className={`mx-2 flex items-center gap-2 rounded px-3 py-1.5 text-sm hover:bg-white/15 ${channelId === item.id ? 'bg-white text-[#481349] hover:bg-white' : 'text-[#f9EDFFCC]'}`}>
              <Hash className="size-4" /> <span>{item.name}</span><span className="ml-auto text-xs opacity-60">{item.messages}</span>
            </Link>
          ))}
        </aside>

        <main className="flex min-w-0 flex-1 flex-col">
          <header className="flex h-[49px] shrink-0 items-center gap-2 border-b px-5 text-lg font-semibold">
            <Hash className="size-5" /> <span>{channel?.name || channelId}</span>
            <select aria-label="Change channel" value={channelId} onChange={(event) => router.push(`/workspace/beacon/channel/${event.target.value}`)} className="ml-auto max-w-32 rounded border p-1 text-sm md:hidden">
              {channels.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
            </select>
            <span className="ml-auto hidden text-xs font-normal text-muted-foreground md:inline">Read-only archive</span>
          </header>
          {error && <p role="alert" className="border-b bg-rose-50 px-5 py-2 text-sm text-rose-700">{error}</p>}
          <div ref={scrollRef} onScroll={(event) => { if (event.currentTarget.scrollTop < 120) void loadMore(); }} style={{ overflowAnchor: 'none' }} className="messages-scrollbar min-h-0 flex-1 overflow-y-auto" aria-label={`Messages in ${channelId}`}>
            {loading ? <div className="flex h-full items-center justify-center"><Loader className="size-5 animate-spin" /></div> : (
              <>
                <div className="px-5 py-5">
                  <h1 className="text-2xl font-bold"># {channel?.name || channelId}</h1>
                  <p className="mt-1 text-sm text-muted-foreground">Browse the team’s archived conversation and open threads for replies.</p>
                </div>
                {nextCursor && <div className="flex h-8 items-center justify-center" role="status">{loadingMore && <><Loader className="mr-2 size-4 animate-spin" /><span className="text-xs text-muted-foreground">Loading older messages…</span></>}</div>}
                {messages.map((message) => <MessageCard key={message.id} message={message} onThread={openThread} />)}
                {visibleEntries.map((entry) => (
                  <article key={entry.id} className={`flex gap-3 px-5 py-2 ${entry.kind === 'assistant' ? 'bg-violet-50/60' : ''}`}>
                    <Avatar className="mt-0.5 size-9 shrink-0"><AvatarFallback>{entry.kind === 'assistant' ? 'R' : 'Y'}</AvatarFallback></Avatar>
                    <div className="min-w-0 flex-1 text-sm">
                      <div className="flex gap-2"><strong>{entry.kind === 'assistant' ? 'RecallHQ' : 'You'}</strong><span className="text-xs text-muted-foreground">{format(new Date(entry.created_at), 'h:mm a')}</span></div>
                      <p className="whitespace-pre-wrap break-words leading-[22px]">{entry.text}</p>
                      {!!entry.sources?.length && <div className="mt-2 flex flex-wrap gap-2">{entry.sources.map((item) => <Link key={item.id} href={sourceUrl(item)} className="rounded border bg-white px-2 py-1 text-xs text-sky-700 hover:underline">#{item.channel} · {item.author_name} · {format(new Date(item.created_at), 'MMM d')}</Link>)}</div>}
                      {!!entry.hits?.length && <div className="mt-2 space-y-2">{entry.hits.map((item) => <Link key={item.id} href={sourceUrl(item)} className="block rounded border bg-white p-2 hover:border-sky-400"><strong>#{item.channel} · {item.author_name}</strong><span className="ml-2 text-xs text-muted-foreground">{format(new Date(item.created_at), 'MMM d')}</span><p className="line-clamp-2 whitespace-pre-wrap text-sm">{item.text}</p></Link>)}</div>}
                    </div>
                  </article>
                ))}
                <div ref={bottomRef} />
              </>
            )}
          </div>
          <div className="shrink-0 border-t bg-white px-5 pb-3 pt-2">
            <div className="mb-2 flex flex-wrap items-center gap-2 text-xs">
              <span className="font-medium text-muted-foreground">Commands:</span>
              {['/ask <question>', '/search <terms>', '/catchup 2026-09-14 2026-09-18'].map((item) => (
                <button key={item} onClick={() => { setDraft(item.replace(' <question>', ' ').replace(' <terms>', ' ')); setEditorKey((key) => key + 1); }} className="rounded border px-2 py-1 text-sky-700 hover:bg-sky-50">{item}</button>
              ))}
            </div>
            <Editor key={editorKey} defaultValue={draft ? [{ insert: `${draft}\n` }] : []} placeholder={`Message #${channelId} or enter a command`} onSubmit={send} disabled={sending} allowImage={false} />
          </div>
        </main>

        {(source || thread) && <aside className="fixed inset-0 z-20 flex flex-col border-l bg-white shadow-xl md:static md:w-[380px] md:shrink-0">
          <header className="flex h-[49px] items-center gap-2 border-b px-4 font-semibold"><MessageSquareText className="size-4" /> {thread ? 'Thread' : 'Source message'}<button onClick={() => { setSource(null); setThread(null); router.replace(`/workspace/beacon/channel/${channelId}`); }} aria-label="Close panel" className="ml-auto"><X className="size-5" /></button></header>
          <div className="messages-scrollbar flex-1 overflow-y-auto py-3">
            {thread ? thread.map((item) => <MessageCard key={item.id} message={item} />) : source && <MessageCard message={source} highlighted />}
            {source?.thread_root_id && <button onClick={() => openThread(source.thread_root_id!)} className="mx-5 mt-2 text-sm text-sky-700 hover:underline">Open full thread</button>}
          </div>
        </aside>}
      </div>
    </div>
  );
}
