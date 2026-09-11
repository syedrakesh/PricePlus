'use client';

import { useState } from 'react';
import useSWR from 'swr';
import { monitoringApi } from '@/lib/api';
import { Button } from '@/components/ui/Button';
import styles from './TrackingStatusBanner.module.css';

interface TrackingStatusBannerProps {
  onPollComplete?: () => void;
}

export function TrackingStatusBanner({ onPollComplete }: TrackingStatusBannerProps) {
  const { data: status, mutate } = useSWR('monitoring-engine-status', () => monitoringApi.getEngineStatus(), {
    refreshInterval: 5000,
  });

  const [isTriggering, setIsTriggering] = useState(false);
  const [isRestarting, setIsRestarting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const isRunning = status?.is_running && status?.status === 'running';
  const isStalled = status?.status === 'stalled';
  const isStopped = status?.status === 'stopped' || status?.status === 'error';

  async function handleTriggerPoll() {
    setIsTriggering(true);
    setMessage(null);
    try {
      const res = await monitoringApi.triggerPollNow();
      setMessage(`Poll cycle complete: ${res.result.polled} items checked (${res.result.changes} price changes)`);
      mutate();
      if (onPollComplete) onPollComplete();
    } catch (err: any) {
      setMessage(`Error: ${err.message || 'Failed to trigger poll'}`);
    } finally {
      setIsTriggering(false);
    }
  }

  async function handleRestartEngine() {
    setIsRestarting(true);
    setMessage(null);
    try {
      const res = await monitoringApi.restartEngine();
      setMessage(res.message || 'Tracking service restarted successfully');
      mutate();
      if (onPollComplete) onPollComplete();
    } catch (err: any) {
      setMessage(`Error: ${err.message || 'Failed to restart tracking service'}`);
    } finally {
      setIsRestarting(false);
    }
  }

  // Format last run time
  let lastRunText = 'Never';
  if (status?.last_run_at) {
    const elapsedSec = Math.floor((Date.now() - new Date(status.last_run_at).getTime()) / 1000);
    if (elapsedSec < 10) lastRunText = 'Just now';
    else if (elapsedSec < 60) lastRunText = `${elapsedSec}s ago`;
    else lastRunText = `${Math.floor(elapsedSec / 60)}m ago`;
  }

  return (
    <div
      className={[
        styles.banner,
        isStopped ? styles.bannerError : '',
        isStalled ? styles.bannerStalled : '',
      ].join(' ')}
    >
      <div className={styles.leftCol}>
        <div className={styles.pulseContainer}>
          {isRunning && <span className={styles.pulseRing} />}
          <span
            className={[
              styles.pulseDot,
              isStopped ? styles.dotStopped : '',
              isStalled ? styles.dotStalled : '',
            ].join(' ')}
          />
        </div>

        <div className={styles.statusContent}>
          <div className={styles.statusTitleRow}>
            <span className={styles.title}>Product Tracking Service</span>
            <span
              className={
                isRunning
                  ? styles.badgeRunning
                  : isStalled
                  ? styles.badgeStalled
                  : styles.badgeStopped
              }
            >
              {isRunning ? 'Continuous Monitoring Active' : isStalled ? 'Stalled' : 'Service Stopped'}
            </span>
          </div>

          <div className={styles.meta}>
            <span>Last poll: <strong>{lastRunText}</strong></span>
            <span className={styles.metaDot}>•</span>
            <span>Next poll in ~<strong>{status?.seconds_until_next_run ?? 0}s</strong></span>
            <span className={styles.metaDot}>•</span>
            <span>Cycles: {status?.total_cycles_run ?? 0}</span>
            {status?.last_polled_count != null && status.last_polled_count > 0 && (
              <>
                <span className={styles.metaDot}>•</span>
                <span>Last checked: {status.last_polled_count} products ({status.last_changes_count} changes)</span>
              </>
            )}
          </div>

          {message && (
            <div style={{ fontSize: '12px', color: 'var(--color-accent-hover)', marginTop: '4px' }}>
              {message}
            </div>
          )}
        </div>
      </div>

      <div className={styles.actions}>
        <Button
          size="sm"
          variant="secondary"
          disabled={isTriggering || isRestarting}
          onClick={handleTriggerPoll}
        >
          {isTriggering ? 'Polling…' : '⚡ Poll Now'}
        </Button>

        <Button
          size="sm"
          variant={isStopped || isStalled ? 'primary' : 'secondary'}
          disabled={isRestarting || isTriggering}
          onClick={handleRestartEngine}
        >
          {isRestarting ? 'Restarting…' : '🔄 Restart Service'}
        </Button>
      </div>
    </div>
  );
}
