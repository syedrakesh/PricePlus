'use client';

import { useAuth } from '@/context/AuthContext';
import { PageLoader } from '@/components/ui/Spinner';
import { Card, CardHeader, CardBody } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import Link from 'next/link';

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const { user, loading, isAdmin } = useAuth();

  if (loading) {
    return <PageLoader />;
  }

  if (!user || !isAdmin) {
    return (
      <div style={{ padding: '3rem', maxWidth: '600px', margin: '4rem auto' }}>
        <div style={{ border: '1px solid var(--color-danger, #ef4444)', borderRadius: '12px' }}>
          <Card>
            <CardHeader>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                <span style={{ fontSize: '1.5rem' }}>🚫</span>
                <h2 style={{ fontSize: '1.25rem', fontWeight: 600 }}>403 - Access Denied</h2>
              </div>
            </CardHeader>
            <CardBody>
              <p style={{ color: 'var(--color-text-2)', marginBottom: '1.5rem' }}>
                You do not have administrative privileges or the <code>access_admin</code> permission required to view this area.
              </p>
              <Link href="/">
                <Button variant="secondary">Return to Dashboard</Button>
              </Link>
            </CardBody>
          </Card>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
