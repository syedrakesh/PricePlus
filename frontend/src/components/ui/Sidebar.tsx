'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useAuth } from '@/context/AuthContext';
import styles from './Sidebar.module.css';

interface NavItem {
  href: string;
  label: string;
  icon: string;
  permission?: string;
}

interface NavSection {
  title?: string;
  items: NavItem[];
}

const NAV_SECTIONS: NavSection[] = [
  {
    items: [
      { href: '/',               label: 'Dashboard',   icon: '⬛' },
      { href: '/stores',         label: 'Stores',      icon: '🏪', permission: 'manage_stores' },
      { href: '/tracking',       label: 'Products',    icon: '📦', permission: 'manage_tracking' },
      { href: '/alerts',         label: 'Alerts',      icon: '🔔', permission: 'manage_alerts' },
      { href: '/billing',        label: 'Billing',     icon: '💳', permission: 'manage_billing' },
    ],
  },
  {
    title: 'Account',
    items: [
      { href: '/account',          label: 'My Profile',     icon: '👤' },
      { href: '/account/security', label: 'Security',       icon: '🔑' },
    ],
  },
  {
    title: 'Speed & System',
    items: [
      { href: '/system',             label: 'Engine Telemetry', icon: '⚙️' },
      { href: '/settings/discovery', label: 'Discovery Speed', icon: '🔍' },
      { href: '/settings/tracking',  label: 'Tracking Speed',  icon: '⚡' },
    ],
  },
  {
    title: 'Admin',
    items: [
      { href: '/admin/plans',       label: 'Admin Plans',    icon: '👑', permission: 'access_admin' },
      { href: '/admin/users',       label: 'Admin Users',    icon: '👥', permission: 'access_admin' },
      { href: '/admin/permissions', label: 'RBAC Matrix',    icon: '🔒', permission: 'access_admin' },
    ],
  },
];

export function Sidebar() {
  const pathname = usePathname();
  const { user, logout, hasPermission } = useAuth();

  const hasExactMatch = NAV_SECTIONS.some(sec =>
    sec.items.some(i => i.href === pathname)
  );

  return (
    <aside className={styles.sidebar}>
      <div className={styles.logo}>
        <span className={styles.logoIcon}>⚡</span>
        <span className={styles.logoText}>PricePlus</span>
      </div>

      <nav className={styles.nav}>
        {NAV_SECTIONS.map((section, idx) => {
          const visibleItems = section.items.filter(item => {
            if (!item.permission) return true;
            return hasPermission(item.permission);
          });

          if (visibleItems.length === 0) return null;

          return (
            <div key={section.title || `sec-${idx}`}>
              {section.title && <div className={styles.sectionHeader}>{section.title}</div>}
              {visibleItems.map(item => {
                const active = hasExactMatch
                  ? pathname === item.href
                  : (item.href === '/'
                    ? pathname === '/'
                    : pathname === item.href || (item.href !== '/' && pathname.startsWith(item.href + '/')));

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
            </div>
          );
        })}
      </nav>

      <div className={styles.footer}>
        {user && (
          <div className={styles.userProfile}>
            <span className={styles.userEmail}>{user.email}</span>
            <div className={styles.userRoleRow}>
              <span className={styles.userBadge}>
                {user.is_superuser ? 'SuperAdmin' : (user.role_name || 'Standard User')}
              </span>
            </div>
          </div>
        )}
        <button className={styles.logout} onClick={logout}>
          <span>↩</span> Sign out
        </button>
      </div>
    </aside>
  );
}
