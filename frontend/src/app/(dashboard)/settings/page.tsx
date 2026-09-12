'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { PageLoader } from '@/components/ui/Spinner';

export default function SettingsPage() {
  const router = useRouter();

  useEffect(() => {
    router.replace('/settings/discovery');
  }, [router]);

  return <PageLoader />;
}
