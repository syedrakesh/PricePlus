'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import useSWR, { mutate as globalMutate } from 'swr';
import { billingApi, Subscription, Plan } from '@/lib/api';
import { useAuth } from '@/context/AuthContext';
import { Card, CardHeader, CardBody } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { PageLoader } from '@/components/ui/Spinner';
import styles from './page.module.css';

// ─── Usage Meter ──────────────────────────────────────────────────────────────

function UsageMeter({ label, current, max }: { label: string; current: number; max: number }) {
  const isUnlimited = max >= 99999;
  const pct = !isUnlimited && max > 0 ? Math.min((current / max) * 100, 100) : 0;
  const color = pct >= 90 ? '#ef4444' : pct >= 70 ? '#f59e0b' : '#10b981';
  return (
    <div className={styles.meter}>
      <div className={styles.meterHeader}>
        <span className={styles.meterLabel}>{label}</span>
        <span className={styles.meterCount}>{current} / {isUnlimited ? '∞ Unlimited' : max}</span>
      </div>
      <div className={styles.meterTrack}>
        <div className={styles.meterFill} style={{ width: `${isUnlimited ? 100 : pct}%`, background: isUnlimited ? '#38bdf8' : color }} />
      </div>
    </div>
  );
}

// ─── Plan Card ────────────────────────────────────────────────────────────────

function PlanCard({
  plan,
  currentPlanId,
  currentStatus,
  onUpgrade,
  onDowngrade,
  onCancel,
  onOpenExtend,
  loading,
}: {
  plan: Plan;
  currentPlanId: string | undefined;
  currentStatus: string | undefined;
  onUpgrade: (planId: string) => void;
  onDowngrade: (planId: string) => void;
  onCancel: () => void;
  onOpenExtend: () => void;
  loading: boolean;
}) {
  const isCurrent = plan.id === currentPlanId;
  const isPaid = (plan.price_usd ?? 0) > 0;
  const isFree = !isPaid;

  const features = [
    `${plan.max_stores} competitor store${plan.max_stores !== 1 ? 's' : ''}`,
    `${plan.max_tracked_products} tracked products`,
    `Every ${plan.poll_interval_mins} min monitoring`,
    ...(plan.features?.csv_export ? ['CSV export'] : []),
    ...(plan.features?.instant_alerts ? ['Instant alerts'] : []),
    ...(plan.features?.dedicated_proxy ? ['Dedicated proxy'] : []),
  ];

  return (
    <Card glow={isCurrent} className={[styles.planCard, isCurrent ? styles.planCardCurrent : ''].join(' ')}>
      <CardBody>
        <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
          {isCurrent && <div className={styles.currentBadge}>Current plan</div>}
          <h3 className={styles.planName}>{plan.name}</h3>
          <div className={styles.planPrice}>
            {isFree ? (
              <span className={styles.planPriceVal}>Free</span>
            ) : (
              <>
                <span className={styles.planPriceVal}>${plan.price_usd}</span>
                <span className={styles.planPricePer}>/mo</span>
              </>
            )}
          </div>
          <ul className={styles.planFeatures}>
            {features.map(f => (
              <li key={f} className={styles.planFeature}><span className={styles.check}>✓</span> {f}</li>
            ))}
          </ul>

          <div style={{ marginTop: 'auto', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            {isCurrent ? (
              <>
                <div className={styles.currentPill}>✓ Active Plan</div>
                <Button
                  id={`extend-plan-${plan.id}`}
                  size="sm"
                  variant="primary"
                  onClick={onOpenExtend}
                  disabled={loading}
                  style={{ width: '100%' }}
                >
                  Extend Subscription ⏳
                </Button>
                {isPaid && currentStatus !== 'canceled' && (
                  <Button
                    id={`cancel-plan-${plan.id}`}
                    size="sm"
                    variant="secondary"
                    onClick={onCancel}
                    disabled={loading}
                    style={{ fontSize: '0.8rem', opacity: 0.75 }}
                  >
                    Cancel Subscription
                  </Button>
                )}
              </>
            ) : isFree ? (
              currentStatus !== 'canceled' && (
                <Button
                  id={`downgrade-free-${plan.id}`}
                  size="sm"
                  variant="secondary"
                  onClick={() => onDowngrade(plan.id)}
                  disabled={loading}
                >
                  Switch to Free
                </Button>
              )
            ) : isPaid ? (
              <Button
                id={`upgrade-plan-${plan.id}`}
                size="sm"
                onClick={() => onUpgrade(plan.id)}
                disabled={loading}
                style={{ width: '100%' }}
              >
                Switch to {plan.name}
              </Button>
            ) : null}
          </div>
        </div>
      </CardBody>
    </Card>
  );
}

// ─── Subscription Extension Modal ──────────────────────────────────────────────

function ExtendSubscriptionModal({
  isOpen,
  onClose,
  onConfirm,
  currentPeriodEnd,
  planName,
  loading,
}: {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: (months: number) => void;
  currentPeriodEnd?: string | null;
  planName?: string;
  loading: boolean;
}) {
  const [selectedMonths, setSelectedMonths] = useState<number>(1);

  if (!isOpen) return null;

  const baseDate = currentPeriodEnd && new Date(currentPeriodEnd) > new Date()
    ? new Date(currentPeriodEnd)
    : new Date();

  const newPeriodEnd = new Date(baseDate);
  newPeriodEnd.setDate(newPeriodEnd.getDate() + selectedMonths * 30);

  return (
    <div className={styles.modalOverlay} onClick={onClose}>
      <div className={styles.modalContent} onClick={e => e.stopPropagation()}>
        <div className={styles.modalHeader}>
          <h2>⏳ Extend Subscription</h2>
          <p>Add time to your {planName ? <strong>{planName}</strong> : ''} subscription at any time.</p>
        </div>

        <div className={styles.durationGrid}>
          <div
            className={[styles.durationCard, selectedMonths === 1 ? styles.durationCardSelected : ''].join(' ')}
            onClick={() => setSelectedMonths(1)}
          >
            <div className={styles.durationMonths}>+1 Month</div>
            <span className={styles.durationBadge}>30 Days</span>
          </div>

          <div
            className={[styles.durationCard, selectedMonths === 3 ? styles.durationCardSelected : ''].join(' ')}
            onClick={() => setSelectedMonths(3)}
          >
            <div className={styles.durationMonths}>+3 Months</div>
            <span className={styles.durationBadge}>90 Days</span>
          </div>

          <div
            className={[styles.durationCard, selectedMonths === 12 ? styles.durationCardSelected : ''].join(' ')}
            onClick={() => setSelectedMonths(12)}
          >
            <div className={styles.durationMonths}>+1 Year</div>
            <span className={styles.durationBadge}>365 Days</span>
          </div>
        </div>

        <div className={styles.datePreview}>
          <div>📅 Current expiration: <strong>{currentPeriodEnd ? new Date(currentPeriodEnd).toLocaleDateString() : 'Active Now'}</strong></div>
          <div>✨ Extended expiration: <span className={styles.datePreviewHighlight}>{newPeriodEnd.toLocaleDateString()}</span></div>
        </div>

        <div className={styles.modalActions}>
          <Button variant="secondary" onClick={onClose} disabled={loading}>
            Cancel
          </Button>
          <Button variant="primary" onClick={() => onConfirm(selectedMonths)} disabled={loading}>
            {loading ? 'Extending...' : `Confirm Extension (+${selectedMonths} mo)`}
          </Button>
        </div>
      </div>
    </div>
  );
}

// ─── Status Banner ────────────────────────────────────────────────────────────

function StatusBanner({ subscription }: { subscription: Subscription }) {
  if (subscription.status === 'past_due') {
    return (
      <div className={styles.warningBanner}>
        ⚠️ <strong>Payment failed.</strong> Your subscription is past due. Please update your payment method to avoid service interruption.
      </div>
    );
  }
  if (subscription.status === 'trialing') {
    return (
      <div className={styles.infoBanner}>
        🎉 <strong>You are on a free trial.</strong> Enjoy full {subscription.plan?.name} features
        {subscription.current_period_end && (
          <span> until {new Date(subscription.current_period_end).toLocaleDateString()}.</span>
        )}
      </div>
    );
  }
  if (subscription.status === 'canceled') {
    return (
      <div className={styles.warningBanner}>
        ℹ️ <strong>Subscription canceled.</strong>
        {subscription.current_period_end
          ? ` Access continues until ${new Date(subscription.current_period_end).toLocaleDateString()}.`
          : ' You have been moved to the Free plan.'}
      </div>
    );
  }
  return null;
}

export default function BillingPage() {
  const { user, isAdmin } = useAuth();
  const { data: plans, isLoading: plansLoading } = useSWR('plans', () => billingApi.plans());
  const { data: usage, isLoading: usageLoading } = useSWR('user-usage', () => billingApi.getUsage());
  const { data: subscription, mutate: mutateSubscription } = useSWR('subscription', () => billingApi.subscription());

  const [actionLoading, setActionLoading] = useState(false);
  const [isExtendModalOpen, setIsExtendModalOpen] = useState(false);
  const [toast, setToast] = useState<{ type: 'success' | 'error'; msg: string } | null>(null);

  function showToast(type: 'success' | 'error', msg: string) {
    setToast({ type, msg });
    setTimeout(() => setToast(null), 5000);
  }

  async function refreshAll() {
    await Promise.all([
      globalMutate('plans'),
      globalMutate('user-usage'),
      mutateSubscription(),
      globalMutate('entitlements'),
    ]);
  }

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const urlParams = new URLSearchParams(window.location.search);
    const sessionId = urlParams.get('session_id');

    if (sessionId) {
      setActionLoading(true);
      billingApi.verifySession(sessionId)
        .then(res => {
          showToast('success', `Payment successful! Upgraded to ${res.plan_name} plan.`);
          refreshAll();
        })
        .catch(err => {
          console.warn('Session verify note:', err);
          refreshAll();
        })
        .finally(() => {
          setActionLoading(false);
          window.history.replaceState({}, '', '/billing');
        });
    }
  }, []);

  async function handleUpgrade(planId: string) {
    const origin = window.location.origin;
    setActionLoading(true);
    try {
      const { checkout_url } = await billingApi.checkout(
        planId,
        `${origin}/billing?session_id={CHECKOUT_SESSION_ID}`,
        `${origin}/billing`,
      );
      window.location.href = checkout_url;
    } catch (e: unknown) {
      showToast('error', e instanceof Error ? e.message : 'Upgrade failed');
      setActionLoading(false);
    }
  }

  async function handleDowngrade(planId: string) {
    setActionLoading(true);
    try {
      await billingApi.downgrade(planId);
      showToast('success', 'Plan changed successfully.');
      await refreshAll();
    } catch (e: unknown) {
      showToast('error', e instanceof Error ? e.message : 'Plan change failed');
    } finally {
      setActionLoading(false);
    }
  }

  async function handleExtend(months: number) {
    setIsExtendModalOpen(false);
    setActionLoading(true);
    const planIdToUse = currentPlanId || plans?.find(p => p.slug !== 'free')?.id;
    if (!planIdToUse) {
      showToast('error', 'No active paid plan available to extend.');
      setActionLoading(false);
      return;
    }

    const origin = window.location.origin;
    try {
      const { checkout_url } = await billingApi.checkout(
        planIdToUse,
        `${origin}/billing?session_id={CHECKOUT_SESSION_ID}`,
        `${origin}/billing`,
      );
      window.location.href = checkout_url;
    } catch (e: unknown) {
      showToast('error', e instanceof Error ? e.message : 'Extension checkout failed');
      setActionLoading(false);
    }
  }

  async function handleCancel() {
    if (!confirm('Are you sure you want to cancel your subscription?')) return;
    setActionLoading(true);
    try {
      const result = await billingApi.cancel();
      showToast('success', result.message);
      await refreshAll();
    } catch (e: unknown) {
      showToast('error', e instanceof Error ? e.message : 'Cancellation failed');
    } finally {
      setActionLoading(false);
    }
  }

  async function handlePortal() {
    const origin = window.location.origin;
    setActionLoading(true);
    try {
      const { portal_url } = await billingApi.portal(`${origin}/billing`);
      window.location.href = portal_url;
    } catch (e: unknown) {
      showToast('error', e instanceof Error ? e.message : 'Could not open billing portal');
      setActionLoading(false);
    }
  }

  if (typeof window !== 'undefined' && window.location.search.includes('success=1')) {
    showToast('success', 'Payment successful! Your plan has been upgraded.');
    window.history.replaceState({}, '', '/billing');
  }

  if (plansLoading || usageLoading) return <PageLoader />;

  const currentPlanId = usage?.plan_id;
  const currentStatus = subscription?.status;
  const hasStripe = !!(subscription?.stripe_customer_id);

  // ─── SuperAdmin Dedicated View ──────────────────────────────────────────────
  if (isAdmin || user?.is_superuser) {
    return (
      <div className={styles.page}>
        <div className={styles.header}>
          <div>
            <h1>⚡ Billing & Platform Administration</h1>
            <p>System Administrator Control Panel — Unlimited Operational Access</p>
          </div>
          <Badge variant="accent">System Administrator</Badge>
        </div>

        <Card glow>
          <CardHeader>
            <h3>👑 System Administrator Account</h3>
            <Badge variant="success">Unlimited Access</Badge>
          </CardHeader>
          <CardBody>
            <p style={{ color: '#94a3b8', fontSize: '0.875rem', marginBottom: '1.25rem' }}>
              As a System Administrator, your account automatically bypasses all customer store and product quota limits.
              You do not require a paid customer subscription.
            </p>

            <div className={styles.meters}>
              <UsageMeter label="Competitor Stores" current={usage?.current_stores ?? 0} max={999999} />
              <UsageMeter label="Tracked Products" current={usage?.current_tracked_products ?? 0} max={999999} />
              <div style={{ fontSize: '0.875rem', color: '#94a3b8', marginTop: '0.5rem' }}>
                ⚡ Operational Polling Speed: <strong style={{ color: '#38bdf8' }}>1 min (Max Speed)</strong>
              </div>
            </div>

            <div style={{ marginTop: '1.5rem', paddingTop: '1.25rem', borderTop: '1px solid rgba(255, 255, 255, 0.08)', display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
              <Link href="/admin/plans">
                <Button variant="primary">👑 Manage Customer Plans</Button>
              </Link>
              <Link href="/admin/users">
                <Button variant="secondary">👥 Manage User Subscriptions</Button>
              </Link>
              <Link href="/admin/permissions">
                <Button variant="secondary">🔒 System RBAC Matrix</Button>
              </Link>
            </div>
          </CardBody>
        </Card>
      </div>
    );
  }

  // ─── Regular Customer View ──────────────────────────────────────────────────
  return (
    <div className={styles.page}>
      {toast && (
        <div className={toast.type === 'success' ? styles.toastSuccess : styles.toastError}>
          {toast.msg}
        </div>
      )}

      <div className={styles.header}>
        <div>
          <h1>Billing & Plan</h1>
          <p>Manage your subscription and usage</p>
        </div>
        <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center', flexWrap: 'wrap' }}>
          {subscription && (
            <Badge variant={
              subscription.status === 'active' ? 'success' :
              subscription.status === 'trialing' ? 'info' :
              subscription.status === 'past_due' ? 'danger' :
              'warning'
            }>
              {subscription.status_label}
            </Badge>
          )}
          <Button variant="primary" onClick={() => setIsExtendModalOpen(true)} disabled={actionLoading} id="extend-subscription-header-btn">
            Extend Subscription ⏳
          </Button>
          {hasStripe && (
            <Button variant="secondary" onClick={handlePortal} disabled={actionLoading} id="manage-subscription-btn">
              Manage Subscription
            </Button>
          )}
        </div>
      </div>

      {subscription && <StatusBanner subscription={subscription} />}

      {usage && (
        <Card>
          <CardHeader>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <h3>Current Usage & Plan Limits</h3>
              <Badge variant="accent">{usage.plan_name}</Badge>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              {subscription?.current_period_end && subscription.status !== 'canceled' && (() => {
                const periodEnd = new Date(subscription.current_period_end);
                const now = new Date();
                const diffMs = periodEnd.getTime() - now.getTime();
                const daysLeft = diffMs > 0 ? Math.ceil(diffMs / (1000 * 60 * 60 * 24)) : 0;
                return (
                  <Badge variant={daysLeft <= 3 ? 'danger' : daysLeft <= 7 ? 'warning' : 'accent'}>
                    ⏳ {daysLeft} {daysLeft === 1 ? 'day' : 'days'} left
                  </Badge>
                );
              })()}
              <Button size="sm" variant="secondary" onClick={() => setIsExtendModalOpen(true)} disabled={actionLoading}>
                + Extend Period ⏳
              </Button>
            </div>
          </CardHeader>
          <CardBody>
            <div className={styles.meters}>
              <UsageMeter label="Competitor Stores" current={usage.current_stores} max={usage.max_stores} />
              <UsageMeter label="Tracked Products" current={usage.current_tracked_products} max={usage.max_tracked_products} />
              <div style={{ fontSize: '0.875rem', color: '#94a3b8', marginTop: '0.5rem' }}>
                ⚡ Minimum Monitoring Interval: <strong style={{ color: '#38bdf8' }}>{usage.min_poll_interval_mins} mins</strong>
              </div>
            </div>
            {subscription?.current_period_end && subscription.status !== 'canceled' && (() => {
              const periodEnd = new Date(subscription.current_period_end);
              const now = new Date();
              const diffMs = periodEnd.getTime() - now.getTime();
              const daysLeft = diffMs > 0 ? Math.ceil(diffMs / (1000 * 60 * 60 * 24)) : 0;
              return (
                <p className={styles.renewalNote} style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '12px' }}>
                  <span>{subscription.status === 'trialing' ? '🎁 Trial ends:' : '🔄 Next renewal:'} {periodEnd.toLocaleDateString()}</span>
                  <span style={{
                    background: daysLeft <= 3 ? 'rgba(239, 68, 68, 0.2)' : daysLeft <= 7 ? 'rgba(234, 179, 8, 0.2)' : 'rgba(56, 189, 248, 0.15)',
                    color: daysLeft <= 3 ? '#f87171' : daysLeft <= 7 ? '#facc15' : '#38bdf8',
                    border: '1px solid currentColor',
                    padding: '2px 8px', borderRadius: '12px', fontSize: '0.75rem', fontWeight: 600
                  }}>
                    ⏳ {daysLeft} {daysLeft === 1 ? 'day' : 'days'} left
                  </span>
                </p>
              );
            })()}
          </CardBody>
        </Card>
      )}

      <div className={styles.plans}>
        {plans?.map(plan => (
          <PlanCard
            key={plan.id}
            plan={plan}
            currentPlanId={currentPlanId}
            currentStatus={currentStatus}
            onUpgrade={handleUpgrade}
            onDowngrade={handleDowngrade}
            onCancel={handleCancel}
            onOpenExtend={() => setIsExtendModalOpen(true)}
            loading={actionLoading}
          />
        ))}
      </div>

      <ExtendSubscriptionModal
        isOpen={isExtendModalOpen}
        onClose={() => setIsExtendModalOpen(false)}
        onConfirm={handleExtend}
        currentPeriodEnd={subscription?.current_period_end}
        planName={usage?.plan_name || subscription?.plan?.name}
        loading={actionLoading}
      />
    </div>
  );
}
