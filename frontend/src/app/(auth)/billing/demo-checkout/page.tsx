'use client';

import { Suspense, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Button } from '@/components/ui/Button';
import styles from '../../login/page.module.css';

const PLAN_DETAILS: Record<string, { name: string; price: string; features: string[] }> = {
  starter: {
    name: 'Starter Plan',
    price: '$29.00 / month',
    features: ['3 Competitor Stores', '100 Tracked Products', '3-Hour Check Frequency', 'CSV Export & Instant Alerts'],
  },
  pro: {
    name: 'Pro Plan',
    price: '$79.00 / month',
    features: ['10 Competitor Stores', '500 Tracked Products', '1-Hour Check Frequency', 'VIP Monitoring & Instant Alerts'],
  },
  enterprise: {
    name: 'Enterprise Plan',
    price: '$299.00 / month',
    features: ['50 Competitor Stores', '5,000 Tracked Products', '1-Min Realtime Checking', 'Dedicated Proxy Network & VIP Support'],
  },
};

function DemoCheckoutForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const planSlug = (searchParams.get('plan') || 'pro').toLowerCase();
  const sessionId = searchParams.get('session_id') || `mock_session_${planSlug}`;

  const plan = PLAN_DETAILS[planSlug] || PLAN_DETAILS.pro;
  const [loading, setLoading] = useState(false);

  function handleCompleteDemoPayment() {
    setLoading(true);
    setTimeout(() => {
      // Redirect to onboarding with session_id to verify payment and activate plan
      window.location.href = `/onboarding?session_id=${encodeURIComponent(sessionId)}`;
    }, 800);
  }

  return (
    <div className={styles.card} style={{ maxWidth: '520px' }}>
      <div className={styles.header}>
        <div className={styles.logo}>💳</div>
        <h1 className={styles.title}>Stripe Test Checkout</h1>
        <p className={styles.subtitle}>Demo Mode — Simulate Payment for {plan.name}</p>
      </div>

      {/* Plan Summary */}
      <div style={{
        background: 'var(--color-surface-2)',
        border: '1px solid var(--color-border)',
        borderRadius: 'var(--radius-lg)',
        padding: '16px',
        marginBottom: '20px',
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
          <span style={{ fontSize: '16px', fontWeight: 700, color: 'var(--color-text)' }}>{plan.name}</span>
          <span style={{ fontSize: '15px', fontWeight: 700, color: 'var(--color-accent)' }}>{plan.price}</span>
        </div>
        <ul style={{ margin: 0, paddingLeft: '18px', fontSize: '13px', color: 'var(--color-text-2)', display: 'flex', flexDirection: 'column', gap: '4px' }}>
          {plan.features.map((feat, idx) => (
            <li key={idx}>{feat}</li>
          ))}
        </ul>
      </div>

      {/* Simulated Credit Card Input */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginBottom: '24px' }}>
        <div>
          <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--color-text-2)', marginBottom: '4px' }}>
            Card Number (Demo Test Card)
          </label>
          <div style={{
            display: 'flex', alignItems: 'center', background: 'var(--color-surface-1)',
            border: '1px solid var(--color-border)', borderRadius: 'var(--radius-md)', padding: '10px 12px',
            fontSize: '14px', fontFamily: 'monospace', color: 'var(--color-text)'
          }}>
            <span style={{ marginRight: '8px' }}>💳</span> 4242 •••• •••• 4242
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
          <div>
            <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--color-text-2)', marginBottom: '4px' }}>
              Expires
            </label>
            <div style={{
              background: 'var(--color-surface-1)', border: '1px solid var(--color-border)',
              borderRadius: 'var(--radius-md)', padding: '10px 12px', fontSize: '14px', fontFamily: 'monospace', color: 'var(--color-text)'
            }}>
              12 / 28
            </div>
          </div>
          <div>
            <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--color-text-2)', marginBottom: '4px' }}>
              CVC
            </label>
            <div style={{
              background: 'var(--color-surface-1)', border: '1px solid var(--color-border)',
              borderRadius: 'var(--radius-md)', padding: '10px 12px', fontSize: '14px', fontFamily: 'monospace', color: 'var(--color-text)'
            }}>
              123
            </div>
          </div>
        </div>
      </div>

      <Button onClick={handleCompleteDemoPayment} loading={loading} size="lg" style={{ width: '100%' }}>
        Complete Demo Payment ({plan.price.split(' ')[0]}) 🔒
      </Button>

      <div style={{ textAlign: 'center', marginTop: '16px' }}>
        <button
          type="button"
          onClick={() => router.push('/register?canceled=1')}
          style={{ background: 'none', border: 'none', color: 'var(--color-text-3)', fontSize: '13px', cursor: 'pointer' }}
        >
          Cancel and return to registration
        </button>
      </div>
    </div>
  );
}

export default function DemoCheckoutPage() {
  return (
    <Suspense fallback={<div>Loading checkout...</div>}>
      <DemoCheckoutForm />
    </Suspense>
  );
}
