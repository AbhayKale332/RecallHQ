'use client';

import { type Dispatch, type PropsWithChildren, type SetStateAction, createContext, useContext, useState } from 'react';

export type SessionEntry = {
  id: string;
  channel: string;
  kind: 'visitor' | 'assistant';
  text: string;
  created_at: string;
  sources?: Array<{ id: string; channel: string; author_name: string; created_at: string }>;
  hits?: Array<{ id: string; channel: string; author_name: string; created_at: string; text: string }>;
};

const ChatSession = createContext<{
  entries: SessionEntry[];
  setEntries: Dispatch<SetStateAction<SessionEntry[]>>;
  sendingChannel: string | null;
  setSendingChannel: Dispatch<SetStateAction<string | null>>;
} | null>(null);

export function ChatSessionProvider({ children }: PropsWithChildren) {
  const [entries, setEntries] = useState<SessionEntry[]>([]);
  const [sendingChannel, setSendingChannel] = useState<string | null>(null);
  return <ChatSession.Provider value={{ entries, setEntries, sendingChannel, setSendingChannel }}>{children}</ChatSession.Provider>;
}

export function useChatSession() {
  const session = useContext(ChatSession);
  if (!session) throw new Error('Chat session provider is missing');
  return session;
}
