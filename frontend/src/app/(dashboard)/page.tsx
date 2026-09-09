'use client';

import useSWR from 'swr';
import { monitoringApi, trackingApi, storesApi, billingApi } from '@/lib/api';
import { Card, CardBody } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { PageLoader } from '@/components/ui/Spinner';
import Link from 'next/link';
import styles from './page.module.css';

function StatCard({ label, value, sub, icon }: { label: string; value: string | number; sub?: string; icon: string }) {
  return (
    <Card>
      <CardBody>
        <div className={styles.stat}>
          <span className={styles.statIcon}>{icon}</span>
          <div>
            <div className={styles.statValue}>{value}</div>
            <div className={styles.statLabel}>{label}</div>
            {sub && <div className={styles.statSub}>{sub}</div>}
          </div>
        </div>
      </CardBody>
    </Card>
  );
}

export default function DashboardPage() {
  const { data: stores } = useSWR('stores', () => storesApi.list());
  const { data: tracked } = useSWR('tracking', () => trackingApi.list());
  const { data: changes, isLoading: changesLoading } = useSWR('recent-changes', () => monitoringApi.priceChanges());
  const { data: entitlements } = useSWR('entitlements', () => billingApi.entitlements());

  const changeIcon: Record<string, string> = {
    price_decrease: '🔽', price_increase: '🔼',
    became_unavailable: '⚠️', became_available: '✅',
  };

  const changeBadge: Record<string, 'success' | 'danger' | 'warning' | 'info'> = {
    price_decrease: 'success', price_increase: 'danger',
    became_unavailable: 'warning', became_available: 'info',
  };

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <div>
          <h1>Dashboard</h1>
          <p>Overview of your price monitoring</p>
        </div>
        {entitlements && (
          <div className={styles.planBadge}>
            <Badge variant="accent">{entitlements.plan_name} plan</Badge>
          </div>
        )}
      </div>

      {/* Stats */}
      <div className={styles.stats}>
        <StatCard
          icon="🏪" label="Competitor Stores"
          value={stores?.total ?? '—'}
          sub={entitlements ? `of ${entitlements.max_stores} limit` : undefined}
        />
        <StatCard
          icon="📦" label="Tracked Products"
          value={tracked?.total ?? '—'}
          sub={entitlements ? `of ${entitlements.max_tracked_products} limit` : undefined}
        />
        <StatCard
          icon="📊" label="Price Changes"
          value={changes?.total ?? '—'}
          sub="all time"
        />
        <StatCard
          icon="⏱" label="Poll Interval"
          value={entitlements ? `${entitlements.poll_interval_mins}m` : '—'}
          sub="check frequency"
        />
      </div>

      {/* Recent price changes */}
      <Card>
        <div className={styles.cardHeader}>
          <h3>Recent Price Changes</h3>
          <Link href="/tracking" className={styles.viewAll}>View all →</Link>
        </div>
        {changesLoading ? (
          <PageLoader />
        ) : !changes?.changes.length ? (
          <div className={styles.empty}>
            <span>📊</span>
            <p>No price changes detected yet. Start tracking products to see changes here.</p>
          </div>
        ) : (
          <div className={styles.changeList}>
            {changes.changes.slice(0, 10).map(chg => (
              <div key={chg.id} className={styles.changeRow}>
                <span className={styles.changeIcon}>{changeIcon[chg.change_type] ?? '📊'}</span>
                <div className={styles.changeInfo}>
                  <span className={styles.changeType}>
                    <Badge variant={changeBadge[chg.change_type] ?? 'default'}>
                      {chg.change_type.replace(/_/g, ' ')}
                    </Badge>
                  </span>
                  <span className={styles.changeTime}>
                    {new Date(chg.detected_at).toLocaleString()}
                  </span>
                </div>
                <div className={styles.changePrices}>
                  {chg.old_price !== null && (
                    <span className={styles.oldPrice}>${chg.old_price.toFixed(2)}</span>
                  )}
                  {chg.new_price !== null && (
                    <span className={styles.newPrice}>${chg.new_price.toFixed(2)}</span>
                  )}
                  {chg.pct_change !== null && (
                    <span className={chg.pct_change < 0 ? styles.pctDown : styles.pctUp}>
                      {chg.pct_change > 0 ? '+' : ''}{chg.pct_change.toFixed(1)}%
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
