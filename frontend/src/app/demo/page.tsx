import { redirect } from 'next/navigation';

import { DEMO_URL } from '@/lib/public-api';

export default function DemoPage() {
  redirect(DEMO_URL);
}
