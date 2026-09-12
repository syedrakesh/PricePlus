'use client';

import { useState } from 'react';
import { authApi } from '@/lib/api';
import { Card, CardHeader, CardBody } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import styles from '../page.module.css';

export default function SecurityPage() {
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [changing, setChanging] = useState(false);
  const [saved, setSaved] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);
    setSaved(false);

    if (newPassword !== confirmPassword) {
      setErrorMsg('New passwords do not match');
      return;
    }
    if (newPassword.length < 8) {
      setErrorMsg('New password must be at least 8 characters long');
      return;
    }

    setChanging(true);
    try {
      await authApi.changePassword(currentPassword, newPassword);
      setSaved(true);
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
      setTimeout(() => setSaved(false), 3000);
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to change password');
    } finally {
      setChanging(false);
    }
  };

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <h1>🔑 Security & Password</h1>
        <p>Update your account authentication password and access credentials.</p>
      </div>

      <Card glow>
        <CardHeader>
          <h3>Change Password</h3>
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
              <Button type="submit" loading={changing}>Update Password</Button>
              {saved && (
                <span className={styles.toastSuccess}>
                  ✓ Password changed successfully!
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
    </div>
  );
}
