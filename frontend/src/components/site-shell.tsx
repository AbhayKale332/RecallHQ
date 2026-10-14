import { ArrowUpRight, BookOpen, Terminal } from 'lucide-react';
import Link from 'next/link';
import type { ReactNode } from 'react';
import { FaGithub } from 'react-icons/fa6';

import { GITHUB_URL } from '@/lib/docs-nav';
import { DEMO_URL, SLACK_INSTALL_URL } from '@/lib/public-api';

import styles from './site.module.css';

/** The RecallHQ mark from public/logo.svg, inlined so it needs no base-path-aware URL. */
export function Logo({ size = 26, className }: { size?: number; className?: string }) {
  return (
    <svg className={className} width={size} height={size} viewBox="0 0 50 50" aria-hidden="true" focusable="false">
      <path
        fill="#E6176D"
        d="M49.7991 26.4063C49.1071 24.5508 46.7969 23.5645 44.6652 24.1699L39.5982 25.6445L36.2165 16.8555L41.2835 15.3809C43.4152 14.7754 44.5313 12.7637 43.8505 10.8984C43.1585 9.04298 40.8482 8.05665 38.7165 8.66212L33.6496 10.1367L31.8973 5.54688C31.2054 3.69142 28.8951 2.70509 26.7634 3.31056C24.6317 3.91603 23.5156 5.92774 24.1964 7.79298L25.9487 12.3828L15.5246 15.4297L13.7723 10.8399C13.0804 8.98438 10.7701 7.99806 8.6384 8.60353C6.5067 9.20899 5.39063 11.2207 6.07143 13.0859L7.82367 17.6758L2.76786 19.1406C0.636165 19.7461 -0.479906 21.7578 0.200898 23.6231C0.758933 25.0391 2.33259 25.9668 3.9509 26.0254C4.70983 26.1231 5.29018 25.8692 10.3906 24.3848L13.7723 33.1738L8.70536 34.6484C6.58483 35.2539 5.45759 37.2754 6.1384 39.1309C6.69643 40.5469 8.27009 41.4746 9.8884 41.5332C10.6473 41.6309 11.2277 41.377 16.3281 39.8926L18.0804 44.4824C18.7388 46.1328 20.8371 47.3145 23.2143 46.7188C25.346 46.1133 26.4621 44.1016 25.7813 42.2363L24.029 37.6465L34.4755 34.5899L36.2277 39.1797C36.8862 40.8301 38.9844 42.0117 41.3616 41.416C43.4933 40.8106 44.6094 38.7988 43.9286 36.9336L42.1763 32.3438L47.2433 30.8692C49.3638 30.2832 50.4911 28.2617 49.7991 26.4063ZM21.4397 31.0156L18.058 22.207L28.4933 19.1504L31.875 27.959L21.4397 31.0156Z"
      />
    </svg>
  );
}

export function InstallLink({ className = '', label = 'Add to Slack' }: { className?: string; label?: string }) {
  return (
    <a href={SLACK_INSTALL_URL} className={`${styles.primaryButton} ${className}`}>
      {label} <ArrowUpRight size={16} aria-hidden="true" />
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
            <Logo className={styles.brandMark} />
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
            <a href={GITHUB_URL}>
              <FaGithub size={15} aria-hidden="true" />
              <span>GitHub</span>
            </a>
          </nav>
          <InstallLink className={styles.headerInstall} />
        </div>
      </header>
      {children}
      <footer className={styles.footer}>
        <Link href="/" className={styles.footerBrand}>
          <Logo size={18} /> RecallHQ
        </Link>
        <p>Ask your team chat. Get grounded, cited answers.</p>
        <Link href="/docs/architecture">Architecture</Link>
        <Link href="/docs/evaluation">Evaluations</Link>
        <Link href="/docs/permissions">Permissions & data</Link>
        <a href={GITHUB_URL}>GitHub</a>
      </footer>
    </div>
  );
}
