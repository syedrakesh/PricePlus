'use client';

import useSWR from 'swr';
import { trackingApi } from '@/lib/api';
import { Card, CardBody } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { EmptyState, PageLoader } from '@/components/ui/Spinner';
import Link from 'next/link';
import styles from './page.module.css';

export default function TrackingPage() {
  const { data, isLoading, mutate } = useSWR('tracking', () => trackingApi.list());

  async function handleTogglePriority(item: any) {
    try {
      await trackingApi.update(item.id, { is_priority: !item.is_priority });
      mutate();
    } catch (err: any) {
      alert(err.message || 'Failed to update priority');
    }
  }

  async function handleIntervalChange(item: any, intervalMinutes: number | null) {
    try {
      await trackingApi.update(item.id, { tracking_interval_minutes: intervalMinutes });
      mutate();
    } catch (err: any) {
      alert(err.message || 'Failed to update tracking interval');
    }
  }

  async function handleUntrack(id: string, title?: string | null) {
    if (!confirm(`Stop tracking "${title || 'this product'}"?`)) return;
    try {
      await trackingApi.untrack(id);
      mutate();
    } catch (err: any) {
      alert(err.message || 'Failed to untrack product');
    }
  }

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <div>
          <h1>Tracked Products</h1>
          <p>{data ? `${data.total} products being monitored` : 'Loading…'}</p>
        </div>
      </div>

      {isLoading ? (
        <PageLoader />
      ) : !(data?.tracked_products ?? []).length ? (
        <EmptyState
          icon="📦"
          title="No tracked products"
          description="Browse your competitor stores to find and track products."
          action={<Link href="/stores"><Button>Browse Stores</Button></Link>}
        />
      ) : (
        <div className={styles.list}>
          {(data?.tracked_products ?? []).map(item => {
            const p = item.product ?? item;
            let hostname = '';
            try {
              if (p.product_url) hostname = new URL(p.product_url).hostname;
            } catch { /* ignore */ }

            return (
              <Card key={item.id} className={styles.row}>
                <CardBody>
                  <div className={styles.rowInner}>
                    {p.image_url ? (
                      <img src={p.image_url} alt={p.title ?? ''} className={styles.thumb} />
                    ) : (
                      <div className={styles.thumbPlaceholder}>📦</div>
                    )}
                    <div className={styles.info}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                        <h3 className={styles.title}>{p.title ?? p.handle}</h3>
                        {item.is_priority && <Badge variant="accent">⚡ VIP Priority</Badge>}
                      </div>
                      {hostname && <span className={styles.url}>{hostname}</span>}
                    </div>
                    <div className={styles.priceCol}>
                      {p.current_price != null ? (
                        <span className={styles.price}>${p.current_price.toFixed(2)}</span>
                      ) : (
                        <span className={styles.noPrice}>—</span>
                      )}
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <select
                        value={item.tracking_interval_minutes ?? ''}
                        onChange={e => handleIntervalChange(item, e.target.value ? parseInt(e.target.value) : null)}
                        style={{
                          background: 'rgba(15, 23, 42, 0.8)',
                          border: '1px solid rgba(255,255,255,0.15)',
                          borderRadius: '6px',
                          color: '#fff',
                          padding: '0.35rem 0.5rem',
                          fontSize: '0.75rem',
                        }}
                      >
                        <option value="">Default Interval</option>
                        <option value="1">⚡ 1 Minute (Realtime VIP)</option>
                        <option value="5">⚡ 5 Minutes (Turbo)</option>
                        <option value="15">15 Minutes</option>
                        <option value="60">1 Hour (Enterprise)</option>
                        <option value="360">6 Hours (Pro)</option>
                        <option value="1440">24 Hours (Free)</option>
                      </select>

                      <Button
                        size="sm"
                        variant={item.is_priority ? 'secondary' : 'ghost'}
                        onClick={() => handleTogglePriority(item)}
                        title="Toggle VIP High Frequency Priority"
                      >
                        {item.is_priority ? '⚡ VIP' : '☆ Standard'}
                      </Button>

                      <Link href={`/tracking/${item.id}`}>
                        <Button size="sm" variant="secondary">History</Button>
                      </Link>
                      <Button size="sm" variant="danger" onClick={() => handleUntrack(item.id, p.title)}>
                        Untrack
                      </Button>
                    </div>
                  </div>
                </CardBody>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
