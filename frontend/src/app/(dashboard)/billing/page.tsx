'use client';

import useSWR from 'swr';
import { billingApi } from '@/lib/api';
import { Card, CardHeader, CardBody } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { PageLoader } from '@/components/ui/Spinner';
import styles from './page.module.css';

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

function PlanCard({ plan, current, onUpgrade }: {
  plan: { id: string; name: string; price_usd: number | null; max_stores: number; max_tracked_products: number; poll_interval_mins: number; is_active: boolean };
  current: boolean;
  onUpgrade: (planId: string) => void;
}) {
  const features = [
    `${plan.max_stores} competitor stores`,
    `${plan.max_tracked_products} tracked products`,
    `${plan.poll_interval_mins} min poll interval`,
  ];

  return (
    <Card glow={current} className={[styles.planCard, current ? styles.planCardCurrent : ''].join(' ')}>
      <CardBody>
        {current && <div className={styles.currentBadge}>Current plan</div>}
        <h3 className={styles.planName}>{plan.name}</h3>
        <div className={styles.planPrice}>
          {plan.price_usd === 0 || plan.price_usd === null ? (
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
        {!current && (plan.price_usd ?? 0) > 0 && (
          <Button
            size="sm"
            style={{ width: '100%', marginTop: 'auto' }}
            onClick={() => onUpgrade(plan.id)}
          >
            Upgrade to {plan.name}
          </Button>
        )}
        {current && (
          <div className={styles.currentPill}>✓ Active</div>
        )}
      </CardBody>
    </Card>
  );
}

export default function BillingPage() {
  const { data: plans, isLoading: plansLoading } = useSWR('plans', () => billingApi.plans());
  const { data: usage, isLoading: usageLoading } = useSWR('user-usage', () => billingApi.getUsage());
  const { data: subscription } = useSWR('subscription', () => billingApi.subscription());

  async function handleUpgrade(planId: string) {
    const origin = window.location.origin;
    try {
      const { checkout_url } = await billingApi.checkout(
        planId,
        `${origin}/billing?success=1`,
        `${origin}/billing`,
      );
      window.location.href = checkout_url;
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : 'Checkout failed');
    }
  }

  async function handlePortal() {
    const origin = window.location.origin;
    try {
      const { portal_url } = await billingApi.portal(`${origin}/billing`);
      window.location.href = portal_url;
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : 'Could not open billing portal');
    }
  }

  if (plansLoading || usageLoading) return <PageLoader />;

  const currentPlanName = usage?.plan_name ?? 'free';

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <div>
          <h1>Billing &amp; Plan</h1>
          <p>Manage your subscription and usage</p>
        </div>
        {subscription && (
          <Button variant="secondary" onClick={handlePortal}>Manage Subscription</Button>
        )}
      </div>

      {/* Usage meters */}
      {usage && (
        <Card>
          <CardHeader>
            <h3>Current Usage &amp; Plan Limits</h3>
            <Badge variant="accent">{usage.plan_name} plan</Badge>
          </CardHeader>
          <CardBody>
            <div className={styles.meters}>
              <UsageMeter
                label="Competitor Stores"
                current={usage.current_stores}
                max={usage.max_stores}
              />
              <UsageMeter
                label="Tracked Products"
                current={usage.current_tracked_products}
                max={usage.max_tracked_products}
              />
              <UsageMeter
                label="VIP Priority Items"
                current={usage.current_priority_products}
                max={usage.max_priority_products}
              />
              <div style={{ fontSize: '0.875rem', color: '#94a3b8', marginTop: '0.5rem' }}>
                ⚡ Minimum Monitoring Check Interval: <strong style={{ color: '#38bdf8' }}>{usage.min_poll_interval_mins} mins</strong>
              </div>
            </div>
            {subscription?.current_period_end && (
              <p className={styles.renewalNote}>
                Next renewal: {new Date(subscription.current_period_end).toLocaleDateString()}
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
            current={plan.name === currentPlanName}
            onUpgrade={handleUpgrade}
          />
        ))}
      </div>
    </div>
  );
}
