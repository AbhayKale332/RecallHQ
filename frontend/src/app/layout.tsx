import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import type { PropsWithChildren } from 'react';

import { ChatSessionProvider } from '@/components/chat-session-provider';

import './globals.css';

const inter = Inter({
  subsets: ['latin'],
});

export const metadata: Metadata = {
  title: 'RecallHQ | Beacon workspace',
  description: 'Search and catch up on the Beacon team chat.',
};

const RootLayout = ({ children }: Readonly<PropsWithChildren>) => {
  return (
    <html lang="en">
      <body className={`${inter.className} antialiased`}><ChatSessionProvider>{children}</ChatSessionProvider></body>
    </html>
  );
};

export default RootLayout;
