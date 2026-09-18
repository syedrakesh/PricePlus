'use client';

import { useState } from 'react';
import useSWR from 'swr';
import { monitoringApi } from '@/lib/api';
import { Card, CardHeader } from '@/components/ui/Card';
import { Badge, StatusBadge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { PageLoader, EmptyState } from '@/components/ui/Spinner';
import styles from './page.module.css';

export default function OperationsSystemPage() {
  const [triggering, setTriggering] = useState(false);
  const [actionMsg, setActionMsg] = useState('');

  // Poll telemetry endpoint every 2000ms for live real-time stream
  const { data, isLoading, mutate } = useSWR(
    'worker-telemetry',
    () => monitoringApi.getWorkerTelemetry(),
    { refreshInterval: 2000 }
  );

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
      return <span style={{ color: '#10B981', fontWeight: 600, fontSize: '12px' }}>{code} OK</span>;
    }
    if (code === 404) {
      return <span style={{ color: '#F59E0B', fontWeight: 600, fontSize: '12px' }}>404 Not Found</span>;
    }
    return <span style={{ color: '#EF4444', fontWeight: 600, fontSize: '12px' }}>{code} Error</span>;
  };

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <h1 className={styles.title}>Operations & Engine Telemetry</h1>
            <span style={{
              display: 'inline-flex', alignItems: 'center', gap: '5px', background: 'rgba(16,185,129,0.15)',
              color: '#10B981', padding: '3px 10px', borderRadius: '12px', fontSize: '12px', fontWeight: 700
            }}>
              <span className={styles.pulseDot} /> LIVE (2s)
            </span>
          </div>
          <p className={styles.subtitle}>
            {data?.is_admin
              ? 'Global real-time worker pool health, background task queue, and platform item pull stream.'
              : 'Real-time fetching telemetry and live item checks for your tracked stores.'}
          </p>
        </div>

        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', alignItems: 'center' }}>
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
        <div style={{
          background: actionMsg.startsWith('⚠️') ? 'rgba(239,68,68,0.1)' : 'rgba(16,185,129,0.1)',
          color: actionMsg.startsWith('⚠️') ? 'var(--color-danger)' : '#10B981',
          padding: '10px 16px', borderRadius: '8px', marginBottom: '16px', fontSize: '13px', fontWeight: 600
        }}>
          {actionMsg}
        </div>
      )}

      {/* Summary KPI Ribbon */}
      <div className={styles.kpiGrid}>
        <div className={styles.kpiCard}>
          <span className={styles.kpiLabel}>Engine State</span>
          <span className={styles.kpiValue} style={{ textTransform: 'uppercase', color: 'var(--color-accent)' }}>
            {data?.engine_status ?? 'RUNNING'}
          </span>
        </div>
        <div className={styles.kpiCard}>
          <span className={styles.kpiLabel}>Total Cycles Run</span>
          <span className={styles.kpiValue}>{data?.total_cycles_run ?? 0}</span>
        </div>
        <div className={styles.kpiCard}>
          <span className={styles.kpiLabel}>Last Polled Items</span>
          <span className={styles.kpiValue}>{data?.last_polled_count ?? 0}</span>
        </div>
        <div className={styles.kpiCard}>
          <span className={styles.kpiLabel}>Last Price Changes</span>
          <span className={styles.kpiValue} style={{ color: '#10B981' }}>{data?.last_changes_count ?? 0}</span>
        </div>
        <div className={styles.kpiCard}>
          <span className={styles.kpiLabel}>Error Count</span>
          <span className={styles.kpiValue} style={{ color: data?.last_error_count ? '#EF4444' : 'var(--color-text-2)' }}>
            {data?.last_error_count ?? 0}
          </span>
        </div>
      </div>

      {/* Worker Pool Cards */}
      <div style={{ marginBottom: '24px' }}>
        <Card>
        <CardHeader>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <h3>Worker Pool Breakdown</h3>
            <Badge variant="accent">{data?.workers?.length ?? 3} Workers Active</Badge>
          </div>
        </CardHeader>
        <div className={styles.workerGrid}>
          {data?.workers?.map((w, idx) => (
            <div key={idx} className={styles.workerCard}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
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
      </Card>
    </div>

      {/* Live Pull Stream Feed */}
      <Card>
        <CardHeader>
          <div style={{ display: 'flex', justifyContent: 'space-between', width: '100%', alignItems: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <h3>Real-Time Live Pull Stream Feed</h3>
              <Badge variant="default">{data?.live_pulls?.length ?? 0} Events Recorded</Badge>
            </div>
            <span style={{ fontSize: '12px', color: 'var(--color-text-2)' }}>
              Auto-updating ring buffer (last 50 actions)
            </span>
          </div>
        </CardHeader>

        {isLoading && !data ? (
          <PageLoader />
        ) : !data?.live_pulls?.length ? (
          <EmptyState
            icon="🛰️"
            title="Waiting for live worker actions..."
            description="Live item pulls, price checks, and discovery events will stream here automatically in real time as background workers execute."
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
                {data.live_pulls.map((evt) => (
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
