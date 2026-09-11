'use client';

import { useState, useMemo } from 'react';
import useSWR from 'swr';
import { adminApi, Plan, AdminUser } from '@/lib/api';
import { Card, CardHeader, CardBody } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import styles from './page.module.css';

// ─── User Subscription Management ─────────────────────────────────────────────

function UserSubManager({ plans, users }: { plans: Plan[]; users: AdminUser[] }) {
  const [selectedUserId, setSelectedUserId] = useState('');
  const [selectedPlanId, setSelectedPlanId] = useState('');
  const [note, setNote] = useState('');
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<{ ok: boolean; msg: string } | null>(null);

  const filteredUsers = useMemo(() =>
    users.filter(u => u.email.toLowerCase().includes(search.toLowerCase())),
    [users, search]
  );

  const selectedUser = users.find(u => u.id === selectedUserId);

  async function handleAssign(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedUserId || !selectedPlanId) return;
    setLoading(true);
    setResult(null);
    try {
      const sub = await adminApi.assignUserPlan(selectedUserId, selectedPlanId, note || undefined);
      const plan = plans.find(p => p.id === selectedPlanId);
      setResult({ ok: true, msg: `✅ Assigned "${plan?.name ?? selectedPlanId}" to ${selectedUser?.email}` });
      setSelectedUserId('');
      setSelectedPlanId('');
      setNote('');
      setSearch('');
    } catch (err: any) {
      setResult({ ok: false, msg: `❌ ${err.message || 'Failed to assign plan'}` });
    } finally {
      setLoading(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <h3>🎯 Assign Plan to User</h3>
        <span style={{ fontSize: '0.8rem', color: '#94a3b8' }}>Manually override any user's subscription</span>
      </CardHeader>
      <CardBody>
        <form onSubmit={handleAssign} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>

            {/* User search + dropdown */}
            <div className={styles.inputGroup} style={{ position: 'relative' }}>
              <label className={styles.label}>Select User</label>
              <input
                type="text"
                className={styles.input}
                placeholder="Search by email…"
                value={search || selectedUser?.email || ''}
                onChange={e => { setSearch(e.target.value); setSelectedUserId(''); }}
                onFocus={e => e.target.select()}
              />
              {search && filteredUsers.length > 0 && (
                <div style={{
                  position: 'absolute', top: '100%', left: 0, right: 0, zIndex: 50,
                  background: '#0f172a', border: '1px solid rgba(255,255,255,0.15)',
                  borderRadius: 8, maxHeight: 220, overflowY: 'auto', marginTop: 4,
                  boxShadow: '0 8px 24px rgba(0,0,0,0.5)',
                }}>
                  {filteredUsers.map(u => (
                    <button
                      key={u.id}
                      type="button"
                      onClick={() => { setSelectedUserId(u.id); setSearch(''); }}
                      style={{
                        width: '100%', textAlign: 'left', background: 'transparent',
                        border: 'none', padding: '0.6rem 0.75rem', cursor: 'pointer',
                        color: '#e2e8f0', fontSize: '0.875rem', display: 'flex',
                        justifyContent: 'space-between', alignItems: 'center',
                        borderBottom: '1px solid rgba(255,255,255,0.05)',
                      }}
                      onMouseEnter={e => (e.currentTarget.style.background = 'rgba(56,189,248,0.08)')}
                      onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
                    >
                      <span>{u.email}</span>
                      <span style={{ fontSize: '0.7rem', color: '#64748b', fontFamily: 'monospace' }}>
                        {u.plan_slug ?? 'free'}
                      </span>
                    </button>
                  ))}
                </div>
              )}
              {selectedUser && (
                <div style={{ marginTop: 6, display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap' }}>
                  <Badge variant="accent" style={{ fontSize: '0.7rem' }}>{selectedUser.email}</Badge>
                  <Badge variant={selectedUser.is_active ? 'success' : 'danger'} style={{ fontSize: '0.7rem' }}>
                    {selectedUser.is_active ? 'Active' : 'Inactive'}
                  </Badge>
                  <Badge variant="default" style={{ fontSize: '0.7rem' }}>
                    {selectedUser.plan_name}
                  </Badge>
                </div>
              )}
            </div>

            {/* Plan dropdown */}
            <div className={styles.inputGroup}>
              <label className={styles.label}>Target Plan</label>
              <select
                className={styles.input}
                value={selectedPlanId}
                onChange={e => setSelectedPlanId(e.target.value)}
                required
              >
                <option value="">— Select Plan —</option>
                {plans.map(p => (
                  <option key={p.id} value={p.id}>
                    {p.name} ({p.slug}) — ${p.price_usd?.toFixed(2) ?? '0.00'}/mo
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className={styles.inputGroup}>
            <label className={styles.label}>Internal Note (optional)</label>
            <input
              type="text"
              className={styles.input}
              placeholder="e.g. Manual comp, refund, testing..."
              value={note}
              onChange={e => setNote(e.target.value)}
            />
          </div>

          {result && (
            <Badge variant={result.ok ? 'success' : 'danger'}>{result.msg}</Badge>
          )}

          <div>
            <Button type="submit" variant="primary" disabled={loading || !selectedUserId || !selectedPlanId}>
              {loading ? 'Assigning…' : 'Assign Plan'}
            </Button>
          </div>
        </form>
      </CardBody>
    </Card>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function AdminPlansPage() {
  const { data: plans, error, mutate, isLoading } = useSWR('admin-plans', adminApi.listPlans);
  const { data: users = [] } = useSWR('admin-users', adminApi.listUsers);
  const [editingPlan, setEditingPlan] = useState<Plan | null>(null);
  const [isCreating, setIsCreating] = useState(false);

  const [formData, setFormData] = useState<Partial<Plan>>({
    name: '',
    slug: '',
    price_usd: 0,
    max_stores: 2,
    max_tracked_products: 50,
    poll_interval_mins: 360,
    max_priority_products: 5,
    is_active: true,
    is_public: true,
  });

  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState('');

  function handleOpenEdit(plan: Plan) {
    setEditingPlan(plan);
    setFormData(plan);
    setIsCreating(false);
    setMsg('');
  }

  function handleOpenCreate() {
    setEditingPlan(null);
    setFormData({
      name: '',
      slug: '',
      price_usd: 19.0,
      max_stores: 3,
      max_tracked_products: 100,
      poll_interval_mins: 360,
      max_priority_products: 10,
      is_active: true,
      is_public: true,
    });
    setIsCreating(true);
    setMsg('');
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setMsg('');

    try {
      if (isCreating) {
        await adminApi.createPlan(formData);
        setMsg('✅ New subscription plan created successfully!');
      } else if (editingPlan) {
        await adminApi.updatePlan(editingPlan.id, formData);
        setMsg('✅ Subscription plan updated successfully!');
      }
      mutate();
      setEditingPlan(null);
      setIsCreating(false);
    } catch (err: any) {
      setMsg(`❌ Error: ${err.message || 'Failed to save plan'}`);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <div>
          <h1 className={styles.title}>👑 Admin Plan Management</h1>
          <p className={styles.subtitle}>
            Create, edit, and adjust subscription plan limits, check intervals, and pricing dynamically.
          </p>
        </div>
        <Button onClick={handleOpenCreate} variant="primary">
          + Create New Plan
        </Button>
      </div>

      {msg && (
        <Badge variant={msg.startsWith('✅') ? 'success' : 'danger'}>
          {msg}
        </Badge>
      )}

      {/* User Subscription Assignment */}
      {plans && <UserSubManager plans={plans} users={users} />}

      {/* Editor Modal / Form */}
      {(isCreating || editingPlan) && (
        <Card>
          <CardHeader>
            <h3>{isCreating ? '➕ Create Subscription Plan' : `✏️ Edit Plan: ${editingPlan?.name}`}</h3>
          </CardHeader>
          <CardBody>
            <form onSubmit={handleSave} className={styles.formGrid}>
              <div className={styles.inputGroup}>
                <label className={styles.label}>Plan Name</label>
                <input
                  type="text"
                  className={styles.input}
                  value={formData.name || ''}
                  onChange={e => setFormData({ ...formData, name: e.target.value })}
                  required
                />
              </div>

              <div className={styles.inputGroup}>
                <label className={styles.label}>Slug (Unique Identifier)</label>
                <input
                  type="text"
                  className={styles.input}
                  value={formData.slug || ''}
                  onChange={e => setFormData({ ...formData, slug: e.target.value })}
                  required
                  disabled={!!editingPlan}
                />
              </div>

              <div className={styles.inputGroup}>
                <label className={styles.label}>Price USD ($ / month)</label>
                <input
                  type="number"
                  step="0.01"
                  className={styles.input}
                  value={formData.price_usd ?? 0}
                  onChange={e => setFormData({ ...formData, price_usd: parseFloat(e.target.value) || 0 })}
                  required
                />
              </div>

              <div className={styles.inputGroup}>
                <label className={styles.label}>Stripe Price ID (Optional for Live Billing)</label>
                <input
                  type="text"
                  placeholder="price_1P..."
                  className={styles.input}
                  value={formData.stripe_price_id || ''}
                  onChange={e => setFormData({ ...formData, stripe_price_id: e.target.value || undefined })}
                />
              </div>

              <div className={styles.inputGroup}>
                <label className={styles.label}>Max Competitor Stores</label>
                <input
                  type="number"
                  className={styles.input}
                  value={formData.max_stores ?? 1}
                  onChange={e => setFormData({ ...formData, max_stores: parseInt(e.target.value) || 1 })}
                  required
                />
              </div>

              <div className={styles.inputGroup}>
                <label className={styles.label}>Max Tracked Products</label>
                <input
                  type="number"
                  className={styles.input}
                  value={formData.max_tracked_products ?? 10}
                  onChange={e => setFormData({ ...formData, max_tracked_products: parseInt(e.target.value) || 10 })}
                  required
                />
              </div>

              <div className={styles.inputGroup}>
                <label className={styles.label}>Min Check Interval (Minutes)</label>
                <input
                  type="number"
                  className={styles.input}
                  value={formData.poll_interval_mins ?? 360}
                  onChange={e => setFormData({ ...formData, poll_interval_mins: parseInt(e.target.value) || 60 })}
                  required
                />
              </div>

              <div className={styles.inputGroup}>
                <label className={styles.label}>Status & Visibility</label>
                <div style={{ display: 'flex', gap: '1rem', marginTop: '0.5rem' }}>
                  <label style={{ color: '#fff', fontSize: '0.875rem' }}>
                    <input
                      type="checkbox"
                      checked={formData.is_active ?? true}
                      onChange={e => setFormData({ ...formData, is_active: e.target.checked })}
                    /> Active
                  </label>
                  <label style={{ color: '#fff', fontSize: '0.875rem' }}>
                    <input
                      type="checkbox"
                      checked={formData.is_public ?? true}
                      onChange={e => setFormData({ ...formData, is_public: e.target.checked })}
                    /> Public Pricing
                  </label>
                </div>
              </div>

              <div className={styles.fullWidth} style={{ display: 'flex', gap: '1rem', marginTop: '1rem' }}>
                <Button type="submit" variant="primary" disabled={saving}>
                  {saving ? 'Saving...' : isCreating ? 'Create Plan' : 'Save Changes'}
                </Button>
                <Button type="button" variant="secondary" onClick={() => { setIsCreating(false); setEditingPlan(null); }}>
                  Cancel
                </Button>
              </div>
            </form>
          </CardBody>
        </Card>
      )}

      {/* Plan Cards Grid */}
      {isLoading ? (
        <p style={{ color: '#94a3b8' }}>Loading system subscription plans...</p>
      ) : error ? (
        <Badge variant="danger">Failed to load admin plans. Superadmin privileges required.</Badge>
      ) : (
        <div className={styles.grid}>
          {plans?.map(plan => (
            <div key={plan.id} className={styles.planCard}>
              <div>
                <div className={styles.planHeader}>
                  <div>
                    <div className={styles.planName}>{plan.name}</div>
                    <div className={styles.planSlug}>slug: {plan.slug || 'free'}</div>
                  </div>
                  <Badge variant={plan.is_active ? 'success' : 'warning'}>
                    {plan.is_active ? (plan.is_public ? 'Active (Public)' : 'Hidden (Custom)') : 'Inactive'}
                  </Badge>
                </div>

                <div className={styles.planPrice}>
                  ${plan.price_usd?.toFixed(2) || '0.00'} <span>/ month</span>
                </div>

                <div className={styles.limitsList}>
                  <div className={styles.limitRow}>
                    <span>Max Competitor Stores:</span>
                    <span className={styles.limitVal}>{plan.max_stores} stores</span>
                  </div>
                  <div className={styles.limitRow}>
                    <span>Max Tracked Products:</span>
                    <span className={styles.limitVal}>{plan.max_tracked_products} items</span>
                  </div>
                  <div className={styles.limitRow}>
                    <span>Min Check Interval:</span>
                    <span className={styles.limitVal}>{plan.poll_interval_mins} mins</span>
                  </div>
                </div>
              </div>

              <Button size="sm" variant="secondary" onClick={() => handleOpenEdit(plan)}>
                ✏️ Edit Parameters
              </Button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
