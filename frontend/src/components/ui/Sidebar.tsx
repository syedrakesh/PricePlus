'use client';

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { clearTokens } from '@/lib/auth';
import styles from './Sidebar.module.css';

const NAV = [
  { href: '/',         label: 'Dashboard',  icon: '⬛' },
  { href: '/stores',   label: 'Stores',     icon: '🏪' },
  { href: '/tracking', label: 'Products',   icon: '📦' },
  { href: '/alerts',   label: 'Alerts',     icon: '🔔' },
  { href: '/billing',  label: 'Billing',    icon: '💳' },
];

export function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();

  function handleLogout() {
    clearTokens();
    router.push('/login');
  }

  return (
    <aside className={styles.sidebar}>
      <div className={styles.logo}>
        <span className={styles.logoIcon}>⚡</span>
        <span className={styles.logoText}>PricePlus</span>
      </div>

      <nav className={styles.nav}>
        {NAV.map(item => {
          const active = item.href === '/'
            ? pathname === '/'
            : pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={[styles.navItem, active ? styles.navActive : ''].join(' ')}
            >
              <span className={styles.navIcon}>{item.icon}</span>
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>

      <div className={styles.footer}>
        <button className={styles.logout} onClick={handleLogout}>
          <span>↩</span> Sign out
        </button>
      </div>
    </aside>
  );
}
