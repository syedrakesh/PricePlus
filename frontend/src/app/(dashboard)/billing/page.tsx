'use client';

import { useState } from 'react';
import useSWR, { mutate as globalMutate } from 'swr';
import { billingApi, Subscription, Plan } from '@/lib/api';
import { Card, CardHeader, CardBody } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { PageLoader } from '@/components/ui/Spinner';
import styles from './page.module.css';

// ─── Usage Meter ──────────────────────────────────────────────────────────────

function UsageMeter({ label, current, max }: { label: string; current: number; max: number }) {
  const pct = max > 0 ? Math.min((current / max) * 100, 100) : 0;
  const color = pct >= 90 ? '#ef4444' : pct >= 70 ? '#f59e0b' : '#10b981';
  return (
    <div className={styles.meter}>
      <div className={styles.meterHeader}>
        <span className={styles.meterLabel}>{label}</span>
        <span className={styles.meterCount}>{current} / {max}</span>
      </div>
      <div className={styles.meterTrack}>
        <div className={styles.meterFill} style={{ width: `${pct}%`, background: color }} />
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
  loading,
}: {
  plan: Plan;
  currentPlanId: string | undefined;
  currentStatus: string | undefined;
  onUpgrade: (planId: string) => void;
  onDowngrade: (planId: string) => void;
  onCancel: () => void;
  loading: boolean;
}) {
  const isCurrent = plan.id === currentPlanId;
  const currentPrice = 0; // will be compared below
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
              {/* Cancel button — only for paid plans */}
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
            /* Downgrade to Free */
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

// ─── Status Banner ────────────────────────────────────────────────────────────

function StatusBanner({ subscription }: { subscription: Subscription }) {
  if (subscription.status === 'past_due') {
    return (
      <div className={styles.warningBanner}>
        ⚠️ <strong>Payment failed.</strong> Your subscription is past due. Please update your payment method to avoid service interruption.
        {subscription.stripe_customer_id && (
          <span> Use <strong>Manage Subscription</strong> to update billing.</span>
        )}
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

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function BillingPage() {
  const { data: plans, isLoading: plansLoading } = useSWR('plans', () => billingApi.plans());
  const { data: usage, isLoading: usageLoading } = useSWR('user-usage', () => billingApi.getUsage());
  const { data: subscription, mutate: mutateSubscription } = useSWR('subscription', () => billingApi.subscription());

  const [actionLoading, setActionLoading] = useState(false);
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

  async function handleUpgrade(planId: string) {
    const origin = window.location.origin;
    setActionLoading(true);
    try {
      const { checkout_url } = await billingApi.checkout(
        planId,
        `${origin}/billing?success=1`,
        `${origin}/billing`,
      );
      // If Stripe redirect — navigate away; if direct upgrade — same page
      if (checkout_url === `${origin}/billing?success=1`) {
        showToast('success', 'Plan upgraded successfully!');
        await refreshAll();
      } else {
        window.location.href = checkout_url;
      }
    } catch (e: unknown) {
      showToast('error', e instanceof Error ? e.message : 'Upgrade failed');
    } finally {
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

  // Check success redirect from Stripe
  if (typeof window !== 'undefined' && window.location.search.includes('success=1')) {
    showToast('success', 'Payment successful! Your plan has been upgraded.');
    // Remove query param
    window.history.replaceState({}, '', '/billing');
  }

  if (plansLoading || usageLoading) return <PageLoader />;

  const currentPlanId = usage?.plan_id;
  const currentStatus = subscription?.status;
  const hasStripe = !!(subscription?.stripe_customer_id);
  const isPaidDirectSub = subscription && !subscription.is_direct === false && (subscription.plan?.price_usd ?? 0) > 0;

  return (
    <div className={styles.page}>
      {/* Toast notification */}
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
          {hasStripe && (
            <Button variant="secondary" onClick={handlePortal} disabled={actionLoading} id="manage-subscription-btn">
              Manage Subscription
            </Button>
          )}
        </div>
      </div>

      {/* Status banners */}
      {subscription && <StatusBanner subscription={subscription} />}

      {/* Usage meters */}
      {usage && (
        <Card>
          <CardHeader>
            <h3>Current Usage & Plan Limits</h3>
            <Badge variant="accent">{usage.plan_name}</Badge>
          </CardHeader>
          <CardBody>
            <div className={styles.meters}>
              <UsageMeter label="Competitor Stores" current={usage.current_stores} max={usage.max_stores} />
              <UsageMeter label="Tracked Products" current={usage.current_tracked_products} max={usage.max_tracked_products} />
              <div style={{ fontSize: '0.875rem', color: '#94a3b8', marginTop: '0.5rem' }}>
                ⚡ Minimum Monitoring Interval: <strong style={{ color: '#38bdf8' }}>{usage.min_poll_interval_mins} mins</strong>
              </div>
            </div>
            {subscription?.current_period_end && subscription.status !== 'canceled' && (
              <p className={styles.renewalNote}>
                {subscription.status === 'trialing' ? '🎁 Trial ends:' : '🔄 Next renewal:'}
                {' '}{new Date(subscription.current_period_end).toLocaleDateString()}
              </p>
            )}
          </CardBody>
        </Card>
      )}

      {/* Plan cards */}
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
            loading={actionLoading}
          />
        ))}
      </div>
    </div>
  );
}
