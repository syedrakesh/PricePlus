'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { authApi } from '@/lib/api';
import { saveTokens } from '@/lib/auth';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import styles from '../login/page.module.css';

export default function RegisterPage() {
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const tokens = await authApi.register(email, password);
      saveTokens(tokens.access_token, tokens.refresh_token);
      router.push('/');
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Registration failed');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className={styles.card}>
      <div className={styles.header}>
        <div className={styles.logo}>⚡</div>
        <h1 className={styles.title}>Get started free</h1>
        <p className={styles.subtitle}>Create your PricePlus account</p>
      </div>

      <form onSubmit={handleSubmit} className={styles.form}>
        <Input
          label="Email"
          type="email"
          value={email}
          onChange={e => setEmail(e.target.value)}
          placeholder="you@example.com"
          required
          autoComplete="email"
        />
        <Input
          label="Password"
          type="password"
          value={password}
          onChange={e => setPassword(e.target.value)}
          placeholder="Min. 8 characters"
          required
          minLength={8}
          autoComplete="new-password"
          hint="At least 8 characters"
        />

        {error && <p className={styles.errorMsg}>{error}</p>}

        <Button type="submit" loading={loading} size="lg" style={{ width: '100%' }}>
          Create account
        </Button>
      </form>

      <p className={styles.switch}>
        Already have an account?{' '}
        <Link href="/login" className={styles.link}>Sign in</Link>
      </p>
    </div>
  );
}
