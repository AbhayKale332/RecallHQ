'use client';

import { createContext, useContext, useState, type Dispatch, type PropsWithChildren, type SetStateAction } from 'react';

export type SessionEntry = {
  id: string;
  channel: string;
  kind: 'visitor' | 'assistant';
  text: string;
  created_at: string;
  sources?: Array<{ id: string; channel: string; author_name: string; created_at: string }>;
  hits?: Array<{ id: string; channel: string; author_name: string; created_at: string; text: string }>;
};

const ChatSession = createContext<{ entries: SessionEntry[]; setEntries: Dispatch<SetStateAction<SessionEntry[]>> } | null>(null);

export function ChatSessionProvider({ children }: PropsWithChildren) {
  const [entries, setEntries] = useState<SessionEntry[]>([]);
  return <ChatSession.Provider value={{ entries, setEntries }}>{children}</ChatSession.Provider>;
}

export function useChatSession() {
  const session = useContext(ChatSession);
  if (!session) throw new Error('Chat session provider is missing');
  return session;
}
