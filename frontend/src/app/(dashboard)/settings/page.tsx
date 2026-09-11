'use client';

import { useState, useEffect, Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
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

function SettingsContent() {
  const searchParams = useSearchParams();
  const initialTab = searchParams.get('tab') === 'tracking' ? 'tracking' : 'discovery';
  const [activeTab, setActiveTab] = useState<'discovery' | 'tracking'>(initialTab);

  const { data, isLoading, mutate } = useSWR('user-settings', () => settingsApi.get());

  // Discovery settings state
  const [discConcurrency, setDiscConcurrency] = useState(2);
  const [discMinDelay, setDiscMinDelay] = useState(0.8);
  const [discMaxDelay, setDiscMaxDelay] = useState(1.5);
  const [activeDiscPreset, setActiveDiscPreset] = useState<string | null>('safe');

  // Tracking settings state
  const [trackConcurrency, setTrackConcurrency] = useState(5);
  const [trackMinDelay, setTrackMinDelay] = useState(0.2);
  const [trackMaxDelay, setTrackMaxDelay] = useState(0.5);
  const [activeTrackPreset, setActiveTrackPreset] = useState<string | null>('safe');

  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (data) {
      setDiscConcurrency(data.discovery_concurrency);
      setDiscMinDelay(data.discovery_min_delay);
      setDiscMaxDelay(data.discovery_max_delay);

      setTrackConcurrency(data.tracking_concurrency ?? 5);
      setTrackMinDelay(data.tracking_min_delay ?? 0.2);
      setTrackMaxDelay(data.tracking_max_delay ?? 0.5);

      const discFound = DISCOVERY_PRESETS.find(
        p => p.concurrency === data.discovery_concurrency &&
             Math.abs(p.minDelay - data.discovery_min_delay) < 0.05 &&
             Math.abs(p.maxDelay - data.discovery_max_delay) < 0.05
      );
      setActiveDiscPreset(discFound ? discFound.id : null);

      const trackFound = TRACKING_PRESETS.find(
        p => p.concurrency === (data.tracking_concurrency ?? 5) &&
             Math.abs(p.minDelay - (data.tracking_min_delay ?? 0.2)) < 0.05 &&
             Math.abs(p.maxDelay - (data.tracking_max_delay ?? 0.5)) < 0.05
      );
      setActiveTrackPreset(trackFound ? trackFound.id : null);
    }
  }, [data]);

  const applyDiscPreset = (preset: Preset) => {
    setDiscConcurrency(preset.concurrency);
    setDiscMinDelay(preset.minDelay);
    setDiscMaxDelay(preset.maxDelay);
    setActiveDiscPreset(preset.id);
    setSaved(false);
  };

  const applyTrackPreset = (preset: Preset) => {
    setTrackConcurrency(preset.concurrency);
    setTrackMinDelay(preset.minDelay);
    setTrackMaxDelay(preset.maxDelay);
    setActiveTrackPreset(preset.id);
    setSaved(false);
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setSaved(false);
    try {
      const updated = await settingsApi.update({
        discovery_concurrency: discConcurrency,
        discovery_min_delay: discMinDelay,
        discovery_max_delay: discMaxDelay,
        tracking_concurrency: trackConcurrency,
        tracking_min_delay: trackMinDelay,
        tracking_max_delay: trackMaxDelay,
      });
      mutate(updated, false);
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (err) {
      console.error('Failed to update speed settings:', err);
    } finally {
      setSaving(false);
    }
  };

  // Discovery rate calculation
  const discAvgDelay = (discMinDelay + discMaxDelay) / 2;
  const discReqPerSec = (discConcurrency / discAvgDelay).toFixed(1);

  // Tracking rate calculation
  const trackAvgDelay = (trackMinDelay + trackMaxDelay) / 2;
  const trackReqPerSec = (trackConcurrency / trackAvgDelay).toFixed(1);

  if (isLoading) {
    return <PageLoader />;
  }

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <h1>System Speed & Rate Settings</h1>
        <p>Control product discovery speed, background tracking poll concurrency, and randomized min/max request delays.</p>
      </div>

      {/* Tabs Navigation */}
      <div className={styles.tabsNav}>
        <button
          className={[styles.tabBtn, activeTab === 'discovery' ? styles.tabBtnActive : ''].join(' ')}
          onClick={() => setActiveTab('discovery')}
        >
          🔍 Store Discovery Speed
        </button>
        <button
          className={[styles.tabBtn, activeTab === 'tracking' ? styles.tabBtnActive : ''].join(' ')}
          onClick={() => setActiveTab('tracking')}
        >
          📦 Product Tracking Speed
        </button>
      </div>

      {/* Tab 1: Store Discovery Speed */}
      {activeTab === 'discovery' && (
        <form onSubmit={handleSave} style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          <div className={styles.presetsSection}>
            <label className={styles.label}>Discovery Presets</label>
            <div className={styles.presetGrid}>
              {DISCOVERY_PRESETS.map(preset => (
                <div
                  key={preset.id}
                  className={[
                    styles.presetCard,
                    activeDiscPreset === preset.id ? styles.presetCardActive : '',
                  ].join(' ')}
                  onClick={() => applyDiscPreset(preset)}
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
              <span className={styles.gaugeNumber}>~{discReqPerSec} <span style={{ fontSize: '16px', fontWeight: 600 }}>req/s</span></span>
              <span className={styles.gaugeLabel}>Estimated Discovery Throughput</span>
            </div>
            <div className={styles.safeBadge}>
              🛡️ Safe Discovery Rate
            </div>
          </div>

          <Card glow>
            <CardHeader>
              <h3>🔍 Store Discovery Concurrency & Min/Max Jitter Delays</h3>
            </CardHeader>
            <CardBody>
              <div className={styles.controlGroup}>
                <div className={styles.field}>
                  <div className={styles.fieldHeader}>
                    <label className={styles.label}>Parallel Discovery Workers</label>
                    <span className={styles.valueBadge}>{discConcurrency} worker{discConcurrency > 1 ? 's' : ''}</span>
                  </div>
                  <input
                    type="range" min="1" max="10" step="1"
                    value={discConcurrency}
                    onChange={e => {
                      setDiscConcurrency(parseInt(e.target.value, 10));
                      setActiveDiscPreset(null);
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
                  <p className={styles.hint}>Number of catalog fetch requests executed simultaneously during store discovery.</p>
                </div>

                <div className={styles.field}>
                  <div className={styles.fieldHeader}>
                    <label className={styles.label}>Minimum Discovery Delay</label>
                    <span className={styles.valueBadge}>{discMinDelay.toFixed(1)}s</span>
                  </div>
                  <input
                    type="range" min="0.1" max="5.0" step="0.1"
                    value={discMinDelay}
                    onChange={e => {
                      const val = parseFloat(e.target.value);
                      setDiscMinDelay(val);
                      if (val > discMaxDelay) setDiscMaxDelay(val);
                      setActiveDiscPreset(null);
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
                    <span className={styles.valueBadge}>{discMaxDelay.toFixed(1)}s</span>
                  </div>
                  <input
                    type="range" min="0.2" max="10.0" step="0.1"
                    value={discMaxDelay}
                    onChange={e => {
                      const val = parseFloat(e.target.value);
                      setDiscMaxDelay(val);
                      if (val < discMinDelay) setDiscMinDelay(val);
                      setActiveDiscPreset(null);
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
                      ✓ Settings saved successfully!
                    </span>
                  )}
                </div>
              </div>
            </CardBody>
          </Card>
        </form>
      )}

      {/* Tab 2: Product Tracking Speed */}
      {activeTab === 'tracking' && (
        <form onSubmit={handleSave} style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          <div className={styles.presetsSection}>
            <label className={styles.label}>Tracking Presets</label>
            <div className={styles.presetGrid}>
              {TRACKING_PRESETS.map(preset => (
                <div
                  key={preset.id}
                  className={[
                    styles.presetCard,
                    activeTrackPreset === preset.id ? styles.presetCardActive : '',
                  ].join(' ')}
                  onClick={() => applyTrackPreset(preset)}
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
              <span className={styles.gaugeNumber}>~{trackReqPerSec} <span style={{ fontSize: '16px', fontWeight: 600 }}>req/s</span></span>
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
                    <span className={styles.valueBadge}>{trackConcurrency} worker{trackConcurrency > 1 ? 's' : ''}</span>
                  </div>
                  <input
                    type="range" min="1" max="10" step="1"
                    value={trackConcurrency}
                    onChange={e => {
                      setTrackConcurrency(parseInt(e.target.value, 10));
                      setActiveTrackPreset(null);
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
                    <span className={styles.valueBadge}>{trackMinDelay.toFixed(2)}s</span>
                  </div>
                  <input
                    type="range" min="0.05" max="5.0" step="0.05"
                    value={trackMinDelay}
                    onChange={e => {
                      const val = parseFloat(e.target.value);
                      setTrackMinDelay(val);
                      if (val > trackMaxDelay) setTrackMaxDelay(val);
                      setActiveTrackPreset(null);
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
                    <span className={styles.valueBadge}>{trackMaxDelay.toFixed(2)}s</span>
                  </div>
                  <input
                    type="range" min="0.1" max="10.0" step="0.05"
                    value={trackMaxDelay}
                    onChange={e => {
                      const val = parseFloat(e.target.value);
                      setTrackMaxDelay(val);
                      if (val < trackMinDelay) setTrackMinDelay(val);
                      setActiveTrackPreset(null);
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
                      ✓ Settings saved successfully!
                    </span>
                  )}
                </div>
              </div>
            </CardBody>
          </Card>
        </form>
      )}
    </div>
  );
}

export default function SettingsPage() {
  return (
    <Suspense fallback={<PageLoader />}>
      <SettingsContent />
    </Suspense>
  );
}
