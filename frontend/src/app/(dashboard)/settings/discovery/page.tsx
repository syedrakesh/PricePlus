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

const DISCOVERY_PRESETS: Preset[] = [
  {
    id: 'safe',
    name: 'Safe & Recommended',
    icon: '🛡️',
    desc: 'Stays well under Shopify rate limits. Best for general store product discovery.',
    concurrency: 2,
    minDelay: 0.8,
    maxDelay: 1.5,
    meta: '~1.2 req/s · Zero 429 errors',
  },
  {
    id: 'fast',
    name: 'Fast Scan',
    icon: '⚡',
    desc: 'High-speed catalog discovery. May encounter soft rate limits on strict stores.',
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

export default function DiscoverySettingsPage() {
  const { data, isLoading, mutate } = useSWR('user-settings', () => settingsApi.get());

  const [concurrency, setConcurrency] = useState(2);
  const [minDelay, setMinDelay] = useState(0.8);
  const [maxDelay, setMaxDelay] = useState(1.5);
  const [activePreset, setActivePreset] = useState<string | null>('safe');

  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (data) {
      setConcurrency(data.discovery_concurrency);
      setMinDelay(data.discovery_min_delay);
      setMaxDelay(data.discovery_max_delay);

      const found = DISCOVERY_PRESETS.find(
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
      console.error('Failed to update discovery speed settings:', err);
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
        <h1>🔍 Store Discovery Speed Controls</h1>
        <p>Fine-tune store catalog product discovery speed, parallel worker concurrency, and randomized request delays.</p>
      </div>

      <form onSubmit={handleSave} style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
        <div className={styles.presetsSection}>
          <label className={styles.label}>Discovery Speed Presets</label>
          <div className={styles.presetGrid}>
            {DISCOVERY_PRESETS.map(preset => (
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
            <span className={styles.gaugeLabel}>Estimated Discovery Throughput</span>
          </div>
          <div className={styles.safeBadge}>
            🛡️ Safe Discovery Rate
          </div>
        </div>

        <Card glow>
          <CardHeader>
            <h3>🔍 Worker Concurrency & Randomized Min/Max Jitter Delays</h3>
          </CardHeader>
          <CardBody>
            <div className={styles.controlGroup}>
              <div className={styles.field}>
                <div className={styles.fieldHeader}>
                  <label className={styles.label}>Parallel Discovery Workers</label>
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
                  <span>2 (Safe Standard)</span>
                  <span>5 (Fast)</span>
                  <span>10 (Max)</span>
                </div>
                <p className={styles.hint}>Number of catalog fetch HTTP requests executed simultaneously during store discovery.</p>
              </div>

              <div className={styles.field}>
                <div className={styles.fieldHeader}>
                  <label className={styles.label}>Minimum Discovery Delay</label>
                  <span className={styles.valueBadge}>{minDelay.toFixed(1)}s</span>
                </div>
                <input
                  type="range" min="0.1" max="5.0" step="0.1"
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
                  <span>0.8s (Recommended)</span>
                  <span>2.0s</span>
                  <span>5.0s</span>
                </div>
                <p className={styles.hint}>Minimum pause duration before initiating each discovery request.</p>
              </div>

              <div className={styles.field}>
                <div className={styles.fieldHeader}>
                  <label className={styles.label}>Maximum Discovery Delay</label>
                  <span className={styles.valueBadge}>{maxDelay.toFixed(1)}s</span>
                </div>
                <input
                  type="range" min="0.2" max="10.0" step="0.1"
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
                  <span>1.5s (Recommended)</span>
                  <span>5.0s</span>
                  <span>10.0s</span>
                </div>
                <p className={styles.hint}>Maximum randomized pause between requests for polite jitter.</p>
              </div>

              <div className={styles.actions}>
                <Button type="submit" loading={saving}>Save Discovery Speed Settings</Button>
                {saved && (
                  <span className={styles.toastSuccess}>
                    ✓ Discovery speed settings saved successfully!
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
