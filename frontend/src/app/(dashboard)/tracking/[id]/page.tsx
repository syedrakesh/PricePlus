'use client';

import { use } from 'react';
import useSWR from 'swr';

import { monitoringApi } from '@/lib/api';
import { Card, CardHeader, CardBody } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { PriceChart } from '@/components/charts/PriceChart';
import { PageLoader } from '@/components/ui/Spinner';
import styles from './page.module.css';

export default function TrackingDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { data, isLoading } = useSWR(
    `timeline-${id}`,
    () => monitoringApi.timeline(id, 200)
  );


  if (isLoading) return <PageLoader />;

  const changes = data?.entries.filter(e => e.kind === 'change') ?? [];
  const snapshots = data?.entries.filter(e => e.kind === 'snapshot') ?? [];

  const changeColor: Record<string, string> = {
    price_decrease: '#10b981', price_increase: '#ef4444',
    became_unavailable: '#f59e0b', became_available: '#3b82f6',
  };

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <div>
          <h1>Price History</h1>
          <p>{data?.total_snapshots ?? 0} snapshots · {data?.total_changes ?? 0} changes</p>
        </div>
        <div className={styles.priceStats}>
          {data?.latest_price !== null && data?.latest_price !== undefined && (
            <div className={styles.priceStat}>
              <span className={styles.priceStatVal}>${data.latest_price.toFixed(2)}</span>
              <span className={styles.priceStatLabel}>Current</span>
            </div>
          )}
          {data?.min_price !== null && data?.min_price !== undefined && (
            <div className={styles.priceStat}>
              <span className={styles.priceStatVal} style={{ color: '#10b981' }}>${data.min_price.toFixed(2)}</span>
              <span className={styles.priceStatLabel}>Min</span>
            </div>
          )}
          {data?.max_price !== null && data?.max_price !== undefined && (
            <div className={styles.priceStat}>
              <span className={styles.priceStatVal} style={{ color: '#ef4444' }}>${data.max_price.toFixed(2)}</span>
              <span className={styles.priceStatLabel}>Max</span>
            </div>
          )}
        </div>
      </div>

      {/* Chart */}
      <Card>
        <CardHeader><h3>Price Chart</h3></CardHeader>
        <CardBody>
          <PriceChart entries={data?.entries ?? []} />
        </CardBody>
      </Card>

      {/* Change events */}
      {changes.length > 0 && (
        <Card>
          <CardHeader><h3>Price Change Events</h3><Badge variant="accent">{changes.length}</Badge></CardHeader>
          <div className={styles.changeList}>
            {changes.map(chg => (
              <div key={chg.ref_id} className={styles.changeRow}>
                <div
                  className={styles.changeDot}
                  style={{ background: changeColor[chg.change_type ?? ''] ?? '#6366f1' }}
                />
                <div className={styles.changeInfo}>
                  <span className={styles.changeType}>{chg.change_type?.replace(/_/g, ' ')}</span>
                  <span className={styles.changeTime}>{new Date(chg.timestamp).toLocaleString()}</span>
                </div>
                <div className={styles.changePrices}>
                  {chg.old_price !== null && (
                    <span className={styles.oldPrice}>${chg.old_price?.toFixed(2)}</span>
                  )}
                  <span className={styles.arrow}>→</span>
                  {chg.new_price !== null && (
                    <span className={styles.newPrice}>${chg.new_price?.toFixed(2)}</span>
                  )}
                  {chg.pct_change !== null && (
                    <span style={{ color: (chg.pct_change ?? 0) < 0 ? '#10b981' : '#ef4444', fontSize: '12px', fontWeight: 600 }}>
                      {(chg.pct_change ?? 0) > 0 ? '+' : ''}{chg.pct_change?.toFixed(1)}%
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Recent snapshots */}
      <Card>
        <CardHeader>
          <h3>Snapshot Log</h3>
          <Badge variant="default">{snapshots.length}</Badge>
        </CardHeader>
        <div className={styles.snapshotList}>
          {snapshots.slice(0, 20).map(snap => (
            <div key={snap.ref_id} className={styles.snapshotRow}>
              <span className={styles.snapTime}>{new Date(snap.timestamp).toLocaleString()}</span>
              <span className={styles.snapPrice}>
                {snap.price !== null ? `$${snap.price.toFixed(2)}` : '—'}
              </span>
              {snap.error_message && (
                <span className={styles.snapError} title={snap.error_message}>⚠ Error</span>
              )}
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
