'use client';

import { Suspense, useEffect, useState } from 'react';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import { isLoggedIn } from '@/lib/auth';
import { AuthProvider, useAuth } from '@/context/AuthContext';
import { Sidebar } from '@/components/ui/Sidebar';
import { PageLoader } from '@/components/ui/Spinner';
import { OverQuotaBanner } from '@/components/ui/OverQuotaBanner';
import styles from './DashboardLayout.module.css';

function DashboardShellContent({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const sessionId = searchParams.get('session_id');

  const { user, loading, isAdmin } = useAuth();
  const [mounted, setMounted] = useState(false);

  const isAdminUser = user && (isAdmin || user.is_superuser || user.role_slug === 'admin');
  const isCustomer = user && !isAdminUser;

  useEffect(() => {
    setMounted(true);
    if (!isLoggedIn() && !sessionId) {
      router.replace('/login');
      return;
    }
    if (!loading && user) {
      if (isAdminUser && pathname === '/onboarding') {
        router.replace('/');
      } else if (isCustomer && !user.onboarding_completed && pathname !== '/onboarding') {
        router.replace('/onboarding');
      }
    }
  }, [router, user, loading, pathname, sessionId, isCustomer, isAdminUser]);

  if (!mounted || loading) {
    return <PageLoader />;
  }

  if (isAdminUser && pathname === '/onboarding') {
    return <PageLoader />;
  }

  if (isCustomer && !user.onboarding_completed && pathname !== '/onboarding') {
    return <PageLoader />;
  }

  return (
    <div className={styles.shell}>
      <Sidebar />
      <main className={styles.main}>
        <OverQuotaBanner />
        {children}
      </main>
    </div>
  );
}

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthProvider>
      <Suspense fallback={<PageLoader />}>
        <DashboardShellContent>{children}</DashboardShellContent>
      </Suspense>
    </AuthProvider>
  );
}
