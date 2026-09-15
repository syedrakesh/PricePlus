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

  const { user, loading } = useAuth();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    if (!isLoggedIn() && !sessionId) {
      router.replace('/login');
      return;
    }
    if (!loading && user && !user.onboarding_completed && pathname !== '/onboarding') {
      router.replace('/onboarding');
    }
  }, [router, user, loading, pathname, sessionId]);

  if (!mounted || loading) {
    return <PageLoader />;
  }

  if (user && !user.onboarding_completed && pathname !== '/onboarding') {
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
