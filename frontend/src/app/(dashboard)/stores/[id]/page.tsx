'use client';

import { useState, use } from 'react';
import useSWR from 'swr';
import Link from 'next/link';
import { billingApi, productsApi, trackingApi } from '@/lib/api';
import { Card, CardHeader, CardBody } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { EmptyState, PageLoader } from '@/components/ui/Spinner';
import styles from './page.module.css';

function getPageNumbers(current: number, total: number): (number | '...')[] {
  if (total <= 7) {
    return Array.from({ length: total }, (_, i) => i + 1);
  }
  if (current <= 4) {
    return [1, 2, 3, 4, 5, '...', total];
  }
  if (current >= total - 3) {
    return [1, '...', total - 4, total - 3, total - 2, total - 1, total];
  }
  return [1, '...', current - 1, current, current + 1, '...', total];
}

export default function StoreDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [page, setPage] = useState(1);
  const [inputPage, setInputPage] = useState('');
  const pageSize = 40;

  // Filter states
  const [searchQuery, setSearchQuery] = useState('');
  const [minPrice, setMinPrice] = useState('');
  const [maxPrice, setMaxPrice] = useState('');
  const [error, setError] = useState('');

  const activeFilters = {
    q: searchQuery.trim() || undefined,
    min_price: minPrice ? parseFloat(minPrice) : undefined,
    max_price: maxPrice ? parseFloat(maxPrice) : undefined,
  };

  const { data, isLoading, mutate } = useSWR(
    `store-products-${id}-${page}-${searchQuery}-${minPrice}-${maxPrice}`,
    () => productsApi.list(id, page, pageSize, activeFilters)
  );

  const { data: entitlements, mutate: mutateEntitlements } = useSWR(
    'entitlements',
    () => billingApi.entitlements()
  );

  const [tracking, setTracking] = useState<Record<string, boolean>>({});

  const isProductLimitReached = !!(
    entitlements && entitlements.current_tracked_products >= entitlements.max_tracked_products
  );

  async function handleTrack(discoveredProductId: string) {
    setError('');

    if (isProductLimitReached) {
      setError(`Tracked product limit reached (${entitlements?.current_tracked_products}/${entitlements?.max_tracked_products}) for ${entitlements?.plan_name} plan. Please upgrade your plan.`);
      return;
    }

    setTracking(t => ({ ...t, [discoveredProductId]: true }));
    try {
      await trackingApi.track(discoveredProductId);
      if (data) {
        mutate(
          {
            ...data,
            products: data.products.map(p =>
              p.id === discoveredProductId ? { ...p, is_tracked: true } : p
            ),
          },
          false
        );
      }
      await mutate();
      await mutateEntitlements();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to track product');
    } finally {
      setTracking(t => ({ ...t, [discoveredProductId]: false }));
    }
  }

  const goToPage = (p: number) => {
    setPage(p);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const resetFilters = () => {
    setSearchQuery('');
    setMinPrice('');
    setMaxPrice('');
    setPage(1);
  };

  const hasActiveFilters = !!(searchQuery || minPrice || maxPrice);
  const tracked = data?.products.filter(p => p.is_tracked).length ?? 0;
  const total = data?.total ?? 0;
  const totalPages = data ? Math.ceil(data.total / pageSize) : 1;
  const pageNumbers = getPageNumbers(page, totalPages);

  const handleJumpSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const val = parseInt(inputPage, 10);
    if (!isNaN(val) && val >= 1 && val <= totalPages) {
      goToPage(val);
      setInputPage('');
    }
  };


  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <h1>Store Products</h1>
            {entitlements && (
              <Badge variant={isProductLimitReached ? 'warning' : 'accent'}>
                {entitlements.current_tracked_products} / {entitlements.max_tracked_products} Products Tracked
              </Badge>
            )}
          </div>
          <p className={styles.sub}>
            {isLoading ? 'Loading…' : `${total} products found · Showing page ${page} of ${totalPages}`}
          </p>
        </div>
      </div>

      {(isProductLimitReached || error) && (
        <div style={{
          padding: '1rem',
          borderRadius: '8px',
          background: 'rgba(239, 68, 68, 0.1)',
          border: '1px solid rgba(239, 68, 68, 0.3)',
          marginBottom: '1rem',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '1rem'
        }}>
          <span style={{ color: '#ef4444', fontSize: '0.9rem', fontWeight: 500 }}>
            ⚠️ {error || `Tracked product limit reached (${entitlements?.current_tracked_products}/${entitlements?.max_tracked_products}) on your ${entitlements?.plan_name} plan.`}
          </span>
          <Link href="/billing">
            <Button size="sm" variant="primary">Upgrade Plan</Button>
          </Link>
        </div>
      )}

      {/* Search & Filter Bar */}
      <Card className={styles.filterCard}>
        <CardBody>
          <div className={styles.filterBar}>
            <div className={styles.searchInputGroup}>
              <span className={styles.searchIcon}>🔍</span>
              <input
                type="text"
                placeholder="Search products by title or handle (e.g. biryani, chicken)..."
                value={searchQuery}
                onChange={e => {
                  setSearchQuery(e.target.value);
                  setPage(1);
                }}
                className={styles.searchInput}
              />
              {searchQuery && (
                <button className={styles.clearBtn} onClick={() => setSearchQuery('')}>✕</button>
              )}
            </div>

            <div className={styles.filterGroup}>
              <div className={styles.priceRange}>
                <input
                  type="number"
                  placeholder="Min $"
                  min="0"
                  step="0.01"
                  value={minPrice}
                  onChange={e => {
                    setMinPrice(e.target.value);
                    setPage(1);
                  }}
                  className={styles.filterInput}
                />
                <span className={styles.rangeDash}>–</span>
                <input
                  type="number"
                  placeholder="Max $"
                  min="0"
                  step="0.01"
                  value={maxPrice}
                  onChange={e => {
                    setMaxPrice(e.target.value);
                    setPage(1);
                  }}
                  className={styles.filterInput}
                />
              </div>

              {hasActiveFilters && (
                <Button size="sm" variant="secondary" onClick={resetFilters}>
                  Clear Filters
                </Button>
              )}
            </div>
          </div>
        </CardBody>
      </Card>


      {isLoading ? (
        <PageLoader />
      ) : !(data?.products ?? []).length ? (
        <EmptyState
          icon="📦"
          title="No products found"
          description="Trigger a discovery run to scan this store's product catalog."
        />
      ) : (
        <>
          <div className={styles.grid}>
            {(data?.products ?? []).map(product => (
              <Card key={product.id} className={styles.productCard}>
                <CardBody>
                  {product.image_url && (
                    <img src={product.image_url} alt={product.title ?? ''} className={styles.productImg} />
                  )}
                  {!product.image_url && (
                    <div className={styles.productImgPlaceholder}>📦</div>
                  )}
                  <h3 className={styles.productTitle}>{product.title ?? product.handle}</h3>
                  <div className={styles.productMeta}>
                    {product.is_discontinued ? (
                      <span className={styles.noPrice}>Discontinued</span>
                    ) : product.current_price !== null ? (
                      <div className={styles.priceBlock}>
                        <span className={styles.price}>${product.current_price.toFixed(2)}</span>
                        {product.is_on_sale && product.compare_at_price !== null && (
                          <span className={styles.comparePrice}>${product.compare_at_price.toFixed(2)}</span>
                        )}
                      </div>
                    ) : (
                      <span className={styles.noPrice}>No price</span>
                    )}
                    <div className={styles.badgeRow}>
                      {product.is_on_sale && !product.is_discontinued && (
                        <Badge variant="danger">🏷️ Sale</Badge>
                      )}
                      {product.is_discontinued && (
                        <Badge variant="warning">Discontinued</Badge>
                      )}
                    </div>
                  </div>
                  <Button
                    size="sm"
                    variant={product.is_tracked ? 'secondary' : isProductLimitReached ? 'danger' : 'primary'}
                    style={{ width: '100%', marginTop: '12px' }}
                    loading={tracking[product.id]}
                    disabled={product.is_tracked || isProductLimitReached}
                    title={isProductLimitReached && !product.is_tracked ? "Tracked product limit reached. Upgrade your plan." : undefined}
                    onClick={() => !product.is_tracked && handleTrack(product.id)}
                  >
                    {product.is_tracked ? '✓ Tracking' : isProductLimitReached ? 'Limit Reached' : 'Track Product'}
                  </Button>
                </CardBody>
              </Card>
            ))}
          </div>

          {totalPages > 1 && (
            <div className={styles.paginationWrapper}>
              <div className={styles.pagination}>
                <Button
                  size="sm"
                  variant="secondary"
                  disabled={page <= 1}
                  onClick={() => goToPage(1)}
                  title="First page"
                >
                  «
                </Button>
                <Button
                  size="sm"
                  variant="secondary"
                  disabled={page <= 1}
                  onClick={() => goToPage(page - 1)}
                >
                  ← Prev
                </Button>

                <div className={styles.pageNumbers}>
                  {pageNumbers.map((p, idx) =>
                    p === '...' ? (
                      <span key={`dots-${idx}`} className={styles.ellipsis}>…</span>
                    ) : (
                      <button
                        key={p}
                        className={`${styles.pageBtn} ${p === page ? styles.activePageBtn : ''}`}
                        onClick={() => goToPage(p)}
                      >
                        {p}
                      </button>
                    )
                  )}
                </div>

                <Button
                  size="sm"
                  variant="secondary"
                  disabled={page >= totalPages}
                  onClick={() => goToPage(page + 1)}
                >
                  Next →
                </Button>
                <Button
                  size="sm"
                  variant="secondary"
                  disabled={page >= totalPages}
                  onClick={() => goToPage(totalPages)}
                  title="Last page"
                >
                  »
                </Button>
              </div>

              <form onSubmit={handleJumpSubmit} className={styles.jumpForm}>
                <span>Go to page:</span>
                <input
                  type="number"
                  min={1}
                  max={totalPages}
                  placeholder={String(page)}
                  value={inputPage}
                  onChange={e => setInputPage(e.target.value)}
                  className={styles.jumpInput}
                />
                <Button type="submit" size="sm" variant="secondary">Go</Button>
              </form>
            </div>
          )}
        </>
      )}
    </div>
  );
}


