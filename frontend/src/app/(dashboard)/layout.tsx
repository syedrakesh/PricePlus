'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { isLoggedIn } from '@/lib/auth';
import { AuthProvider, useAuth } from '@/context/AuthContext';
import { Sidebar } from '@/components/ui/Sidebar';
import { PageLoader } from '@/components/ui/Spinner';
import styles from './DashboardLayout.module.css';

function DashboardShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { loading } = useAuth();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    if (!isLoggedIn()) {
      router.replace('/login');
    }
  }, [router]);

  if (!mounted || loading) {
    return <PageLoader />;
  }

  return (
    <div className={styles.shell}>
      <Sidebar />
      <main className={styles.main}>{children}</main>
    </div>
  );
}

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthProvider>
      <DashboardShell>{children}</DashboardShell>
    </AuthProvider>
  );
}
