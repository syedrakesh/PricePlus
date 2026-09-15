'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { storesApi, productsApi, trackingApi, authApi, DiscoveredProduct } from '@/lib/api';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import styles from './page.module.css';

export default function OnboardingPage() {
  const router = useRouter();
  const [step, setStep] = useState<1 | 2 | 3 | 4>(1);

  // Form state
  const [storeName, setStoreName] = useState('');
  const [storeUrl, setStoreUrl] = useState('');
  const [storeId, setStoreId] = useState<string | null>(null);
  const [discoveredProducts, setDiscoveredProducts] = useState<DiscoveredProduct[]>([]);
  const [trackedProductIds, setTrackedProductIds] = useState<Set<string>>(new Set());
  const [alertThreshold, setAlertThreshold] = useState('5');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Step 1: Add Store
  async function handleAddStore(e: React.FormEvent) {
    e.preventDefault();
    if (!storeUrl.trim()) return;

    setError('');
    setLoading(true);
    try {
      let formattedUrl = storeUrl.trim();
      if (!formattedUrl.startsWith('http://') && !formattedUrl.startsWith('https://')) {
        formattedUrl = `https://${formattedUrl}`;
      }

      const displayName = storeName.trim() || new URL(formattedUrl).hostname;
      const store = await storesApi.create(formattedUrl, displayName);

      setStoreId(store.id);

      // Trigger initial discovery scan
      await storesApi.triggerDiscovery(store.id);
      setStep(2);
      fetchDiscoveredProducts(store.id);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to add store. Please check the URL.');
    } finally {
      setLoading(false);
    }
  }

  // Step 2: Fetch discovered products
  async function fetchDiscoveredProducts(sid: string) {
    setLoading(true);
    try {
      const res = await productsApi.list(sid, 1, 10);
      setDiscoveredProducts(res.products);
    } catch (err) {
      console.error('Discovery fetch error:', err);
    } finally {
      setLoading(false);
    }
  }

  // Step 3: Track a product
  async function handleToggleTrack(product: DiscoveredProduct) {
    if (trackedProductIds.has(product.id)) return;

    try {
      await trackingApi.track(product.id);
      setTrackedProductIds(prev => new Set(prev).add(product.id));
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Could not track product');
    }
  }

  // Step 4: Finish Onboarding
  async function handleFinishOnboarding() {
    setLoading(true);
    try {
      await authApi.completeOnboarding();
      router.push('/');
    } catch {
      router.push('/');
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
          <span>Step {step} of 4</span>
          <span>{step === 1 ? 'Add Store' : step === 2 ? 'Discover Products' : step === 3 ? 'Track Products' : 'Configure Alerts'}</span>
        </div>
        <div className={styles.progressBarBg}>
          <div
            className={styles.progressBarFill}
            style={{ width: `${(step / 4) * 100}%` }}
          />
        </div>
      </div>

      {/* Wizard Card */}
      <div className={styles.card}>
        {error && <div className={styles.errorBox}>⚠️ {error}</div>}

        {/* STEP 1: Add Store */}
        {step === 1 && (
          <form onSubmit={handleAddStore} className={styles.formStep}>
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

            <Button type="submit" loading={loading} size="lg" style={{ width: '100%', marginTop: '12px' }}>
              Add Store & Discover Catalog →
            </Button>
          </form>
        )}

        {/* STEP 2: Catalog Scanning / Results */}
        {step === 2 && (
          <div className={styles.formStep}>
            <div className={styles.stepTitle}>2. Product Discovery Scan</div>
            <p className={styles.stepDesc}>We are automatically scanning the store catalog for products.</p>

            {loading ? (
              <div className={styles.loadingState}>
                <div className={styles.spinner} />
                <p>Scanning store sitemaps for products...</p>
              </div>
            ) : discoveredProducts.length > 0 ? (
              <div className={styles.productList}>
                {discoveredProducts.slice(0, 4).map(p => (
                  <div key={p.id} className={styles.productRow}>
                    <div className={styles.productThumb}>📦</div>
                    <div className={styles.productMeta}>
                      <div className={styles.productName}>{p.title}</div>
                      <div className={styles.productPrice}>{p.current_price ? `$${p.current_price.toFixed(2)}` : 'Price pending'}</div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className={styles.emptyScan}>
                Discovery in progress. Click continue to proceed to product tracking.
              </div>
            )}

            <Button onClick={() => setStep(3)} size="lg" style={{ width: '100%', marginTop: '16px' }}>
              Proceed to Track Products →
            </Button>
          </div>
        )}

        {/* STEP 3: Track Products */}
        {step === 3 && (
          <div className={styles.formStep}>
            <div className={styles.stepTitle}>3. Select Products to Track</div>
            <p className={styles.stepDesc}>Track items to receive automated price monitoring alerts when prices change.</p>

            {discoveredProducts.length > 0 ? (
              <div className={styles.productList}>
                {discoveredProducts.slice(0, 5).map(p => {
                  const isTracked = trackedProductIds.has(p.id) || p.is_tracked;
                  return (
                    <div key={p.id} className={styles.productRow}>
                      <div className={styles.productThumb}>📦</div>
                      <div className={styles.productMeta}>
                        <div className={styles.productName}>{p.title}</div>
                        <div className={styles.productPrice}>{p.current_price ? `$${p.current_price.toFixed(2)}` : 'N/A'}</div>
                      </div>
                      <Button
                        variant={isTracked ? 'secondary' : 'primary'}
                        size="sm"
                        onClick={() => handleToggleTrack(p)}
                        disabled={isTracked}
                      >
                        {isTracked ? '✓ Tracking' : '+ Track'}
                      </Button>
                    </div>
                  );
                })}
              </div>
            ) : (
              <p className={styles.stepDesc}>No products discovered yet. You can add product URLs directly from your store page anytime.</p>
            )}

            <Button onClick={() => setStep(4)} size="lg" style={{ width: '100%', marginTop: '16px' }}>
              Continue to Alert Settings →
            </Button>
          </div>
        )}

        {/* STEP 4: Configure Email Alerts */}
        {step === 4 && (
          <div className={styles.formStep}>
            <div className={styles.stepTitle}>4. Price Drop Alert Preferences</div>
            <p className={styles.stepDesc}>Configure notifications when competitor prices change.</p>

            <Input
              label="Minimum Price Drop Threshold (%)"
              type="number"
              value={alertThreshold}
              onChange={e => setAlertThreshold(e.target.value)}
              placeholder="5"
              hint="Trigger email notification if price drops by 5% or more"
            />

            <div className={styles.alertPreview}>
              📧 Automated email alerts will be sent to your account email when price drops occur.
            </div>

            <Button onClick={handleFinishOnboarding} loading={loading} size="lg" style={{ width: '100%', marginTop: '16px' }}>
              Finish Setup & Launch Dashboard 🚀
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
