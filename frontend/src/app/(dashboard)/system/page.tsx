'use client';

import { useState, useEffect } from 'react';
import useSWR from 'swr';
import { monitoringApi } from '@/lib/api';
import { Card, CardHeader, CardBody } from '@/components/ui/Card';
import { Badge, StatusBadge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { PageLoader, EmptyState } from '@/components/ui/Spinner';
import { TelemetryCharts } from '@/components/charts/TelemetryCharts';
import styles from './page.module.css';

export default function OperationsSystemPage() {
  const [triggering, setTriggering] = useState(false);
  const [actionMsg, setActionMsg] = useState('');
  const [actionFilter, setActionFilter] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [elapsedSec, setElapsedSec] = useState<number>(0);

  // Poll telemetry endpoint every 2000ms for live real-time stream
  const { data, isLoading, mutate } = useSWR(
    'worker-telemetry',
    () => monitoringApi.getWorkerTelemetry(),
    { refreshInterval: 2000 }
  );

  // Reset elapsed counter when fresh data arrives
  useEffect(() => {
    if (data) {
      setElapsedSec(0);
    }
  }, [data]);

  // Tick elapsed counter every second
  useEffect(() => {
    const timer = setInterval(() => {
      setElapsedSec(prev => prev + 1);
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  async function handleForcePollGlobal() {
    setTriggering(true);
    setActionMsg('');
    try {
      const res = await monitoringApi.triggerPollNow();
      setActionMsg(`⚡ Global poll complete! ${res.result?.polled ?? 0} items polled.`);
      mutate();
    } catch (err: unknown) {
      setActionMsg(err instanceof Error ? `⚠️ ${err.message}` : 'Failed to trigger poll');
    } finally {
      setTriggering(false);
    }
  }

  async function handleRestartEngine() {
    if (!confirm('Restart background monitoring workers?')) return;
    setTriggering(true);
    setActionMsg('');
    try {
      await monitoringApi.restartEngine();
      setActionMsg('🔄 Workers restarted successfully.');
      mutate();
    } catch (err: unknown) {
      setActionMsg(err instanceof Error ? `⚠️ ${err.message}` : 'Failed to restart engine');
    } finally {
      setTriggering(false);
    }
  }

  async function handleTriggerUserChecks() {
    setTriggering(true);
    setActionMsg('');
    try {
      const res = await monitoringApi.triggerUserChecks();
      setActionMsg(`⚡ Immediate check completed for your items (${res.result?.polled ?? 0} polled).`);
      mutate();
    } catch (err: unknown) {
      setActionMsg(err instanceof Error ? `⚠️ ${err.message}` : 'Failed to trigger user check');
    } finally {
      setTriggering(false);
    }
  }

  const actionBadge = (act: string) => {
    switch (act) {
      case 'PULLED':
        return <Badge variant="accent">⚡ PULLED</Badge>;
      case 'DISCOVERED':
        return <Badge variant="default">🔍 DISCOVERED</Badge>;
      case 'DISPATCHED':
        return <Badge variant="accent">🔔 DISPATCHED</Badge>;
      case 'ERROR':
        return <Badge variant="danger">⚠️ ERROR</Badge>;
      default:
        return <Badge variant="default">{act}</Badge>;
    }
  };

  const statusBadge = (code: number) => {
    if (code >= 200 && code < 300) {
      return <span style={{ color: 'var(--color-success)', fontWeight: 600, fontSize: 'var(--text-xs)' }}>{code} OK</span>;
    }
    if (code === 404) {
      return <span style={{ color: 'var(--color-warning)', fontWeight: 600, fontSize: 'var(--text-xs)' }}>404 Not Found</span>;
    }
    return <span style={{ color: 'var(--color-danger)', fontWeight: 600, fontSize: 'var(--text-xs)' }}>{code} Error</span>;
  };

  const rawEvents = data?.live_pulls || [];

  const filteredEvents = rawEvents.filter(evt => {
    const matchesAction = actionFilter === 'ALL' || evt.action === actionFilter;
    const matchesQuery = !searchQuery ||
      evt.product_title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      evt.store_domain.toLowerCase().includes(searchQuery.toLowerCase()) ||
      evt.details.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesAction && matchesQuery;
  });

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <div>
          <div className={styles.headerTitleGroup}>
            <h1>Operations & Engine Telemetry</h1>
            <span className={styles.liveBadge} title="SWR auto-fetches background telemetry every 2 seconds">
              <span className={styles.pulseDot} /> LIVE • Polling 2s ({elapsedSec}s ago)
            </span>
          </div>
          <p className={styles.subtitle}>
            {data?.is_admin
              ? 'Global real-time worker pool health, background task queue, and platform item pull stream.'
              : 'Real-time fetching telemetry and live item checks for your tracked stores.'}
          </p>
        </div>

        <div className={styles.headerActions}>
          {data?.is_admin ? (
            <>
              <Button size="sm" variant="secondary" onClick={handleRestartEngine} disabled={triggering}>
                🔄 Restart Workers
              </Button>
              <Button size="sm" onClick={handleForcePollGlobal} loading={triggering}>
                ⚡ Force Global Poll
              </Button>
            </>
          ) : (
            <Button size="sm" onClick={handleTriggerUserChecks} loading={triggering}>
              ⚡ Poll My Tracked Items Now
            </Button>
          )}
        </div>
      </div>

      {actionMsg && (
        <div className={actionMsg.startsWith('⚠️') ? styles.bannerError : styles.bannerSuccess}>
          {actionMsg}
        </div>
      )}

      {/* Summary KPI Ribbon */}
      <div className={styles.stats}>
        <Card>
          <CardBody>
            <div className={styles.stat}>
              <span className={styles.statIcon}>⚙️</span>
              <div>
                <div className={styles.statValue} style={{ textTransform: 'uppercase', color: 'var(--color-accent)' }}>
                  {data?.engine_status ?? 'RUNNING'}
                </div>
                <div className={styles.statLabel}>Engine State</div>
              </div>
            </div>
          </CardBody>
        </Card>

        <Card>
          <CardBody>
            <div className={styles.stat}>
              <span className={styles.statIcon}>🔄</span>
              <div>
                <div className={styles.statValue}>{data?.total_cycles_run ?? 0}</div>
                <div className={styles.statLabel}>Total Cycles Run</div>
              </div>
            </div>
          </CardBody>
        </Card>

        <Card>
          <CardBody>
            <div className={styles.stat}>
              <span className={styles.statIcon}>📡</span>
              <div>
                <div className={styles.statValue}>{data?.last_polled_count ?? 0}</div>
                <div className={styles.statLabel}>Last Polled Items</div>
              </div>
            </div>
          </CardBody>
        </Card>

        <Card>
          <CardBody>
            <div className={styles.stat}>
              <span className={styles.statIcon}>📈</span>
              <div>
                <div className={styles.statValue} style={{ color: 'var(--color-success)' }}>
                  {data?.last_changes_count ?? 0}
                </div>
                <div className={styles.statLabel}>Last Price Changes</div>
              </div>
            </div>
          </CardBody>
        </Card>

        <Card>
          <CardBody>
            <div className={styles.stat}>
              <span className={styles.statIcon}>⚠️</span>
              <div>
                <div className={styles.statValue} style={{ color: data?.last_error_count ? 'var(--color-danger)' : 'var(--color-text-2)' }}>
                  {data?.last_error_count ?? 0}
                </div>
                <div className={styles.statLabel}>Error Count</div>
              </div>
            </div>
          </CardBody>
        </Card>
      </div>

      {/* Interactive Visual Telemetry Charts & Analytics */}
      <Card>
        <CardHeader>
          <div className={styles.streamHeaderLeft}>
            <h3>Visual Telemetry & Execution Analytics</h3>
            <Badge variant="accent">Real-Time Charts</Badge>
          </div>
        </CardHeader>
        <CardBody>
          <TelemetryCharts events={rawEvents} />
        </CardBody>
      </Card>

      {/* Worker Pool Cards */}
      <Card>
        <CardHeader>
          <div className={styles.streamHeaderLeft}>
            <h3>Worker Pool Breakdown</h3>
            <Badge variant="accent">{data?.workers?.length ?? 3} Workers Active</Badge>
          </div>
        </CardHeader>
        <CardBody>
          <div className={styles.workerGrid}>
            {data?.workers?.map((w, idx) => (
              <div key={idx} className={styles.workerCard}>
                <div className={styles.workerHeader}>
                  <h4 className={styles.workerName}>{w.name}</h4>
                  <StatusBadge status={w.status === 'ACTIVE' ? 'active' : 'paused'} />
                </div>
                <p className={styles.workerTask}>{w.current_task}</p>
                <div className={styles.workerMeta}>
                  <span>Concurrency: <strong>{w.concurrency || 'Async Loop'}</strong></span>
                  {w.throughput_cycles !== undefined && (
                    <span>Cycles: <strong>{w.throughput_cycles}</strong></span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </CardBody>
      </Card>

      {/* Live Pull Stream Feed */}
      <Card>
        <CardHeader>
          <div className={styles.streamHeader}>
            <div className={styles.streamHeaderLeft}>
              <h3>Real-Time Live Pull Stream Feed</h3>
              <Badge variant="default">{filteredEvents.length} Events Displayed</Badge>
            </div>
            <span className={styles.streamHeaderSub}>
              Auto-updating ring buffer (last 50 actions)
            </span>
          </div>
        </CardHeader>

        {/* Action & Search Filter Toolbar */}
        <div className={styles.filterToolbar}>
          <div className={styles.filterPills}>
            {['ALL', 'PULLED', 'DISCOVERED', 'DISPATCHED', 'ERROR'].map((act) => (
              <button
                key={act}
                onClick={() => setActionFilter(act)}
                className={`${styles.filterPill} ${actionFilter === act ? styles.filterPillActive : ''}`}
              >
                {act === 'ALL' ? '🌐 All Events' : act}
              </button>
            ))}
          </div>
          <input
            type="text"
            placeholder="🔍 Filter product, domain, details..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className={styles.filterSearchInput}
          />
        </div>

        {isLoading && !data ? (
          <PageLoader />
        ) : !filteredEvents.length ? (
          <EmptyState
            icon="🛰️"
            title="No matching worker actions"
            description={searchQuery || actionFilter !== 'ALL'
              ? "No telemetry events match your current filter criteria."
              : "Live item pulls, price checks, and discovery events will stream here automatically in real time as background workers execute."}
          />
        ) : (
          <div className={styles.streamTableWrapper}>
            <table className={styles.streamTable}>
              <thead>
                <tr>
                  <th>Timestamp</th>
                  <th>Action</th>
                  <th>Product / Target</th>
                  <th>Store Domain</th>
                  <th>Price</th>
                  <th>HTTP Status</th>
                  <th>Latency</th>
                  <th>Details</th>
                </tr>
              </thead>
              <tbody>
                {filteredEvents.map((evt) => (
                  <tr key={evt.id}>
                    <td className={styles.timeCell}>
                      {new Date(evt.timestamp).toLocaleTimeString()}
                    </td>
                    <td>{actionBadge(evt.action)}</td>
                    <td className={styles.titleCell} title={evt.product_title}>
                      {evt.product_title}
                    </td>
                    <td><code className={styles.codeDomain}>{evt.store_domain}</code></td>
                    <td className={styles.priceCell}>
                      {evt.price !== null && evt.price !== undefined ? `$${evt.price.toFixed(2)}` : '—'}
                    </td>
                    <td>{statusBadge(evt.status_code)}</td>
                    <td className={styles.latencyCell}>
                      {evt.latency_ms > 0 ? `${evt.latency_ms}ms` : '—'}
                    </td>
                    <td className={styles.detailsCell} title={evt.details}>
                      {evt.details}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
