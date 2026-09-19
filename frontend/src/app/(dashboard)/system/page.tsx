'use client';

import { useState, useEffect } from 'react';
import useSWR from 'swr';
import { monitoringApi, LivePullEvent } from '@/lib/api';
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
  const [lastFetchTime, setLastFetchTime] = useState<number>(Date.now());
  const [now, setNow] = useState<number>(Date.now());
  const [selectedErrorEvent, setSelectedErrorEvent] = useState<LivePullEvent | null>(null);

  // Poll telemetry endpoint every 2000ms for live real-time stream
  const { data, isLoading, error, mutate } = useSWR(
    'worker-telemetry',
    () => monitoringApi.getWorkerTelemetry(),
    {
      refreshInterval: 2000,
      refreshWhenHidden: true,
      onSuccess: () => {
        setLastFetchTime(Date.now());
      },
    }
  );

  // Tick clock every second for exact elapsed time calculation
  useEffect(() => {
    const timer = setInterval(() => {
      setNow(Date.now());
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  const elapsedSec = Math.max(0, Math.floor((now - lastFetchTime) / 1000));

  async function handleForcePollGlobal() {
    setTriggering(true);
    setActionMsg('');
    try {
      const res = await monitoringApi.triggerPollNow();
      setActionMsg(`⚡ Global poll complete! ${res.result?.polled ?? 0} items polled.`);
      setLastFetchTime(Date.now());
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
      setLastFetchTime(Date.now());
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
      setLastFetchTime(Date.now());
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

  const getTroubleshootingAdvice = (evt: LivePullEvent) => {
    const detailsLower = (evt.details || '').toLowerCase();
    const code = evt.status_code;

    if (code === 404 || detailsLower.includes('404')) {
      return 'The target product page returned 404 Not Found. The product URL may have changed or been deleted from the merchant store.';
    }
    if (code === 403 || detailsLower.includes('403') || detailsLower.includes('cloudflare') || detailsLower.includes('captcha')) {
      return 'HTTP 403 Forbidden / Anti-Bot protection triggered. The merchant site is blocking direct HTTP requests. Consider enabling dynamic headless rendering or IP proxy rotation.';
    }
    if (detailsLower.includes('timeout') || detailsLower.includes('timed out') || detailsLower.includes('connect')) {
      return 'Connection timed out or store host unreachable. Check target domain accessibility and network DNS resolution.';
    }
    if (detailsLower.includes('selector') || detailsLower.includes('parse') || detailsLower.includes('none')) {
      return 'Price extraction returned null or selector matched zero elements. The store template or CSS markup may have been updated.';
    }
    return 'Review system logs or click "⚡ Poll My Tracked Items Now" / "⚡ Force Global Poll" to retry fetching this item.';
  };

  const rawEvents = data?.live_pulls || [];
  const errorEvents = rawEvents.filter(evt => evt.action === 'ERROR' || evt.status_code >= 400);

  const filteredEvents = rawEvents.filter(evt => {
    const matchesAction = actionFilter === 'ALL'
      ? true
      : actionFilter === 'ERROR'
      ? (evt.action === 'ERROR' || evt.status_code >= 400)
      : evt.action === actionFilter;
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
            {error ? (
              <span className={styles.liveBadge} style={{ background: 'rgba(239, 68, 68, 0.15)', borderColor: 'rgba(239, 68, 68, 0.3)', color: 'var(--color-danger)' }}>
                <span className={styles.pulseDot} style={{ backgroundColor: 'var(--color-danger)', boxShadow: '0 0 8px var(--color-danger)' }} /> PAUSED (Error)
              </span>
            ) : elapsedSec > 4 ? (
              <span className={styles.liveBadge} style={{ background: 'rgba(245, 158, 11, 0.15)', borderColor: 'rgba(245, 158, 11, 0.3)', color: 'var(--color-warning)' }}>
                <span className={styles.pulseDot} style={{ backgroundColor: 'var(--color-warning)', boxShadow: '0 0 8px var(--color-warning)' }} /> SYNCING ({elapsedSec}s ago)
              </span>
            ) : (
              <span className={styles.liveBadge} title="SWR auto-fetches background telemetry every 2 seconds">
                <span className={styles.pulseDot} /> LIVE • Polling 2s ({elapsedSec}s ago)
              </span>
            )}
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

        <Card
          className={styles.statClickable}
          onClick={() => {
            setActionFilter('ERROR');
            const el = document.getElementById('live-stream-feed');
            if (el) el.scrollIntoView({ behavior: 'smooth' });
          }}
          title="Click to view error log stream"
        >
          <CardBody>
            <div className={styles.stat}>
              <span className={styles.statIcon}>⚠️</span>
              <div>
                <div className={styles.statValue} style={{ color: (data?.last_error_count || errorEvents.length) ? 'var(--color-danger)' : 'var(--color-text-2)' }}>
                  {data?.last_error_count ?? errorEvents.length}
                </div>
                <div className={styles.statLabel}>Error Count (Click to Filter)</div>
              </div>
            </div>
          </CardBody>
        </Card>
      </div>

      {/* Error Diagnostics Card (if error events exist) */}
      {errorEvents.length > 0 && (
        <div className={styles.errorDiagnosticCard}>
          <div className={styles.errorDiagnosticHeader}>
            <div className={styles.errorDiagnosticTitle}>
              <span>⚠️</span>
              <span>Recent Engine Error Diagnostics ({errorEvents.length} Recent Failures)</span>
            </div>
            <Button
              size="sm"
              variant="secondary"
              onClick={() => setActionFilter('ERROR')}
            >
              Filter Stream to Errors
            </Button>
          </div>
          <div className={styles.errorList}>
            {errorEvents.slice(0, 3).map((evt) => (
              <div key={evt.id} className={styles.errorItemRow}>
                <div>
                  <span className={styles.errorItemTitle}>{evt.store_domain}</span> —{' '}
                  <span>{evt.product_title}</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
                  <span className={styles.errorItemMsg}>{evt.details}</span>
                  <button
                    className={styles.errorDetailsBtn}
                    onClick={() => setSelectedErrorEvent(evt)}
                  >
                    Inspect Error
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

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
      <Card id="live-stream-feed">
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
                {act === 'ALL' ? '🌐 All Events' : act === 'ERROR' ? '⚠️ Errors Only' : act}
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
                  <th>Details & Diagnostics</th>
                </tr>
              </thead>
              <tbody>
                {filteredEvents.map((evt) => {
                  const isErr = evt.action === 'ERROR' || evt.status_code >= 400;
                  return (
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
                      <td>
                        {isErr ? (
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                            <span
                              className={styles.detailsCellError}
                              title={evt.details}
                              onClick={() => setSelectedErrorEvent(evt)}
                            >
                              {evt.details}
                            </span>
                            <button
                              className={styles.errorDetailsBtn}
                              onClick={() => setSelectedErrorEvent(evt)}
                            >
                              Inspect
                            </button>
                          </div>
                        ) : (
                          <span className={styles.detailsCell} title={evt.details}>
                            {evt.details}
                          </span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Error Details Modal */}
      {selectedErrorEvent && (
        <div className={styles.modalOverlay} onClick={() => setSelectedErrorEvent(null)}>
          <div className={styles.modalContent} onClick={(e) => e.stopPropagation()}>
            <div className={styles.modalHeader}>
              <div className={styles.modalTitle}>
                <span>⚠️</span>
                <span>Telemetry Error Inspection Details</span>
              </div>
              <button
                className={styles.modalClose}
                onClick={() => setSelectedErrorEvent(null)}
              >
                ✕
              </button>
            </div>
            <div className={styles.modalBody}>
              <div className={styles.modalMetaGrid}>
                <div className={styles.modalMetaItem}>
                  <span className={styles.modalMetaLabel}>Timestamp</span>
                  <span className={styles.modalMetaVal}>
                    {new Date(selectedErrorEvent.timestamp).toLocaleString()}
                  </span>
                </div>
                <div className={styles.modalMetaItem}>
                  <span className={styles.modalMetaLabel}>Action & Status</span>
                  <span className={styles.modalMetaVal}>
                    {selectedErrorEvent.action} (HTTP {selectedErrorEvent.status_code})
                  </span>
                </div>
                <div className={styles.modalMetaItem}>
                  <span className={styles.modalMetaLabel}>Store Domain</span>
                  <span className={styles.modalMetaVal}>{selectedErrorEvent.store_domain}</span>
                </div>
                <div className={styles.modalMetaItem}>
                  <span className={styles.modalMetaLabel}>Product Target</span>
                  <span className={styles.modalMetaVal}>{selectedErrorEvent.product_title}</span>
                </div>
                <div className={styles.modalMetaItem}>
                  <span className={styles.modalMetaLabel}>Request Latency</span>
                  <span className={styles.modalMetaVal}>{selectedErrorEvent.latency_ms} ms</span>
                </div>
                <div className={styles.modalMetaItem}>
                  <span className={styles.modalMetaLabel}>Event ID</span>
                  <span className={styles.modalMetaVal}>{selectedErrorEvent.id}</span>
                </div>
              </div>

              <div>
                <h4 style={{ fontSize: 'var(--text-xs)', fontWeight: 700, color: 'var(--color-text-2)', marginBottom: '8px', textTransform: 'uppercase' }}>
                  Full Error Output & Details
                </h4>
                <pre className={styles.modalCodeBlock}>{selectedErrorEvent.details}</pre>
              </div>

              <div className={styles.suggestionBox}>
                <h5>💡 Suggested Troubleshooting Resolution</h5>
                <p>{getTroubleshootingAdvice(selectedErrorEvent)}</p>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 'var(--space-3)' }}>
                <Button variant="secondary" onClick={() => setSelectedErrorEvent(null)}>
                  Close
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

