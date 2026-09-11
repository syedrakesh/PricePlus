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

const NAV: NavItem[] = [
  { href: '/',               label: 'Dashboard',   icon: '⬛' },
  { href: '/stores',         label: 'Stores',      icon: '🏪', permission: 'manage_stores' },
  { href: '/tracking',       label: 'Products',    icon: '📦', permission: 'manage_tracking' },
  { href: '/alerts',         label: 'Alerts',      icon: '🔔', permission: 'manage_alerts' },
  { href: '/billing',        label: 'Billing',     icon: '💳', permission: 'manage_billing' },
  { href: '/settings',       label: 'Settings',    icon: '⚙️' },
  { href: '/admin/plans',    label: 'Admin Plans', icon: '👑', permission: 'access_admin' },
  { href: '/admin/users',    label: 'Admin Users', icon: '👥', permission: 'access_admin' },
  { href: '/admin/permissions', label: 'RBAC Matrix', icon: '🔒', permission: 'access_admin' },
];

export function Sidebar() {
  const pathname = usePathname();
  const { user, logout, hasPermission } = useAuth();

  const visibleNav = NAV.filter(item => {
    if (!item.permission) return true;
    return hasPermission(item.permission);
  });

  return (
    <aside className={styles.sidebar}>
      <div className={styles.logo}>
        <span className={styles.logoIcon}>⚡</span>
        <span className={styles.logoText}>PricePlus</span>
      </div>

      <nav className={styles.nav}>
        {visibleNav.map(item => {
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
