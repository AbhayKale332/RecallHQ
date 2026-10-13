import { ArrowUpRight, BookOpen, Hash, Terminal } from 'lucide-react';
import Link from 'next/link';
import type { ReactNode } from 'react';

import { DEMO_URL, SLACK_INSTALL_URL } from '@/lib/public-api';

import styles from './site.module.css';

export const docsLinks = [
  { label: 'Introduction', href: '/docs' },
  { label: 'Installation', href: '/docs/installation' },
  { label: 'Quick start', href: '/docs/quickstart' },
  { label: 'Command reference', href: '/docs/commands' },
  { label: 'Permissions & data', href: '/docs/permissions' },
  { label: 'Troubleshooting', href: '/docs/troubleshooting' },
];

export function InstallLink({ className = '' }: { className?: string }) {
  return (
    <a href={SLACK_INSTALL_URL} className={`${styles.primaryButton} ${className}`}>
      Add to Slack <ArrowUpRight size={16} aria-hidden="true" />
    </a>
  );
}

export function SiteShell({ children, active }: { children: ReactNode; active?: 'docs' | 'playground' }) {
  return (
    <div className={styles.site}>
      <a className={styles.skipLink} href="#main-content">
        Skip to content
      </a>
      <header className={styles.header}>
        <div className={styles.headerInner}>
          <Link className={styles.brand} href="/" aria-label="RecallHQ home">
            <span className={styles.brandMark}>
              <Hash size={21} aria-hidden="true" />
            </span>
            RecallHQ<span className={styles.brandTag}>for Slack</span>
          </Link>
          <nav className={styles.navigation} aria-label="Main navigation">
            <Link href="/docs" aria-current={active === 'docs' ? 'page' : undefined}>
              <BookOpen size={15} aria-hidden="true" />
              <span>Docs</span>
            </Link>
            <Link href="/playground" aria-current={active === 'playground' ? 'page' : undefined}>
              <Terminal size={15} aria-hidden="true" />
              <span>Playground</span>
            </Link>
            <Link href={DEMO_URL}>
              Demo <ArrowUpRight size={14} aria-hidden="true" />
            </Link>
          </nav>
          <InstallLink className={styles.headerInstall} />
        </div>
      </header>
      {children}
      <footer className={styles.footer}>
        <Link href="/" className={styles.footerBrand}>
          RecallHQ
        </Link>
        <p>Answers grounded in your team’s conversations.</p>
        <Link href="/docs/permissions">Permissions & data</Link>
        <Link href="/docs/troubleshooting">Help</Link>
      </footer>
    </div>
  );
}
