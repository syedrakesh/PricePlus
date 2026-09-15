'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { authApi } from '@/lib/api';
import { saveTokens } from '@/lib/auth';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import styles from '../login/page.module.css';

const PLANS = [
  { slug: 'free', name: 'Free', price: '$0/mo', desc: '1 Store, 3 Products' },
  { slug: 'starter', name: 'Starter', price: '$29/mo', desc: '3 Stores, 5 Products' },
  { slug: 'pro', name: 'Pro', price: '$79/mo', desc: '10 Stores, 25 Products' },
  { slug: 'enterprise', name: 'Enterprise', price: '$199/mo', desc: 'Unlimited Stores' },
];

export default function RegisterPage() {
  const router = useRouter();
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [selectedPlan, setSelectedPlan] = useState('free');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const tokens = await authApi.register(email, password, fullName || undefined, selectedPlan);

      if (tokens.checkout_url) {
        window.location.href = tokens.checkout_url;
      } else if (tokens.access_token && tokens.refresh_token) {
        saveTokens(tokens.access_token, tokens.refresh_token);
        router.push(tokens.redirect_url || '/onboarding');
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Registration failed');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className={styles.card} style={{ maxWidth: '480px' }}>
      <div className={styles.header}>
        <div className={styles.logo}>⚡</div>
        <h1 className={styles.title}>Create your account</h1>
        <p className={styles.subtitle}>Get started tracking competitor prices</p>
      </div>

      <form onSubmit={handleSubmit} className={styles.form}>
        <Input
          label="Full Name (optional)"
          type="text"
          value={fullName}
          onChange={e => setFullName(e.target.value)}
          placeholder="Jane Doe"
          autoComplete="name"
        />
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

        {/* Plan Selection Grid */}
        <div>
          <label style={{ display: 'block', fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--color-text-2)', marginBottom: '8px' }}>
            Choose Plan
          </label>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
            {PLANS.map(plan => {
              const isSelected = selectedPlan === plan.slug;
              return (
                <button
                  key={plan.slug}
                  type="button"
                  onClick={() => setSelectedPlan(plan.slug)}
                  style={{
                    padding: '10px 12px',
                    borderRadius: 'var(--radius-md)',
                    border: isSelected ? '2px solid var(--color-accent)' : '1px solid var(--color-border)',
                    background: isSelected ? 'rgba(99, 102, 241, 0.1)' : 'var(--color-surface-2)',
                    textAlign: 'left',
                    cursor: 'pointer',
                    transition: 'all 0.15s ease',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2px' }}>
                    <span style={{ fontWeight: 600, fontSize: '13px', color: 'var(--color-text)' }}>{plan.name}</span>
                    <span style={{ fontSize: '11px', color: isSelected ? 'var(--color-accent)' : 'var(--color-text-3)', fontWeight: 600 }}>{plan.price}</span>
                  </div>
                  <div style={{ fontSize: '11px', color: 'var(--color-text-3)' }}>{plan.desc}</div>
                </button>
              );
            })}
          </div>
        </div>

        {error && <p className={styles.errorMsg}>{error}</p>}

        <Button type="submit" loading={loading} size="lg" style={{ width: '100%', marginTop: '8px' }}>
          {selectedPlan === 'free' ? 'Start Free Onboarding' : `Subscribe to ${selectedPlan.charAt(0).toUpperCase() + selectedPlan.slice(1)} Plan`}
        </Button>
      </form>

      <p className={styles.switch}>
        Already have an account?{' '}
        <Link href="/login" className={styles.link}>Sign in</Link>
      </p>
    </div>
  );
}
