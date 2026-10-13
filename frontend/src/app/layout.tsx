import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import type { PropsWithChildren } from 'react';

import { ChatSessionProvider } from '@/components/chat-session-provider';

import './globals.css';

const inter = Inter({
  subsets: ['latin'],
});

export const metadata: Metadata = {
  title: 'RecallHQ | Your team’s memory in Slack',
  description:
    'Ask questions, find decisions, and catch up on Slack conversations with source-linked answers. Explore the docs and public Beacon playground.',
};

const RootLayout = ({ children }: Readonly<PropsWithChildren>) => {
  return (
    <html lang="en">
      <body className={`${inter.className} antialiased`}>
        <ChatSessionProvider>{children}</ChatSessionProvider>
      </body>
    </html>
  );
};

export default RootLayout;
