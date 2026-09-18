'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import useSWR from 'swr';
import { authApi, alertsApi, User } from '@/lib/api';
import { Card, CardHeader, CardBody } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { PageLoader } from '@/components/ui/Spinner';
import styles from '../page.module.css';

export default function NotificationSettingsPage() {
  const { data: user, isLoading, mutate: mutateUser } = useSWR<User>('auth-me', () => authApi.me());

  const [notificationEmail, setNotificationEmail] = useState('');
  const [emailEnabled, setEmailEnabled] = useState(true);

  const [telegramChatId, setTelegramChatId] = useState('');
  const [telegramBotToken, setTelegramBotToken] = useState('');
  const [telegramEnabled, setTelegramEnabled] = useState(true);

  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const [testEmailStatus, setTestEmailStatus] = useState<{ loading: boolean; msg: string | null; error: boolean }>({
    loading: false, msg: null, error: false
  });
  const [testTelegramStatus, setTestTelegramStatus] = useState<{ loading: boolean; msg: string | null; error: boolean }>({
    loading: false, msg: null, error: false
  });

  useEffect(() => {
    if (user) {
      setNotificationEmail(user.notification_email ?? '');
      setEmailEnabled(user.email_alerts_enabled ?? true);
      setTelegramChatId(user.telegram_chat_id ?? '');
      setTelegramBotToken(user.telegram_bot_token ?? '');
      setTelegramEnabled(user.telegram_alerts_enabled ?? true);
    }
  }, [user]);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setSaved(false);
    setErrorMsg(null);
    try {
      const updatedUser = await authApi.updateProfile({
        notification_email: notificationEmail || null,
        email_alerts_enabled: emailEnabled,
        telegram_chat_id: telegramChatId || null,
        telegram_bot_token: telegramBotToken || null,
        telegram_alerts_enabled: telegramEnabled,
      });
      mutateUser(updatedUser, false);
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : 'Failed to save notification settings');
    } finally {
      setSaving(false);
    }
  };

  const handleTestEmail = async () => {
    setTestEmailStatus({ loading: true, msg: null, error: false });
    try {
      const res = await alertsApi.sendTestNotification('email', {
        notification_email: notificationEmail || null,
      });
      setTestEmailStatus({ loading: false, msg: res.message, error: !res.success });
    } catch (err: unknown) {
      setTestEmailStatus({ loading: false, msg: err instanceof Error ? err.message : 'Test email failed', error: true });
    }
  };

  const handleTestTelegram = async () => {
    setTestTelegramStatus({ loading: true, msg: null, error: false });
    try {
      const res = await alertsApi.sendTestNotification('telegram', {
        telegram_chat_id: telegramChatId || null,
        telegram_bot_token: telegramBotToken || null,
      });
      setTestTelegramStatus({ loading: false, msg: res.message, error: !res.success });
    } catch (err: unknown) {
      setTestTelegramStatus({ loading: false, msg: err instanceof Error ? err.message : 'Test Telegram failed', error: true });
    }
  };

  if (isLoading) return <PageLoader />;

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <h1>🔔 Notification Channels & Alerts Settings</h1>
        <p>Configure Telegram, Email, and delivery preferences for price change notifications.</p>
      </div>

      <div className={styles.tabsNav}>
        <Link href="/settings/discovery" className={styles.tabBtn}>
          🔍 Discovery Speed
        </Link>
        <Link href="/settings/tracking" className={styles.tabBtn}>
          ⚡ Tracking Speed
        </Link>
        <Link href="/settings/notifications" className={`${styles.tabBtn} ${styles.tabBtnActive}`}>
          🔔 Notifications & Channels
        </Link>
      </div>

      <form onSubmit={handleSave} style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
        {/* Email Settings Card */}
        <Card glow>
          <CardHeader>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <span style={{ fontSize: '20px' }}>📧</span>
                <h3 style={{ margin: 0 }}>Email Notifications</h3>
              </div>
              <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', fontSize: '14px', fontWeight: 600 }}>
                <input
                  type="checkbox"
                  checked={emailEnabled}
                  onChange={e => setEmailEnabled(e.target.checked)}
                  style={{ width: '18px', height: '18px', accentColor: 'var(--color-accent)' }}
                />
                Email Alerts Enabled
              </label>
            </div>
          </CardHeader>
          <CardBody>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '13px', fontWeight: 600, color: 'var(--color-text-2)', marginBottom: '6px' }}>
                  Notification Email Address
                </label>
                <input
                  type="text"
                  value={notificationEmail}
                  onChange={e => setNotificationEmail(e.target.value)}
                  placeholder="e.g. user1@example.com, team@company.com (comma-separated for multiple)"
                  style={{
                    width: '100%', padding: '10px 14px', borderRadius: 'var(--radius-md)',
                    background: 'var(--color-surface-2)', border: '1px solid var(--color-border)',
                    color: 'var(--color-text)', fontSize: '14px'
                  }}
                />
                <p style={{ fontSize: '12px', color: 'var(--color-text-3)', marginTop: '4px' }}>
                  Enter one or multiple recipient emails separated by commas. Leave empty to use primary account email (<strong>{user?.email}</strong>).
                </p>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginTop: '4px' }}>
                <Button type="button" variant="secondary" size="sm" onClick={handleTestEmail} disabled={testEmailStatus.loading}>
                  {testEmailStatus.loading ? 'Sending Test...' : '✉️ Send Test Email'}
                </Button>
                {testEmailStatus.msg && (
                  <span style={{
                    fontSize: '13px',
                    color: testEmailStatus.error ? '#f87171' : '#4ade80',
                    fontWeight: 500
                  }}>
                    {testEmailStatus.msg}
                  </span>
                )}
              </div>
            </div>
          </CardBody>
        </Card>

        {/* Telegram Settings Card */}
        <Card glow>
          <CardHeader>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <span style={{ fontSize: '20px' }}>✈️</span>
                <h3 style={{ margin: 0 }}>Telegram Notifications</h3>
              </div>
              <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', fontSize: '14px', fontWeight: 600 }}>
                <input
                  type="checkbox"
                  checked={telegramEnabled}
                  onChange={e => setTelegramEnabled(e.target.checked)}
                  style={{ width: '18px', height: '18px', accentColor: 'var(--color-accent)' }}
                />
                Telegram Alerts Enabled
              </label>
            </div>
          </CardHeader>
          <CardBody>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '13px', fontWeight: 600, color: 'var(--color-text-2)', marginBottom: '6px' }}>
                  Telegram Chat ID(s)
                </label>
                <input
                  type="text"
                  value={telegramChatId}
                  onChange={e => setTelegramChatId(e.target.value)}
                  placeholder="e.g. 123456789, 987654321, @channel (comma-separated for multiple)"
                  style={{
                    width: '100%', padding: '10px 14px', borderRadius: 'var(--radius-md)',
                    background: 'var(--color-surface-2)', border: '1px solid var(--color-border)',
                    color: 'var(--color-text)', fontSize: '14px'
                  }}
                />
                <p style={{ fontSize: '12px', color: 'var(--color-text-3)', marginTop: '4px' }}>
                  Enter one or multiple Chat IDs / Channels separated by commas. Start a chat with <strong><a href="https://t.me/userinfobot">@userinfobot</a></strong> on Telegram to find your Chat ID.
                </p>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '13px', fontWeight: 600, color: 'var(--color-text-2)', marginBottom: '6px' }}>
                  Custom Telegram Bot Token (Optional)
                </label>
                <input
                  type="password"
                  value={telegramBotToken}
                  onChange={e => setTelegramBotToken(e.target.value)}
                  placeholder="e.g. 123456789:ABCdefGHIjklmNOPqrstUVWxyz"
                  style={{
                    width: '100%', padding: '10px 14px', borderRadius: 'var(--radius-md)',
                    background: 'var(--color-surface-2)', border: '1px solid var(--color-border)',
                    color: 'var(--color-text)', fontSize: '14px'
                  }}
                />
                <p style={{ fontSize: '12px', color: 'var(--color-text-3)', marginTop: '4px' }}>
                  Optional. If left blank, PricePlus uses the default system Telegram bot.
                </p>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginTop: '4px' }}>
                <Button type="button" variant="secondary" size="sm" onClick={handleTestTelegram} disabled={testTelegramStatus.loading}>
                  {testTelegramStatus.loading ? 'Sending Test...' : '🚀 Send Test Telegram Message'}
                </Button>
                {testTelegramStatus.msg && (
                  <span style={{
                    fontSize: '13px',
                    color: testTelegramStatus.error ? '#f87171' : '#4ade80',
                    fontWeight: 500
                  }}>
                    {testTelegramStatus.msg}
                  </span>
                )}
              </div>
            </div>
          </CardBody>
        </Card>

        {errorMsg && (
          <div style={{ color: '#f87171', background: 'rgba(239,68,68,0.1)', padding: '10px 14px', borderRadius: 'var(--radius-md)', fontSize: '14px' }}>
            ⚠️ {errorMsg}
          </div>
        )}

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <Button type="submit" variant="primary" disabled={saving}>
            {saving ? 'Saving Settings...' : '💾 Save Notification Settings'}
          </Button>
          {saved && (
            <span style={{ color: '#4ade80', fontSize: '14px', fontWeight: 600 }}>
              ✅ Notification settings saved successfully!
            </span>
          )}
        </div>
      </form>
    </div>
  );
}
