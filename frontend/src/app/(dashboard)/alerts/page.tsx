'use client';

import { useState } from 'react';
import useSWR from 'swr';
import Link from 'next/link';
import { alertsApi, trackingApi, TrackedProduct, AlertRule } from '@/lib/api';
import { Card, CardHeader, CardBody } from '@/components/ui/Card';
import { Badge, StatusBadge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { EmptyState, PageLoader } from '@/components/ui/Spinner';
import styles from './page.module.css';

export default function AlertsPage() {
  const { data: rules, isLoading: rulesLoading, mutate: mutateRules } = useSWR('alert-rules', () => alertsApi.listRules());
  const { data: alerts, isLoading: alertsLoading } = useSWR('alerts', () => alertsApi.listAlerts());

  async function handleToggle(id: string) {
    await alertsApi.toggleRule(id);
    mutateRules();
  }

  async function handleDelete(id: string) {
    if (!confirm('Delete this alert rule?')) return;
    await alertsApi.deleteRule(id);
    mutateRules();
  }

  const conditionLabel: Record<string, string> = {
    any_change: 'Any change',
    price_drop: 'Price drops',
    price_rise: 'Price rises',
    price_drop_pct: 'Price drops by %',
    price_increase_pct: 'Price increases by %',
    price_below: 'Price falls below $',
    price_above: 'Price rises above $',
  };

  const { data: trackedData } = useSWR('tracked-products', () => trackingApi.list());
  const [showModal, setShowModal] = useState(false);
  const [editingRuleId, setEditingRuleId] = useState<string | null>(null);
  const [ruleScope, setRuleScope] = useState<'universal' | 'product'>('universal');
  const [selectedTrackedId, setSelectedTrackedId] = useState('');
  const [conditionType, setConditionType] = useState('price_drop_pct');
  const [thresholdPct, setThresholdPct] = useState('5');
  const [thresholdPrice, setThresholdPrice] = useState('');
  const [selectedChannels, setSelectedChannels] = useState<string[]>(['email']);
  const [webhookUrl, setWebhookUrl] = useState('');
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState('');

  function toggleChannel(ch: string) {
    setSelectedChannels(prev => {
      if (prev.includes(ch)) {
        if (prev.length <= 1) return prev;
        return prev.filter(c => c !== ch);
      }
      return [...prev, ch];
    });
  }

  function openCreateModal() {
    setEditingRuleId(null);
    setRuleScope('universal');
    setSelectedTrackedId('');
    setConditionType('price_drop_pct');
    setThresholdPct('5');
    setThresholdPrice('');
    setSelectedChannels(['email']);
    setWebhookUrl('');
    setCreateError('');
    setShowModal(true);
  }

  function openEditModal(rule: AlertRule) {
    setEditingRuleId(rule.id);
    setRuleScope(rule.tracked_product_id ? 'product' : 'universal');
    setSelectedTrackedId(rule.tracked_product_id || '');
    setConditionType(rule.condition_type || 'price_drop_pct');
    setThresholdPct(rule.threshold_pct !== null && rule.threshold_pct !== undefined ? String(rule.threshold_pct) : '');
    setThresholdPrice(rule.threshold_price !== null && rule.threshold_price !== undefined ? String(rule.threshold_price) : '');
    const chList = rule.channel ? rule.channel.split(',').map(c => c.trim()).filter(Boolean) : ['email'];
    setSelectedChannels(chList.length ? chList : ['email']);
    setWebhookUrl(rule.webhook_url || '');
    setCreateError('');
    setShowModal(true);
  }

  async function handleSaveRule(e: React.FormEvent) {
    e.preventDefault();
    if (ruleScope === 'product' && !selectedTrackedId) {
      setCreateError('Please select a tracked product');
      return;
    }

    if (!selectedChannels.length) {
      setCreateError('Please select at least one notification channel');
      return;
    }

    setCreateError('');
    setCreating(true);
    try {
      const payload = {
        tracked_product_id: ruleScope === 'universal' ? null : selectedTrackedId,
        condition_type: conditionType,
        threshold_pct: conditionType.includes('pct') && thresholdPct ? parseFloat(thresholdPct) : null,
        threshold_price: (conditionType === 'price_below' || conditionType === 'price_above') && thresholdPrice ? parseFloat(thresholdPrice) : null,
        channel: selectedChannels.join(','),
        webhook_url: selectedChannels.includes('webhook') ? webhookUrl : null,
      };

      if (editingRuleId) {
        await alertsApi.updateRule(editingRuleId, payload);
      } else {
        await alertsApi.createRule(payload);
      }
      setShowModal(false);
      setEditingRuleId(null);
      mutateRules();
    } catch (err: unknown) {
      setCreateError(err instanceof Error ? err.message : 'Failed to save alert rule');
    } finally {
      setCreating(false);
    }
  }

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <div>
          <h1>Alerts</h1>
          <p>Your alert rules and notification history</p>
        </div>
        <div style={{ display: 'flex', gap: '10px' }}>
          <Link href="/settings/notifications">
            <Button variant="secondary">⚙️ Notification Channels</Button>
          </Link>
          <Button onClick={openCreateModal}>+ Create Alert Rule</Button>
        </div>
      </div>

      {/* Alert Rules */}
      <Card>
        <CardHeader>
          <h3>Alert Rules</h3>
          <Badge variant="accent">{rules?.total ?? 0}</Badge>
        </CardHeader>
        {rulesLoading ? (
          <PageLoader />
        ) : !rules?.rules.length ? (
          <EmptyState
            icon="🔔"
            title="No alert rules created"
            description="Create a Universal Rule (e.g. alert me when ANY product drops in price by ≥ 5%) to automatically monitor all products across all stores."
          />
        ) : (
          <div className={styles.ruleList}>
            {rules.rules.map(rule => (
              <div key={rule.id} className={styles.ruleRow}>
                <div className={styles.ruleCondition}>
                  <span className={styles.ruleLabel}>
                    {conditionLabel[rule.condition_type] ?? rule.condition_type}
                  </span>
                  {rule.threshold_pct !== null && (
                    <span className={styles.ruleThreshold}>by ≥{rule.threshold_pct}%</span>
                  )}
                  {rule.threshold_price !== null && (
                    <span className={styles.ruleThreshold}>below ${rule.threshold_price}</span>
                  )}
                </div>
                <div className={styles.ruleMeta}>
                  {!rule.tracked_product_id ? (
                    <Badge variant="accent">Universal (All Stores)</Badge>
                  ) : (
                    <Badge variant="default">Specific Product</Badge>
                  )}
                  {rule.channel.split(',').map(ch => (
                    <Badge key={ch.trim()} variant="default">{ch.trim()}</Badge>
                  ))}
                  <StatusBadge status={rule.is_enabled ? 'active' : 'paused'} />
                  {rule.last_triggered_at && (
                    <span className={styles.ruleTriggered}>
                      Last: {new Date(rule.last_triggered_at).toLocaleDateString()}
                    </span>
                  )}
                </div>
                <div className={styles.ruleActions}>
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => openEditModal(rule)}
                  >
                    Edit ✏️
                  </Button>
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => handleToggle(rule.id)}
                  >
                    {rule.is_enabled ? 'Pause' : 'Enable'}
                  </Button>
                  <Button size="sm" variant="danger" onClick={() => handleDelete(rule.id)}>
                    Delete
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* Fired alerts */}
      <Card>
        <CardHeader>
          <h3>Notification History</h3>
          <Badge variant="default">{alerts?.total ?? 0}</Badge>
        </CardHeader>
        {alertsLoading ? (
          <PageLoader />
        ) : !alerts?.alerts.length ? (
          <EmptyState icon="📭" title="No alerts fired yet" description="Alerts will appear here when price changes trigger your rules." />
        ) : (
          <div className={styles.alertList}>
            {alerts.alerts.map(alert => (
              <div key={alert.id} className={styles.alertRow}>
                <span className={styles.alertIcon}>{alert.delivered ? '✅' : '⏳'}</span>
                <div className={styles.alertInfo}>
                  <span className={styles.alertSummary}>{alert.trigger_summary ?? 'Price change detected'}</span>
                  <span className={styles.alertTime}>{new Date(alert.created_at).toLocaleString()}</span>
                </div>
                <Badge variant="default">{alert.channel}</Badge>
                <StatusBadge status={alert.delivered ? 'active' : 'pending'} />
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* Create Rule Modal */}
      {showModal && (
        <div style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(4px)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100, padding: '16px'
        }} onClick={() => setShowModal(false)}>
          <div style={{
            background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-xl)',
            padding: '24px', width: '100%', maxWidth: '460px', boxShadow: 'var(--shadow-xl)'
          }} onClick={e => e.stopPropagation()}>
            <h3 style={{ fontSize: '18px', fontWeight: 700, marginBottom: '16px', color: 'var(--color-text)' }}>
              {editingRuleId ? 'Edit Alert Rule' : 'Create New Alert Rule'}
            </h3>

            <form onSubmit={handleSaveRule} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--color-text-2)', marginBottom: '6px' }}>
                  Rule Scope
                </label>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                  <button
                    type="button"
                    onClick={() => setRuleScope('universal')}
                    style={{
                      padding: '10px 12px', borderRadius: 'var(--radius-md)', textAlign: 'center', cursor: 'pointer',
                      border: ruleScope === 'universal' ? '2px solid var(--color-accent)' : '1px solid var(--color-border)',
                      background: ruleScope === 'universal' ? 'rgba(59,130,246,0.1)' : 'var(--color-surface-2)',
                      color: ruleScope === 'universal' ? 'var(--color-accent)' : 'var(--color-text)',
                      fontWeight: 600, fontSize: '13px'
                    }}
                  >
                    🌐 Universal (All Stores)
                  </button>
                  <button
                    type="button"
                    onClick={() => setRuleScope('product')}
                    style={{
                      padding: '10px 12px', borderRadius: 'var(--radius-md)', textAlign: 'center', cursor: 'pointer',
                      border: ruleScope === 'product' ? '2px solid var(--color-accent)' : '1px solid var(--color-border)',
                      background: ruleScope === 'product' ? 'rgba(59,130,246,0.1)' : 'var(--color-surface-2)',
                      color: ruleScope === 'product' ? 'var(--color-accent)' : 'var(--color-text)',
                      fontWeight: 600, fontSize: '13px'
                    }}
                  >
                    🎯 Specific Product
                  </button>
                </div>
              </div>

              {ruleScope === 'product' && (
                <div>
                  <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--color-text-2)', marginBottom: '4px' }}>
                    Select Tracked Product
                  </label>
                  <select
                    value={selectedTrackedId}
                    onChange={e => setSelectedTrackedId(e.target.value)}
                    required
                    style={{
                      width: '100%', padding: '10px 12px', borderRadius: 'var(--radius-md)',
                      border: '1px solid var(--color-border)', background: 'var(--color-surface-2)', color: 'var(--color-text)', fontSize: '14px'
                    }}
                  >
                    <option value="">Select a product...</option>
                    {trackedData?.tracked_products?.map(tp => (
                      <option key={tp.id} value={tp.id}>
                        {tp.title || tp.handle || tp.id}
                      </option>
                    ))}
                  </select>
                </div>
              )}

              <div>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--color-text-2)', marginBottom: '4px' }}>
                  Alert Condition
                </label>
                <select
                  value={conditionType}
                  onChange={e => setConditionType(e.target.value)}
                  style={{
                    width: '100%', padding: '10px 12px', borderRadius: 'var(--radius-md)',
                    border: '1px solid var(--color-border)', background: 'var(--color-surface-2)', color: 'var(--color-text)', fontSize: '14px'
                  }}
                >
                  <option value="price_drop_pct">Price Drops by %</option>
                  <option value="price_increase_pct">Price Increases by %</option>
                  <option value="price_below">Price Drops Below $ Amount</option>
                  <option value="any_change">Any Price Change</option>
                </select>
              </div>

              {conditionType.includes('pct') && (
                <div>
                  <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--color-text-2)', marginBottom: '4px' }}>
                    Threshold Percentage (%)
                  </label>
                  <input
                    type="number"
                    value={thresholdPct}
                    onChange={e => setThresholdPct(e.target.value)}
                    placeholder="e.g. 5"
                    style={{
                      width: '100%', padding: '10px 12px', borderRadius: 'var(--radius-md)',
                      border: '1px solid var(--color-border)', background: 'var(--color-surface-2)', color: 'var(--color-text)', fontSize: '14px'
                    }}
                  />
                </div>
              )}

              {conditionType === 'price_below' && (
                <div>
                  <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--color-text-2)', marginBottom: '4px' }}>
                    Target Price ($)
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    value={thresholdPrice}
                    onChange={e => setThresholdPrice(e.target.value)}
                    placeholder="e.g. 49.99"
                    style={{
                      width: '100%', padding: '10px 12px', borderRadius: 'var(--radius-md)',
                      border: '1px solid var(--color-border)', background: 'var(--color-surface-2)', color: 'var(--color-text)', fontSize: '14px'
                    }}
                  />
                </div>
              )}

              <div>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--color-text-2)', marginBottom: '6px' }}>
                  Notification Channels (Select one or more)
                </label>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '8px' }}>
                  {[
                    { id: 'email', label: '📧 Email' },
                    { id: 'telegram', label: '✈️ Telegram' },
                    { id: 'webhook', label: '🔗 Webhook' },
                  ].map(ch => {
                    const active = selectedChannels.includes(ch.id);
                    return (
                      <button
                        key={ch.id}
                        type="button"
                        onClick={() => toggleChannel(ch.id)}
                        style={{
                          padding: '10px 6px',
                          borderRadius: 'var(--radius-md)',
                          textAlign: 'center',
                          cursor: 'pointer',
                          border: active ? '2px solid var(--color-accent)' : '1px solid var(--color-border)',
                          background: active ? 'rgba(59,130,246,0.12)' : 'var(--color-surface-2)',
                          color: active ? 'var(--color-accent)' : 'var(--color-text)',
                          fontWeight: 600,
                          fontSize: '13px',
                          transition: 'all 0.15s ease',
                        }}
                      >
                        {active ? '✓ ' : ''}{ch.label}
                      </button>
                    );
                  })}
                </div>
              </div>

              {selectedChannels.includes('webhook') && (
                <div>
                  <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--color-text-2)', marginBottom: '4px' }}>
                    Webhook URL
                  </label>
                  <input
                    type="url"
                    required
                    value={webhookUrl}
                    onChange={e => setWebhookUrl(e.target.value)}
                    placeholder="https://api.yourdomain.com/webhooks/price-drop"
                    style={{
                      width: '100%', padding: '10px 12px', borderRadius: 'var(--radius-md)',
                      border: '1px solid var(--color-border)', background: 'var(--color-surface-2)', color: 'var(--color-text)', fontSize: '14px'
                    }}
                  />
                </div>
              )}

              {createError && (
                <div style={{ fontSize: '13px', color: 'var(--color-danger)', background: 'rgba(239,68,68,0.1)', padding: '8px 12px', borderRadius: '6px' }}>
                  ⚠️ {createError}
                </div>
              )}

              <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end', marginTop: '12px' }}>
                <Button type="button" variant="secondary" onClick={() => setShowModal(false)}>
                  Cancel
                </Button>
                <Button type="submit" loading={creating}>
                  {editingRuleId ? 'Save Changes' : 'Create Rule'}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
