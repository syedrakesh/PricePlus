'use client';

import { useState } from 'react';
import useSWR from 'swr';
import { adminApi, AdminUser, RoleItem } from '@/lib/api';
import { Card, CardHeader, CardBody } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { PageLoader } from '@/components/ui/Spinner';
import styles from './page.module.css';

const PLAN_SLUG_COLOR: Record<string, string> = {
  free:       '#64748b',
  starter:    '#10b981',
  pro:        '#38bdf8',
  enterprise: '#818cf8',
};

function planVariant(slug: string | null): 'default' | 'success' | 'accent' | 'info' {
  if (slug === 'enterprise') return 'accent';
  if (slug === 'pro') return 'info';
  if (slug === 'starter') return 'success';
  return 'default';
}

function subStatusVariant(status: string): 'success' | 'warning' | 'danger' | 'info' | 'default' {
  if (status === 'active') return 'success';
  if (status === 'trialing') return 'info';
  if (status === 'past_due') return 'warning';
  if (status === 'canceled') return 'danger';
  return 'default';
}

// ─── User Row ─────────────────────────────────────────────────────────────────

function UserRow({
  user,
  roles,
  onToggleStatus,
  onUpdateRole,
}: {
  user: AdminUser;
  roles: RoleItem[];
  onToggleStatus: (id: string) => Promise<void>;
  onUpdateRole: (userId: string, roleSlug: string) => Promise<void>;
}) {
  const [toggling, setToggling] = useState(false);
  const [updatingRole, setUpdatingRole] = useState(false);

  async function handleToggle() {
    setToggling(true);
    await onToggleStatus(user.id);
    setToggling(false);
  }

  async function handleRoleSelect(e: React.ChangeEvent<HTMLSelectElement>) {
    const newRoleSlug = e.target.value;
    setUpdatingRole(true);
    try {
      await onUpdateRole(user.id, newRoleSlug);
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : 'Failed to update role');
    } finally {
      setUpdatingRole(false);
    }
  }

  const joinedDate = new Date(user.created_at).toLocaleDateString('en-US', {
    year: 'numeric', month: 'short', day: 'numeric',
  });

  return (
    <tr className={styles.tableRow}>
      <td className={styles.td}>
        <div className={styles.emailCell}>
          <div className={styles.avatar}>
            {user.email[0].toUpperCase()}
          </div>
          <div>
            <div className={styles.emailText}>{user.email}</div>
            <div className={styles.userId} title={user.id}>{user.id.slice(0, 8)}…</div>
          </div>
        </div>
      </td>
      <td className={styles.td}>
        <Badge variant={user.is_active ? 'success' : 'danger'}>
          {user.is_active ? 'Active' : 'Inactive'}
        </Badge>
      </td>
      <td className={styles.td}>
        {user.is_superuser ? (
          <Badge variant="accent">SuperAdmin</Badge>
        ) : (
          <select
            value={user.role_slug || 'user'}
            onChange={handleRoleSelect}
            disabled={updatingRole}
            className={styles.input}
            style={{ padding: '2px 6px', fontSize: '0.8rem' }}
          >
            {roles.map(r => (
              <option key={r.id} value={r.slug}>{r.name}</option>
            ))}
          </select>
        )}
      </td>
      <td className={styles.td}>
        <Badge variant={planVariant(user.plan_slug)}>
          {user.plan_name}
        </Badge>
      </td>
      <td className={styles.td}>
        <Badge variant={subStatusVariant(user.subscription_status)}>
          {user.subscription_status.replace(/_/g, ' ')}
        </Badge>
      </td>
      <td className={styles.td} style={{ color: '#94a3b8', fontSize: '0.8rem' }}>
        {joinedDate}
      </td>
      <td className={styles.td}>
        {!user.is_superuser && (
          <Button
            id={`toggle-user-${user.id}`}
            size="sm"
            variant="secondary"
            onClick={handleToggle}
            disabled={toggling}
            style={{ fontSize: '0.75rem', padding: '4px 10px' }}
          >
            {toggling ? '…' : user.is_active ? 'Deactivate' : 'Activate'}
          </Button>
        )}
      </td>
    </tr>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function AdminUsersPage() {
  const { data: users, isLoading: loadingUsers, mutate: mutateUsers } = useSWR('admin-users', adminApi.listUsers);
  const { data: roles = [], isLoading: loadingRoles } = useSWR('admin-roles', adminApi.listRoles);

  const [search, setSearch] = useState('');
  const [filterPlan, setFilterPlan] = useState('');
  const [filterStatus, setFilterStatus] = useState('');

  async function handleToggleStatus(userId: string) {
    await adminApi.toggleUserStatus(userId);
    await mutateUsers();
  }

  async function handleUpdateRole(userId: string, roleSlug: string) {
    await adminApi.updateUserRole(userId, roleSlug);
    await mutateUsers();
  }

  if (loadingUsers || loadingRoles) return <PageLoader />;

  const planSlugs = [...new Set((users ?? []).map(u => u.plan_slug ?? 'free'))];

  const filtered = (users ?? []).filter(u => {
    const emailMatch = u.email.toLowerCase().includes(search.toLowerCase());
    const planMatch = filterPlan ? (u.plan_slug ?? 'free') === filterPlan : true;
    const statusMatch = filterStatus ? u.subscription_status === filterStatus : true;
    return emailMatch && planMatch && statusMatch;
  });

  const totalActive = (users ?? []).filter(u => u.is_active).length;
  const totalPaid = (users ?? []).filter(u => u.plan_slug && u.plan_slug !== 'free').length;

  return (
    <div className={styles.container}>
      {/* Header */}
      <div className={styles.header}>
        <div>
          <h1 className={styles.title}>👥 User Management</h1>
          <p className={styles.subtitle}>
            View and manage all registered users, assign system roles, subscription plans, and account status.
          </p>
        </div>
      </div>

      {/* Stats row */}
      <div className={styles.statsRow}>
        <div className={styles.statCard}>
          <div className={styles.statVal}>{users?.length ?? 0}</div>
          <div className={styles.statLabel}>Total Users</div>
        </div>
        <div className={styles.statCard}>
          <div className={styles.statVal} style={{ color: '#10b981' }}>{totalActive}</div>
          <div className={styles.statLabel}>Active</div>
        </div>
        <div className={styles.statCard}>
          <div className={styles.statVal} style={{ color: '#38bdf8' }}>{totalPaid}</div>
          <div className={styles.statLabel}>Paid Subscribers</div>
        </div>
        <div className={styles.statCard}>
          <div className={styles.statVal} style={{ color: '#94a3b8' }}>
            {(users?.length ?? 0) - totalActive}
          </div>
          <div className={styles.statLabel}>Inactive</div>
        </div>
      </div>

      {/* Filters */}
      <Card>
        <CardBody>
          <div className={styles.filters}>
            <div className={styles.searchWrap}>
              <input
                type="text"
                className={styles.input}
                placeholder="🔍 Search by email…"
                value={search}
                onChange={e => setSearch(e.target.value)}
                id="user-search-input"
              />
            </div>
            <select
              className={styles.input}
              value={filterPlan}
              onChange={e => setFilterPlan(e.target.value)}
              id="filter-plan"
            >
              <option value="">All Plans</option>
              {planSlugs.map(slug => (
                <option key={slug} value={slug}>{slug}</option>
              ))}
            </select>
            <select
              className={styles.input}
              value={filterStatus}
              onChange={e => setFilterStatus(e.target.value)}
              id="filter-status"
            >
              <option value="">All Statuses</option>
              {['active', 'trialing', 'past_due', 'canceled', 'none'].map(s => (
                <option key={s} value={s}>{s.replace(/_/g, ' ')}</option>
              ))}
            </select>
            {(search || filterPlan || filterStatus) && (
              <Button
                variant="secondary"
                size="sm"
                onClick={() => { setSearch(''); setFilterPlan(''); setFilterStatus(''); }}
              >
                Clear
              </Button>
            )}
          </div>
        </CardBody>
      </Card>

      {/* User table */}
      <Card>
        <CardHeader>
          <h3>Users ({filtered.length})</h3>
          {search || filterPlan || filterStatus ? (
            <span style={{ fontSize: '0.8rem', color: '#94a3b8' }}>filtered from {users?.length} total</span>
          ) : null}
        </CardHeader>
        <CardBody>
          {filtered.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '2rem', color: '#64748b' }}>
              No users found matching your filters.
            </div>
          ) : (
            <div className={styles.tableWrap}>
              <table className={styles.table}>
                <thead>
                  <tr>
                    <th className={styles.th}>User</th>
                    <th className={styles.th}>Status</th>
                    <th className={styles.th}>Role</th>
                    <th className={styles.th}>Plan</th>
                    <th className={styles.th}>Sub Status</th>
                    <th className={styles.th}>Joined</th>
                    <th className={styles.th}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map(user => (
                    <UserRow
                      key={user.id}
                      roles={roles}
                      user={user}
                      onToggleStatus={handleToggleStatus}
                      onUpdateRole={handleUpdateRole}
                    />
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardBody>
      </Card>
    </div>
  );
}
