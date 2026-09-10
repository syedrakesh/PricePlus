'use client';

import { useState, useEffect } from 'react';
import useSWR from 'swr';
import { settingsApi } from '@/lib/api';
import { Card, CardHeader, CardBody } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { PageLoader } from '@/components/ui/Spinner';
import styles from './page.module.css';

interface Preset {
  id: string;
  name: string;
  icon: string;
  desc: string;
  concurrency: number;
  minDelay: number;
  maxDelay: number;
  meta: string;
}

const PRESETS: Preset[] = [
  {
    id: 'safe',
    name: 'Safe & Recommended',
    icon: '🛡️',
    desc: 'Stays well under Shopify rate limits. Best for general store monitoring.',
    concurrency: 2,
    minDelay: 0.8,
    maxDelay: 1.5,
    meta: '~1.2 req/s · Zero 429 errors',
  },
  {
    id: 'fast',
    name: 'Fast Scan',
    icon: '⚡',
    desc: 'High-speed discovery for large catalogs. May encounter soft rate limits on strict stores.',
    concurrency: 4,
    minDelay: 0.4,
    maxDelay: 0.8,
    meta: '~3.3 req/s · 3x faster',
  },
  {
    id: 'stealth',
    name: 'Stealth / Slow',
    icon: '🐢',
    desc: 'Ultra-gentle requests for anti-bot protected stores or strict rate limits.',
    concurrency: 1,
    minDelay: 1.5,
    maxDelay: 3.0,
    meta: '~0.4 req/s · Maximum stealth',
  },
];

export default function SettingsPage() {
  const { data, isLoading, mutate } = useSWR('user-settings', () => settingsApi.get());

  const [concurrency, setConcurrency] = useState(2);
  const [minDelay, setMinDelay] = useState(0.8);
  const [maxDelay, setMaxDelay] = useState(1.5);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [activePreset, setActivePreset] = useState<string | null>('safe');

  useEffect(() => {
    if (data) {
      setConcurrency(data.discovery_concurrency);
      setMinDelay(data.discovery_min_delay);
      setMaxDelay(data.discovery_max_delay);

      // Match preset if values equal
      const found = PRESETS.find(
        p => p.concurrency === data.discovery_concurrency &&
             Math.abs(p.minDelay - data.discovery_min_delay) < 0.05 &&
             Math.abs(p.maxDelay - data.discovery_max_delay) < 0.05
      );
      setActivePreset(found ? found.id : null);
    }
  }, [data]);

  const applyPreset = (preset: Preset) => {
    setConcurrency(preset.concurrency);
    setMinDelay(preset.minDelay);
    setMaxDelay(preset.maxDelay);
    setActivePreset(preset.id);
    setSaved(false);
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setSaved(false);
    try {
      const updated = await settingsApi.update({
        discovery_concurrency: concurrency,
        discovery_min_delay: minDelay,
        discovery_max_delay: maxDelay,
      });
      mutate(updated, false);
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (err) {
      console.error('Failed to update settings:', err);
    } finally {
      setSaving(false);
    }
  };

  const avgDelay = (minDelay + maxDelay) / 2;
  const reqPerSec = (concurrency / avgDelay).toFixed(1);
  const numReqPerSec = parseFloat(reqPerSec);

  let rateStatus: { label: string; badgeClass: string } = {
    label: '🛡️ Safe Rate (Shopify Compliant)',
    badgeClass: styles.safeBadge,
  };
  if (numReqPerSec > 3.0) {
    rateStatus = {
      label: '⚡ High Speed (Risk of 429 Rate Limits)',
      badgeClass: styles.warnBadge,
    };
  } else if (numReqPerSec > 5.0) {
    rateStatus = {
      label: '⚠️ Aggressive Rate (High Risk of Block)',
      badgeClass: styles.dangerBadge,
    };
  }

  if (isLoading) {
    return <PageLoader />;
  }

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <h1>Discovery Rate Settings</h1>
        <p>Control product fetching speed, parallel worker concurrency, and request delay to prevent rate limits.</p>
      </div>

      {/* Preset Profiles */}
      <div className={styles.presetsSection}>
        <label className={styles.label}>Quick Presets</label>
        <div className={styles.presetGrid}>
          {PRESETS.map(preset => (
            <div
              key={preset.id}
              className={[
                styles.presetCard,
                activePreset === preset.id ? styles.presetCardActive : '',
              ].join(' ')}
              onClick={() => applyPreset(preset)}
            >
              <div className={styles.presetTitle}>
                <span>{preset.icon}</span> {preset.name}
              </div>
              <p className={styles.presetDesc}>{preset.desc}</p>
              <div className={styles.presetMeta}>{preset.meta}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Estimated Rate Gauge */}
      <div className={styles.gaugeCard}>
        <div className={styles.gaugeStat}>
          <span className={styles.gaugeNumber}>~{reqPerSec} <span style={{ fontSize: '18px', fontWeight: 600 }}>req/s</span></span>
          <span className={styles.gaugeLabel}>Estimated Discovery Throughput</span>
        </div>
        <div className={[styles.gaugeRecommendation, rateStatus.badgeClass].join(' ')}>
          {rateStatus.label}
        </div>
      </div>

      {/* Manual Controls Card */}
      <Card glow>
        <CardHeader>
          <h3>Custom Rate & Concurrency Controls</h3>
        </CardHeader>
        <CardBody>
          <form onSubmit={handleSave} className={styles.controlGroup}>
            {/* Concurrency Field */}
            <div className={styles.field}>
              <div className={styles.fieldHeader}>
                <label className={styles.label}>Parallel Worker Concurrency</label>
                <span className={styles.valueBadge}>{concurrency} worker{concurrency > 1 ? 's' : ''}</span>
              </div>
              <input
                type="range"
                min="1"
                max="10"
                step="1"
                value={concurrency}
                onChange={e => {
                  setConcurrency(parseInt(e.target.value, 10));
                  setActivePreset(null);
                  setSaved(false);
                }}
                className={styles.rangeInput}
              />
              <div className={styles.rangeMarks}>
                <span>1 (Stealth)</span>
                <span>2 (Safe)</span>
                <span>5 (Fast)</span>
                <span>10 (Max)</span>
              </div>
              <p className={styles.hint}>
                Number of HTTP fetch requests executed simultaneously. Recommended: 2 workers.
              </p>
            </div>

            {/* Min Delay Field */}
            <div className={styles.field}>
              <div className={styles.fieldHeader}>
                <label className={styles.label}>Minimum Request Delay</label>
                <span className={styles.valueBadge}>{minDelay.toFixed(1)}s</span>
              </div>
              <input
                type="range"
                min="0.1"
                max="5.0"
                step="0.1"
                value={minDelay}
                onChange={e => {
                  const val = parseFloat(e.target.value);
                  setMinDelay(val);
                  if (val > maxDelay) setMaxDelay(val);
                  setActivePreset(null);
                  setSaved(false);
                }}
                className={styles.rangeInput}
              />
              <div className={styles.rangeMarks}>
                <span>0.1s</span>
                <span>0.8s</span>
                <span>2.0s</span>
                <span>5.0s</span>
              </div>
              <p className={styles.hint}>Minimum randomized pause before initiating each request.</p>
            </div>

            {/* Max Delay Field */}
            <div className={styles.field}>
              <div className={styles.fieldHeader}>
                <label className={styles.label}>Maximum Request Delay</label>
                <span className={styles.valueBadge}>{maxDelay.toFixed(1)}s</span>
              </div>
              <input
                type="range"
                min="0.2"
                max="10.0"
                step="0.1"
                value={maxDelay}
                onChange={e => {
                  const val = parseFloat(e.target.value);
                  setMaxDelay(val);
                  if (val < minDelay) setMinDelay(val);
                  setActivePreset(null);
                  setSaved(false);
                }}
                className={styles.rangeInput}
              />
              <div className={styles.rangeMarks}>
                <span>0.2s</span>
                <span>1.5s</span>
                <span>5.0s</span>
                <span>10.0s</span>
              </div>
              <p className={styles.hint}>Maximum randomized pause between requests for polite jitter.</p>
            </div>

            {/* Actions */}
            <div className={styles.actions}>
              <Button type="submit" loading={saving}>Save Discovery Settings</Button>
              {saved && (
                <span className={styles.toastSuccess}>
                  ✓ Settings saved successfully!
                </span>
              )}
            </div>
          </form>
        </CardBody>
      </Card>
    </div>
  );
}
