'use client';

import { useState } from 'react';
import useSWR from 'swr';
import { adminApi, Plan } from '@/lib/api';
import { Card, CardHeader, CardBody } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import styles from './page.module.css';

export default function AdminPlansPage() {
  const { data: plans, error, mutate, isLoading } = useSWR('admin-plans', adminApi.listPlans);
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
                <label className={styles.label}>Max VIP Priority Products</label>
                <input
                  type="number"
                  className={styles.input}
                  value={formData.max_priority_products ?? 0}
                  onChange={e => setFormData({ ...formData, max_priority_products: parseInt(e.target.value) || 0 })}
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
                  <div className={styles.limitRow}>
                    <span>VIP Priority Quota:</span>
                    <span className={styles.limitVal}>{plan.max_priority_products || 0} items</span>
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
