'use client';

import { useState, useEffect, Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import useSWR from 'swr';
import { settingsApi, authApi, User } from '@/lib/api';
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
  const rawTab = searchParams.get('tab');
  const initialTab = rawTab === 'tracking' ? 'tracking' : rawTab === 'discovery' ? 'discovery' : 'profile';
  const [activeTab, setActiveTab] = useState<'profile' | 'discovery' | 'tracking'>(initialTab);

  // User profile SWR
  const { data: user, mutate: mutateUser } = useSWR<User>('auth-me', () => authApi.me());

  // Profile form state
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [phoneNumber, setPhoneNumber] = useState('');
  const [savingProfile, setSavingProfile] = useState(false);
  const [savedProfile, setSavedProfile] = useState(false);
  const [profileErr, setProfileErr] = useState<string | null>(null);

  // Password form state
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [changingPassword, setChangingPassword] = useState(false);
  const [savedPassword, setSavedPassword] = useState(false);
  const [passwordErr, setPasswordErr] = useState<string | null>(null);

  useEffect(() => {
    if (user) {
      setFullName(user.full_name ?? '');
      setEmail(user.email ?? '');
      setPhoneNumber(user.phone_number ?? '');
    }
  }, [user]);

  // Settings SWR
  const { data: settingsData, isLoading: isSettingsLoading, mutate: mutateSettings } = useSWR('user-settings', () => settingsApi.get());

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

  const [savingSettings, setSavingSettings] = useState(false);
  const [savedSettings, setSavedSettings] = useState(false);

  useEffect(() => {
    if (settingsData) {
      setDiscConcurrency(settingsData.discovery_concurrency);
      setDiscMinDelay(settingsData.discovery_min_delay);
      setDiscMaxDelay(settingsData.discovery_max_delay);

      setTrackConcurrency(settingsData.tracking_concurrency ?? 5);
      setTrackMinDelay(settingsData.tracking_min_delay ?? 0.2);
      setTrackMaxDelay(settingsData.tracking_max_delay ?? 0.5);

      const discFound = DISCOVERY_PRESETS.find(
        p => p.concurrency === settingsData.discovery_concurrency &&
             Math.abs(p.minDelay - settingsData.discovery_min_delay) < 0.05 &&
             Math.abs(p.maxDelay - settingsData.discovery_max_delay) < 0.05
      );
      setActiveDiscPreset(discFound ? discFound.id : null);

      const trackFound = TRACKING_PRESETS.find(
        p => p.concurrency === (settingsData.tracking_concurrency ?? 5) &&
             Math.abs(p.minDelay - (settingsData.tracking_min_delay ?? 0.2)) < 0.05 &&
             Math.abs(p.maxDelay - (settingsData.tracking_max_delay ?? 0.5)) < 0.05
      );
      setActiveTrackPreset(trackFound ? trackFound.id : null);
    }
  }, [settingsData]);

  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    setSavingProfile(true);
    setSavedProfile(false);
    setProfileErr(null);
    try {
      const updatedUser = await authApi.updateProfile({
        full_name: fullName,
        email: email,
        phone_number: phoneNumber,
      });
      mutateUser(updatedUser, false);
      setSavedProfile(true);
      setTimeout(() => setSavedProfile(false), 3000);
    } catch (err: any) {
      setProfileErr(err.message || 'Failed to update profile');
    } finally {
      setSavingProfile(false);
    }
  };

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setPasswordErr(null);
    setSavedPassword(false);

    if (newPassword !== confirmPassword) {
      setPasswordErr('New passwords do not match');
      return;
    }
    if (newPassword.length < 8) {
      setPasswordErr('New password must be at least 8 characters long');
      return;
    }

    setChangingPassword(true);
    try {
      await authApi.changePassword(currentPassword, newPassword);
      setSavedPassword(true);
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
      setTimeout(() => setSavedPassword(false), 3000);
    } catch (err: any) {
      setPasswordErr(err.message || 'Failed to change password');
    } finally {
      setChangingPassword(false);
    }
  };

  const applyDiscPreset = (preset: Preset) => {
    setDiscConcurrency(preset.concurrency);
    setDiscMinDelay(preset.minDelay);
    setDiscMaxDelay(preset.maxDelay);
    setActiveDiscPreset(preset.id);
    setSavedSettings(false);
  };

  const applyTrackPreset = (preset: Preset) => {
    setTrackConcurrency(preset.concurrency);
    setTrackMinDelay(preset.minDelay);
    setTrackMaxDelay(preset.maxDelay);
    setActiveTrackPreset(preset.id);
    setSavedSettings(false);
  };

  const handleSaveSettings = async (e: React.FormEvent) => {
    e.preventDefault();
    setSavingSettings(true);
    setSavedSettings(false);
    try {
      const updated = await settingsApi.update({
        discovery_concurrency: discConcurrency,
        discovery_min_delay: discMinDelay,
        discovery_max_delay: discMaxDelay,
        tracking_concurrency: trackConcurrency,
        tracking_min_delay: trackMinDelay,
        tracking_max_delay: trackMaxDelay,
      });
      mutateSettings(updated, false);
      setSavedSettings(true);
      setTimeout(() => setSavedSettings(false), 3000);
    } catch (err) {
      console.error('Failed to update speed settings:', err);
    } finally {
      setSavingSettings(false);
    }
  };

  // Discovery rate calculation
  const discAvgDelay = (discMinDelay + discMaxDelay) / 2;
  const discReqPerSec = (discConcurrency / discAvgDelay).toFixed(1);

  // Tracking rate calculation
  const trackAvgDelay = (trackMinDelay + trackMaxDelay) / 2;
  const trackReqPerSec = (trackConcurrency / trackAvgDelay).toFixed(1);

  if (isSettingsLoading && activeTab !== 'profile') {
    return <PageLoader />;
  }

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <h1>Account & System Settings</h1>
        <p>Manage your account profile, credentials, catalog discovery speed, and background tracking rate limits.</p>
      </div>

      {/* Tabs Navigation */}
      <div className={styles.tabsNav}>
        <button
          className={[styles.tabBtn, activeTab === 'profile' ? styles.tabBtnActive : ''].join(' ')}
          onClick={() => setActiveTab('profile')}
        >
          👤 My Account & Profile
        </button>
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

      {/* Tab 1: Profile & Security */}
      {activeTab === 'profile' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          {/* Personal Information Form */}
          <Card glow>
            <CardHeader>
              <h3>👤 Personal Information</h3>
            </CardHeader>
            <CardBody>
              <form onSubmit={handleSaveProfile} className={styles.controlGroup}>
                <div className={styles.field}>
                  <label className={styles.label}>Full Name</label>
                  <input
                    type="text"
                    value={fullName}
                    onChange={e => setFullName(e.target.value)}
                    placeholder="Enter your full name"
                    className={styles.textInput}
                  />
                </div>

                <div className={styles.field}>
                  <label className={styles.label}>Email Address</label>
                  <input
                    type="email"
                    required
                    value={email}
                    onChange={e => setEmail(e.target.value)}
                    placeholder="user@example.com"
                    className={styles.textInput}
                  />
                  <p className={styles.hint}>Used for logging in and receiving price drop email notifications.</p>
                </div>

                <div className={styles.field}>
                  <label className={styles.label}>Phone Number</label>
                  <input
                    type="tel"
                    value={phoneNumber}
                    onChange={e => setPhoneNumber(e.target.value)}
                    placeholder="+1 (555) 000-0000"
                    className={styles.textInput}
                  />
                  <p className={styles.hint}>Optional contact phone number for SMS or account security alerts.</p>
                </div>

                {user && (
                  <div className={styles.gaugeCard} style={{ marginTop: '0.5rem' }}>
                    <div className={styles.gaugeStat}>
                      <span style={{ fontSize: '15px', fontWeight: 600, color: 'var(--color-text)' }}>
                        Role: {user.role_name}
                      </span>
                      <span className={styles.gaugeLabel}>Account Status: {user.is_active ? 'Active' : 'Inactive'}</span>
                    </div>
                    <div className={styles.safeBadge}>
                      🛡️ {user.permissions.length} Active Permissions
                    </div>
                  </div>
                )}

                <div className={styles.actions}>
                  <Button type="submit" loading={savingProfile}>Save Profile Changes</Button>
                  {savedProfile && (
                    <span className={styles.toastSuccess}>
                      ✓ Profile details updated successfully!
                    </span>
                  )}
                  {profileErr && (
                    <span className={styles.toastError}>
                      ⚠️ {profileErr}
                    </span>
                  )}
                </div>
              </form>
            </CardBody>
          </Card>

          {/* Security & Password Form */}
          <Card glow>
            <CardHeader>
              <h3>🔑 Security & Password</h3>
            </CardHeader>
            <CardBody>
              <form onSubmit={handleChangePassword} className={styles.controlGroup}>
                <div className={styles.field}>
                  <label className={styles.label}>Current Password</label>
                  <input
                    type="password"
                    required
                    value={currentPassword}
                    onChange={e => setCurrentPassword(e.target.value)}
                    placeholder="••••••••••••"
                    className={styles.textInput}
                  />
                </div>

                <div className={styles.field}>
                  <label className={styles.label}>New Password</label>
                  <input
                    type="password"
                    required
                    value={newPassword}
                    onChange={e => setNewPassword(e.target.value)}
                    placeholder="Min. 8 chars (letters & numbers)"
                    className={styles.textInput}
                  />
                </div>

                <div className={styles.field}>
                  <label className={styles.label}>Confirm New Password</label>
                  <input
                    type="password"
                    required
                    value={confirmPassword}
                    onChange={e => setConfirmPassword(e.target.value)}
                    placeholder="Repeat new password"
                    className={styles.textInput}
                  />
                </div>

                <div className={styles.actions}>
                  <Button type="submit" loading={changingPassword}>Change Password</Button>
                  {savedPassword && (
                    <span className={styles.toastSuccess}>
                      ✓ Password changed successfully!
                    </span>
                  )}
                  {passwordErr && (
                    <span className={styles.toastError}>
                      ⚠️ {passwordErr}
                    </span>
                  )}
                </div>
              </form>
            </CardBody>
          </Card>
        </div>
      )}

      {/* Tab 2: Store Discovery Speed */}
      {activeTab === 'discovery' && (
        <form onSubmit={handleSaveSettings} style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
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
                      setSavedSettings(false);
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
                      setSavedSettings(false);
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
                      setSavedSettings(false);
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
                  <Button type="submit" loading={savingSettings}>Save Discovery Speed Settings</Button>
                  {savedSettings && (
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

      {/* Tab 3: Product Tracking Speed */}
      {activeTab === 'tracking' && (
        <form onSubmit={handleSaveSettings} style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
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
                      setSavedSettings(false);
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
                      setSavedSettings(false);
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
                      setSavedSettings(false);
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
                  <Button type="submit" loading={savingSettings}>Save Tracking Speed Settings</Button>
                  {savedSettings && (
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
