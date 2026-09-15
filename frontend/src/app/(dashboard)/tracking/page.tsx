'use client';

import useSWR from 'swr';
import { trackingApi } from '@/lib/api';
import { Card, CardBody } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { EmptyState, PageLoader } from '@/components/ui/Spinner';
import Link from 'next/link';
import { StatusBadge } from '@/components/ui/Badge';
import { TrackingStatusBanner } from '@/components/ui/TrackingStatusBanner';
import styles from './page.module.css';

export default function TrackingPage() {
  const { data, isLoading, mutate } = useSWR('tracking', () => trackingApi.list());

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
          <p>{data ? `${data.total} products monitored (${data.active_count} active)` : 'Loading…'}</p>
        </div>
      </div>

      <TrackingStatusBanner onPollComplete={() => mutate()} />

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
                      <h3 className={styles.title}>{p.title ?? p.handle}</h3>
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
                      <StatusBadge status={item.status ?? (item.is_active ? 'active' : 'paused_over_limit')} />
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
