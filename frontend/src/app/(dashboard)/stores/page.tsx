'use client';

import { useState } from 'react';
import useSWR from 'swr';
import { storesApi } from '@/lib/api';
import { Card, CardHeader, CardBody } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Badge, StatusBadge } from '@/components/ui/Badge';
import { EmptyState, PageLoader } from '@/components/ui/Spinner';
import Link from 'next/link';
import styles from './page.module.css';

export default function StoresPage() {
  const { data, isLoading, mutate } = useSWR(
    'stores',
    () => storesApi.list(),
    {
      refreshInterval: (latestData) => {
        const hasActiveRun = latestData?.stores.some(
          s => s.latest_discovery_run?.status === 'running' || s.latest_discovery_run?.status === 'pending'
        );
        return hasActiveRun ? 2000 : 0;
      },
    }
  );

  const [url, setUrl] = useState('');
  const [name, setName] = useState('');
  const [adding, setAdding] = useState(false);
  const [discovering, setDiscovering] = useState<string | null>(null);
  const [error, setError] = useState('');
  const [showForm, setShowForm] = useState(false);

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    setAdding(true);
    try {
      const store = await storesApi.create(url, name || undefined);
      await storesApi.triggerDiscovery(store.id);
      setUrl(''); setName(''); setShowForm(false);
      mutate();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to add store');
    } finally {
      setAdding(false);
    }
  }

  async function handleDelete(id: string) {
    if (!confirm('Remove this store and all its tracked products?')) return;
    await storesApi.delete(id);
    mutate();
  }

  async function handleDiscover(id: string) {
    setDiscovering(id);
    try {
      await storesApi.triggerDiscovery(id);
      mutate();
    } finally {
      setDiscovering(null);
    }
  }

  function formatTime(isoStr: string | null) {
    if (!isoStr) return null;
    try {
      const d = new Date(isoStr);
      return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) + ', ' + d.toLocaleDateString([], { month: 'short', day: 'numeric' });
    } catch {
      return null;
    }
  }

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <div>
          <h1>Competitor Stores</h1>
          <p>Add Shopify stores to discover and track their products</p>
        </div>
        <Button onClick={() => setShowForm(v => !v)} variant={showForm ? 'secondary' : 'primary'}>
          {showForm ? 'Cancel' : '+ Add Store'}
        </Button>
      </div>

      {showForm && (
        <Card glow>
          <CardHeader><h3>Add Competitor Store</h3></CardHeader>
          <CardBody>
            <form onSubmit={handleAdd} className={styles.form}>
              <Input
                label="Store URL"
                type="url"
                value={url}
                onChange={e => setUrl(e.target.value)}
                placeholder="https://competitor.myshopify.com"
                required
                hint="Any public Shopify store URL"
              />
              <Input
                label="Display Name (optional)"
                value={name}
                onChange={e => setName(e.target.value)}
                placeholder="e.g. Acme Store"
              />
              {error && <p className={styles.error}>{error}</p>}
              <Button type="submit" loading={adding}>Add Store</Button>
            </form>
          </CardBody>
        </Card>
      )}

      {isLoading ? (
        <PageLoader />
      ) : !data?.stores.length ? (
        <EmptyState
          icon="🏪"
          title="No stores yet"
          description="Add a competitor's Shopify store URL to start discovering and tracking their products."
          action={<Button onClick={() => setShowForm(true)}>Add your first store</Button>}
        />
      ) : (
        <div className={styles.grid}>
          {data.stores.map(store => {
            const run = store.latest_discovery_run;
            const isRunning = run?.status === 'running' || run?.status === 'pending';
            const isFailed = run?.status === 'failed';
            const lastTime = formatTime(store.last_discovery_at || run?.completed_at || null);
            const pct = run && run.products_discovered > 0
              ? Math.min(100, Math.round((run.products_fetched / run.products_discovered) * 100))
              : 0;

            return (
              <Card key={store.id} className={styles.storeCard}>
                <CardBody>
                  <div className={styles.storeMeta}>
                    <div className={styles.storeIcon}>🏪</div>
                    <div className={styles.storeInfo}>
                      <h3 className={styles.storeName}>{store.display_name ?? store.url}</h3>
                      {store.display_name && (
                        <span className={styles.storeUrl}>{new URL(store.url).hostname}</span>
                      )}
                    </div>
                    {isRunning ? (
                      <Badge variant="warning">⚡ Discovering</Badge>
                    ) : (
                      <StatusBadge status={store.status} />
                    )}
                  </div>

                  <div className={styles.storeStat}>
                    <span className={styles.storeStatNum}>{store.products_count}</span>
                    <span className={styles.storeStatLabel}>products discovered</span>
                  </div>

                  {/* Discovery Running Progress Box */}
                  {isRunning && (
                    <div className={styles.progressBox}>
                      <div className={styles.progressHeader}>
                        <span className={styles.spinnerIcon}>🔄</span>
                        <span className={styles.progressText}>
                          {run.products_discovered > 0
                            ? `Fetching details: ${run.products_fetched} / ${run.products_discovered} (${pct}%)`
                            : 'Scanning store...'}
                        </span>
                      </div>
                      {run.products_discovered > 0 && (
                        <div className={styles.progressBarBg}>
                          <div
                            className={styles.progressBarFill}
                            style={{ width: `${pct}%` }}
                          />
                        </div>
                      )}
                    </div>
                  )}

                  {/* Discovery Failed Box */}
                  {!isRunning && isFailed && run.error_message && (
                    <div className={styles.errorBox}>
                      ⚠️ Discovery failed: {run.error_message}
                    </div>
                  )}

                  {/* Last Discovered Time */}
                  {!isRunning && lastTime && (
                    <div className={styles.lastDiscovered}>
                      🕒 Last discovered: {lastTime}
                    </div>
                  )}

                  <div className={styles.storeActions}>
                    <Link href={`/stores/${store.id}`}>
                      <Button variant="secondary" size="sm">Browse Products</Button>
                    </Link>
                    <Button
                      variant="ghost"
                      size="sm"
                      loading={discovering === store.id || isRunning}
                      disabled={isRunning}
                      onClick={() => handleDiscover(store.id)}
                    >
                      {isRunning ? 'Discovering...' : '↻ Discover'}
                    </Button>
                    <Button variant="danger" size="sm" onClick={() => handleDelete(store.id)}>
                      Remove
                    </Button>
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
