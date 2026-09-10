'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { authApi } from '@/lib/api';
import { saveTokens, isLoggedIn } from '@/lib/auth';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import styles from './page.module.css';

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (isLoggedIn()) {
      router.replace('/');
    }
  }, [router]);


  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const tokens = await authApi.login(email, password);
      saveTokens(tokens.access_token, tokens.refresh_token);
      router.push('/');
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Login failed');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className={styles.card}>
      <div className={styles.header}>
        <div className={styles.logo}>⚡</div>
        <h1 className={styles.title}>Welcome back</h1>
        <p className={styles.subtitle}>Sign in to your PricePlus account</p>
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
          placeholder="••••••••"
          required
          autoComplete="current-password"
        />

        {error && <p className={styles.errorMsg}>{error}</p>}

        <Button type="submit" loading={loading} size="lg" style={{ width: '100%' }}>
          Sign in
        </Button>
      </form>

      <p className={styles.switch}>
        Don&apos;t have an account?{' '}
        <Link href="/register" className={styles.link}>Create one free</Link>
      </p>
    </div>
  );
}
