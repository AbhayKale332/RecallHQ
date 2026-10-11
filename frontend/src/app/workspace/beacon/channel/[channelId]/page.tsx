import { Suspense } from 'react';

import { PublicChat } from '@/components/public-chat';

export default function ChannelPage() {
  return <Suspense fallback={<div className="p-6">Loading chat…</div>}><PublicChat /></Suspense>;
}
