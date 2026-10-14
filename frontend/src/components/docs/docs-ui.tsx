import type { ReactNode } from 'react';

import styles from '@/components/site.module.css';

export function Note({ children }: { children: ReactNode }) {
  return (
    <aside className={styles.note}>
      <p>{children}</p>
    </aside>
  );
}

export function Code({ children, label }: { children: string; label?: string }) {
  return (
    <div className={styles.codeBlock}>
      {label && <span className={styles.codeLabel}>{label}</span>}
      <pre tabIndex={0}>
        <code>{children}</code>
      </pre>
    </div>
  );
}

export function Toc({ items }: { items: [id: string, label: string][] }) {
  return (
    <nav className={styles.toc} aria-label="On this page">
      {items.map(([id, label]) => (
        <a key={id} href={`#${id}`}>
          {label}
        </a>
      ))}
    </nav>
  );
}

export function Table({ head, rows, numeric = [] }: { head: string[]; rows: ReactNode[][]; numeric?: number[] }) {
  return (
    <div className={styles.tableWrap} tabIndex={0} role="region" aria-label={head.join(', ')}>
      <table className={styles.table}>
        <thead>
          <tr>
            {head.map((cell, i) => (
              <th key={cell} scope="col" className={numeric.includes(i) ? styles.num : undefined}>
                {cell}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, r) => (
            <tr key={r}>
              {row.map((cell, i) => (
                <td key={i} className={numeric.includes(i) ? styles.num : undefined}>
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
