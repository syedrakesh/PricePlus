'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { billingApi, Entitlements } from '@/lib/api';
import styles from './OverQuotaBanner.module.css';

export function OverQuotaBanner() {
  const [entitlements, setEntitlements] = useState<Entitlements | null>(null);

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

  if (!entitlements) return null;

  const pausedStores = entitlements.paused_stores ?? 0;
  const pausedProducts = entitlements.paused_tracked_products ?? 0;
  const isOverLimit =
    entitlements.is_over_limit || pausedStores > 0 || pausedProducts > 0;

  if (!isOverLimit) return null;

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
        <Link href="/billing" className={styles.upgradeBtn}>
          Upgrade Plan
        </Link>
        <Link href="/stores" className={styles.manageBtn}>
          Manage Stores
        </Link>
      </div>
    </div>
  );
}
