import type { Metadata } from 'next';

import { BeaconPlayground } from '@/components/beacon-playground';
import { SiteShell } from '@/components/site-shell';
import styles from '@/components/site.module.css';

export const metadata: Metadata = {
  title: 'Beacon playground | RecallHQ',
  description: 'Try RecallHQ’s ask, search, and catchup commands on the public synthetic Beacon corpus. No Slack account required.',
};

export default function PlaygroundPage() {
  return (
    <SiteShell active="playground">
      <main id="main-content" className={styles.playgroundContainer}>
        <div className={styles.playgroundHeading}>
          <p className={styles.eyebrow}>
            <span className={styles.eyebrowDot} /> Public synthetic workspace
          </p>
          <h1>Meet your team’s memory.</h1>
          <p>
            Try RecallHQ on Beacon, a fictional team planning a campus pilot. Ask about the data model, the pilot scope, or the venue.
            Follow the sources to see where each answer came from.
          </p>
        </div>
        <BeaconPlayground />
      </main>
    </SiteShell>
  );
}
