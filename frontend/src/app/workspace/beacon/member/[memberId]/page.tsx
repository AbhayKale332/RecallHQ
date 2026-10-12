import { notFound } from 'next/navigation';
import { Suspense } from 'react';

import { PublicChat } from '@/components/public-chat';

export default async function MemberPage({ params }: { params: Promise<{ memberId: string }> }) {
  const { memberId } = await params;
  if (memberId !== 'recallhq') notFound();

  return (
    <Suspense fallback={<div className="p-6">Loading conversation…</div>}>
      <PublicChat directMessage />
    </Suspense>
  );
}
