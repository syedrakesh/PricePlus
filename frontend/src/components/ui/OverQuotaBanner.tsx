'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { billingApi, Entitlements } from '@/lib/api';
import styles from './OverQuotaBanner.module.css';

export function OverQuotaBanner() {
  const [entitlements, setEntitlements] = useState<Entitlements | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let isMounted = true;
    billingApi
      .entitlements()
      .then((data) => {
        if (isMounted) setEntitlements(data);
      })
      .catch(() => {
        /* Ignore error if not loaded */
      });
    return () => {
      isMounted = false;
    };
  }, []);

  async function handleRenewOrUpgrade(e: React.MouseEvent) {
    e.preventDefault();
    setLoading(true);

    try {
      // 1. Attempt to launch Stripe Customer Portal directly
      const res = await billingApi.portal(window.location.href);
      if (res?.portal_url) {
        window.location.href = res.portal_url;
        return;
      }
    } catch {
      /* Fallback to /billing page on error or direct sub */
    } finally {
      setLoading(false);
    }

    // Navigating to /billing
    if (window.location.pathname === '/billing') {
      window.scrollTo({ top: 0, behavior: 'smooth' });
    } else {
      window.location.href = '/billing';
    }
  }

  if (!entitlements) return null;

  const pausedStores = entitlements.paused_stores ?? 0;
  const pausedProducts = entitlements.paused_tracked_products ?? 0;
  const isOverLimit =
    entitlements.is_over_limit || pausedStores > 0 || pausedProducts > 0;

  const subStatus = (entitlements.subscription_status || '').toLowerCase();
  const isSubAlert = subStatus === 'canceled' || subStatus === 'past_due' || subStatus === 'expired';

  // Pre-expiration warning calculation: Check if current_period_end is within 7 days
  let daysUntilExpiry: number | null = null;
  let formattedExpiryDate: string | null = null;

  if (entitlements.current_period_end && (subStatus === 'active' || subStatus === 'trialing')) {
    const periodEnd = new Date(entitlements.current_period_end);
    const now = new Date();
    const diffMs = periodEnd.getTime() - now.getTime();
    if (diffMs > 0) {
      daysUntilExpiry = Math.ceil(diffMs / (1000 * 60 * 60 * 24));
      formattedExpiryDate = periodEnd.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    }
  }

  const isExpiringSoon = daysUntilExpiry !== null && daysUntilExpiry <= 7;

  if (!isOverLimit && !isSubAlert && !isExpiringSoon) return null;

  if (isExpiringSoon) {
    return (
      <div className={styles.banner} style={{ background: 'rgba(234, 179, 8, 0.15)', borderColor: 'rgba(234, 179, 8, 0.4)' }}>
        <div className={styles.content}>
          <span className={styles.icon}>⏰</span>
          <div className={styles.text}>
            <strong className={styles.strong}>Subscription Expiring Soon:</strong>{' '}
            Your {entitlements.plan_name} plan subscription will end in <strong className={styles.strong}>{daysUntilExpiry} day{daysUntilExpiry === 1 ? '' : 's'}</strong> (on {formattedExpiryDate}). Update your payment details or renew now to prevent service interruption.
          </div>
        </div>
        <div className={styles.actions}>
          <button onClick={handleRenewOrUpgrade} disabled={loading} className={styles.upgradeBtn}>
            {loading ? 'Opening Portal...' : 'Renew / Update Payment →'}
          </button>
        </div>
      </div>
    );
  }

  if (isSubAlert) {
    return (
      <div className={styles.banner}>
        <div className={styles.content}>
          <span className={styles.icon}>⚠️</span>
          <div className={styles.text}>
            <strong className={styles.strong}>Account Subscription Alert:</strong>{' '}
            Your subscription status is <strong className={styles.strong}>{entitlements.subscription_status}</strong>. Upgrade or renew your subscription to reactivate full feature access ({entitlements.max_stores} Store, {entitlements.max_tracked_products} Products).
          </div>
        </div>
        <div className={styles.actions}>
          <button onClick={handleRenewOrUpgrade} disabled={loading} className={styles.upgradeBtn}>
            {loading ? 'Opening Portal...' : 'Renew / Upgrade Plan'}
          </button>
        </div>
      </div>
    );
  }

  const details: string[] = [];
  if (pausedStores > 0) {
    details.push(`${pausedStores} store${pausedStores > 1 ? 's' : ''}`);
  }
  if (pausedProducts > 0) {
    details.push(
      `${pausedProducts} product${pausedProducts > 1 ? 's' : ''}`
    );
  }

  const pausedSummary =
    details.length > 0 ? details.join(' and ') : 'Some items';

  return (
    <div className={styles.banner}>
      <div className={styles.content}>
        <span className={styles.icon}>⚠️</span>
        <div className={styles.text}>
          <strong className={styles.strong}>Plan Quota Exceeded:</strong>{' '}
          {pausedSummary} are currently <strong className={styles.strong}>Paused</strong> because your account exceeds the {entitlements.plan_name} plan limit ({entitlements.max_stores} Store, {entitlements.max_tracked_products} Products).
        </div>
      </div>
      <div className={styles.actions}>
        <button onClick={handleRenewOrUpgrade} disabled={loading} className={styles.upgradeBtn}>
          {loading ? 'Loading...' : 'Upgrade Plan'}
        </button>
        <Link href="/stores" className={styles.manageBtn}>
          Manage Stores
        </Link>
      </div>
    </div>
  );
}
