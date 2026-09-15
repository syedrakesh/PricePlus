'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import useSWR from 'swr';
import { storesApi, authApi } from '@/lib/api';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { PageLoader } from '@/components/ui/Spinner';
import styles from './page.module.css';

export default function OnboardingPage() {
  const router = useRouter();
  const { data: user, isLoading: userLoading } = useSWR('auth-me', () => authApi.me());
  const [step, setStep] = useState<1 | 2>(1);

  // Form state kept in local memory until Finish button click
  const [storeName, setStoreName] = useState('');
  const [storeUrl, setStoreUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Auto-redirect if onboarding is already completed
  useEffect(() => {
    if (user?.onboarding_completed) {
      router.replace('/');
    }
  }, [user, router]);

  if (userLoading || user?.onboarding_completed) {
    return <PageLoader />;
  }

  // Step 1: Validate input & move to confirmation (No DB call!)
  function handleStep1Submit(e: React.FormEvent) {
    e.preventDefault();
    if (!storeUrl.trim()) return;

    setError('');
    let formattedUrl = storeUrl.trim();
    if (!formattedUrl.startsWith('http://') && !formattedUrl.startsWith('https://')) {
      formattedUrl = `https://${formattedUrl}`;
    }

    try {
      new URL(formattedUrl);
    } catch {
      setError('Please enter a valid store URL');
      return;
    }

    setStoreUrl(formattedUrl);
    setStep(2);
  }

  // Finish Onboarding: Create store, trigger discovery, and complete onboarding in DB
  async function handleFinishOnboarding() {
    if (!storeUrl) {
      setStep(1);
      return;
    }

    setLoading(true);
    setError('');
    try {
      const displayName = storeName.trim() || new URL(storeUrl).hostname;
      
      // 1. Create store in DB
      const store = await storesApi.create(storeUrl, displayName);

      // 2. Trigger discovery scan in DB
      try {
        await storesApi.triggerDiscovery(store.id);
      } catch (discErr) {
        console.warn('Initial discovery trigger note:', discErr);
      }

      // 3. Mark onboarding completed in DB
      await authApi.completeOnboarding();
      router.push('/');
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to complete onboarding');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className={styles.container}>
      {/* Onboarding Header */}
      <div className={styles.header}>
        <div className={styles.badge}>Quick Onboarding</div>
        <h1 className={styles.title}>Welcome to PricePlus ⚡</h1>
        <p className={styles.subtitle}>Set up your competitor price tracking in 60 seconds</p>
      </div>

      {/* Progress Bar */}
      <div className={styles.progressContainer}>
        <div className={styles.stepsLabel}>
          <span>Step {step} of 2</span>
          <span>{step === 1 ? 'Add Store' : 'Confirm & Launch'}</span>
        </div>
        <div className={styles.progressBarBg}>
          <div
            className={styles.progressBarFill}
            style={{ width: `${(step / 2) * 100}%` }}
          />
        </div>
      </div>

      {/* Wizard Card */}
      <div className={styles.card}>
        {error && <div className={styles.errorBox}>⚠️ {error}</div>}

        {/* STEP 1: Enter Store URL & Name */}
        {step === 1 && (
          <form onSubmit={handleStep1Submit} className={styles.formStep}>
            <div className={styles.stepTitle}>1. Add Your First Competitor Store</div>
            <p className={styles.stepDesc}>Enter any Shopify or e-commerce store URL to scan catalog prices.</p>

            <Input
              label="Store URL"
              type="text"
              value={storeUrl}
              onChange={e => setStoreUrl(e.target.value)}
              placeholder="https://competitor-shop.com"
              required
              hint="e.g. york-fashion.com or competitor-store.myshopify.com"
            />

            <Input
              label="Store Name (optional)"
              type="text"
              value={storeName}
              onChange={e => setStoreName(e.target.value)}
              placeholder="Competitor Fashion"
            />

            <Button type="submit" size="lg" style={{ width: '100%', marginTop: '12px' }}>
              Continue to Confirmation →
            </Button>
          </form>
        )}

        {/* STEP 2: Confirm & Launch Dashboard */}
        {step === 2 && (
          <div className={styles.formStep}>
            <div className={styles.stepTitle}>2. Confirm Store Setup</div>
            <p className={styles.stepDesc}>Review your competitor store details before launching your dashboard.</p>

            <div style={{
              background: 'var(--color-surface-2)', border: '1px solid var(--color-border)',
              borderRadius: 'var(--radius-lg)', padding: '16px', display: 'flex', flexDirection: 'column', gap: '8px'
            }}>
              <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--color-text)' }}>
                🏪 Store: {storeName.trim() || new URL(storeUrl).hostname}
              </div>
              <div style={{ fontSize: '13px', color: 'var(--color-text-2)', fontFamily: 'monospace' }}>
                🔗 {storeUrl}
              </div>
              <div style={{ fontSize: '12px', color: 'var(--color-accent)', marginTop: '4px' }}>
                ⚡ Catalog discovery scan will automatically run upon launching your dashboard.
              </div>
            </div>

            <div style={{ display: 'flex', gap: '8px', marginTop: '16px' }}>
              <Button type="button" variant="secondary" onClick={() => setStep(1)} disabled={loading}>
                ← Back
              </Button>
              <Button onClick={handleFinishOnboarding} loading={loading} size="lg" style={{ flex: 1 }}>
                Finish Setup & Launch Dashboard 🚀
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
