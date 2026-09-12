'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import useSWR from 'swr';
import { authApi, User } from '@/lib/api';
import { Card, CardHeader, CardBody } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { PageLoader } from '@/components/ui/Spinner';
import styles from './page.module.css';

export default function AccountPage() {
  const { data: user, isLoading, mutate: mutateUser } = useSWR<User>('auth-me', () => authApi.me());

  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [phoneNumber, setPhoneNumber] = useState('');
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    if (user) {
      setFullName(user.full_name ?? '');
      setEmail(user.email ?? '');
      setPhoneNumber(user.phone_number ?? '');
    }
  }, [user]);

  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setSaved(false);
    setErrorMsg(null);
    try {
      const updatedUser = await authApi.updateProfile({
        full_name: fullName,
        email: email,
        phone_number: phoneNumber,
      });
      mutateUser(updatedUser, false);
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to update profile');
    } finally {
      setSaving(false);
    }
  };

  if (isLoading) return <PageLoader />;

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <h1>👤 My Profile & Identity</h1>
        <p>Manage your account personal details, contact info, and role permissions.</p>
      </div>

      <Card glow>
        <CardHeader>
          <h3>Personal Details</h3>
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
              <p className={styles.hint}>Used for logging in and receiving price drop alert notifications.</p>
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
              <p className={styles.hint}>Optional contact number for account alerts or verification.</p>
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
              <Button type="submit" loading={saving}>Save Profile Changes</Button>
              {saved && (
                <span className={styles.toastSuccess}>
                  ✓ Profile details updated successfully!
                </span>
              )}
              {errorMsg && (
                <span className={styles.toastError}>
                  ⚠️ {errorMsg}
                </span>
              )}
            </div>
          </form>
        </CardBody>
      </Card>

      {/* Security Quick Link Card */}
      <Card>
        <CardBody className={styles.gaugeCard}>
          <div>
            <h4 style={{ margin: 0, fontSize: '1rem', fontWeight: 600 }}>🔑 Password & Security</h4>
            <p style={{ margin: '4px 0 0 0', fontSize: '0.825rem', color: 'var(--color-text-3)' }}>
              Want to update your password? Go to the dedicated Security screen.
            </p>
          </div>
          <Link href="/account/security">
            <Button variant="secondary">Go to Security →</Button>
          </Link>
        </CardBody>
      </Card>
    </div>
  );
}
