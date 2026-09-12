'use client';

import { useState, useEffect } from 'react';
import useSWR from 'swr';
import { settingsApi } from '@/lib/api';
import { Card, CardHeader, CardBody } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { PageLoader } from '@/components/ui/Spinner';
import styles from '../page.module.css';

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

const TRACKING_PRESETS: Preset[] = [
  {
    id: 'safe',
    name: 'Safe & Recommended',
    icon: '🛡️',
    desc: 'Polite monitoring rate with randomized jitter delay for price checks.',
    concurrency: 5,
    minDelay: 0.2,
    maxDelay: 0.5,
    meta: '~14 req/s · Zero rate limits',
  },
  {
    id: 'fast',
    name: 'High Speed Poll',
    icon: '⚡',
    desc: 'Fastest price check rate for time-sensitive price drops across large product lists.',
    concurrency: 10,
    minDelay: 0.05,
    maxDelay: 0.2,
    meta: '~80 req/s · Ultra fast',
  },
  {
    id: 'stealth',
    name: 'Stealth / Low Impact',
    icon: '🐢',
    desc: 'Ultra-gentle requests designed for stores with strict Cloudflare protection.',
    concurrency: 1,
    minDelay: 1.0,
    maxDelay: 2.5,
    meta: '~0.6 req/s · Maximum stealth',
  },
];

export default function TrackingSettingsPage() {
  const { data, isLoading, mutate } = useSWR('user-settings', () => settingsApi.get());

  const [concurrency, setConcurrency] = useState(5);
  const [minDelay, setMinDelay] = useState(0.2);
  const [maxDelay, setMaxDelay] = useState(0.5);
  const [activePreset, setActivePreset] = useState<string | null>('safe');

  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (data) {
      setConcurrency(data.tracking_concurrency ?? 5);
      setMinDelay(data.tracking_min_delay ?? 0.2);
      setMaxDelay(data.tracking_max_delay ?? 0.5);

      const found = TRACKING_PRESETS.find(
        p => p.concurrency === (data.tracking_concurrency ?? 5) &&
             Math.abs(p.minDelay - (data.tracking_min_delay ?? 0.2)) < 0.05 &&
             Math.abs(p.maxDelay - (data.tracking_max_delay ?? 0.5)) < 0.05
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
        tracking_concurrency: concurrency,
        tracking_min_delay: minDelay,
        tracking_max_delay: maxDelay,
      });
      mutate(updated, false);
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (err) {
      console.error('Failed to update tracking speed settings:', err);
    } finally {
      setSaving(false);
    }
  };

  const avgDelay = (minDelay + maxDelay) / 2;
  const reqPerSec = (concurrency / avgDelay).toFixed(1);

  if (isLoading) return <PageLoader />;

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <h1>⚡ Product Tracking Speed Controls</h1>
        <p>Control background product tracking polling concurrency and randomized min/max request delays.</p>
      </div>

      <form onSubmit={handleSave} style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
        <div className={styles.presetsSection}>
          <label className={styles.label}>Tracking Speed Presets</label>
          <div className={styles.presetGrid}>
            {TRACKING_PRESETS.map(preset => (
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

        <div className={styles.gaugeCard}>
          <div className={styles.gaugeStat}>
            <span className={styles.gaugeNumber}>~{reqPerSec} <span style={{ fontSize: '16px', fontWeight: 600 }}>req/s</span></span>
            <span className={styles.gaugeLabel}>Estimated Price Check Throughput</span>
          </div>
          <div className={styles.safeBadge}>
            🛡️ Safe Polling Rate
          </div>
        </div>

        <Card glow>
          <CardHeader>
            <h3>📦 Product Tracking Concurrency & Min/Max Jitter Delays</h3>
          </CardHeader>
          <CardBody>
            <div className={styles.controlGroup}>
              <div className={styles.field}>
                <div className={styles.fieldHeader}>
                  <label className={styles.label}>Tracking Check Concurrency</label>
                  <span className={styles.valueBadge}>{concurrency} worker{concurrency > 1 ? 's' : ''}</span>
                </div>
                <input
                  type="range" min="1" max="10" step="1"
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
                  <span>5 (Safe Standard)</span>
                  <span>10 (Max Speed)</span>
                </div>
                <p className={styles.hint}>Number of HTTP price check requests executed simultaneously during a background poll cycle.</p>
              </div>

              <div className={styles.field}>
                <div className={styles.fieldHeader}>
                  <label className={styles.label}>Minimum Tracking Delay</label>
                  <span className={styles.valueBadge}>{minDelay.toFixed(2)}s</span>
                </div>
                <input
                  type="range" min="0.05" max="5.0" step="0.05"
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
                  <span>0.05s (Fast)</span>
                  <span>0.20s (Recommended)</span>
                  <span>1.0s (Stealth)</span>
                  <span>5.0s (Gentle)</span>
                </div>
                <p className={styles.hint}>Minimum pause duration before initiating each product check HTTP request.</p>
              </div>

              <div className={styles.field}>
                <div className={styles.fieldHeader}>
                  <label className={styles.label}>Maximum Tracking Delay</label>
                  <span className={styles.valueBadge}>{maxDelay.toFixed(2)}s</span>
                </div>
                <input
                  type="range" min="0.1" max="10.0" step="0.05"
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
                  <span>0.1s</span>
                  <span>0.5s (Recommended)</span>
                  <span>2.5s (Stealth)</span>
                  <span>10.0s</span>
                </div>
                <p className={styles.hint}>Maximum randomized pause between requests to produce human-like request jitter.</p>
              </div>

              <div className={styles.actions}>
                <Button type="submit" loading={saving}>Save Tracking Speed Settings</Button>
                {saved && (
                  <span className={styles.toastSuccess}>
                    ✓ Tracking speed settings saved successfully!
                  </span>
                )}
              </div>
            </div>
          </CardBody>
        </Card>
      </form>
    </div>
  );
}
