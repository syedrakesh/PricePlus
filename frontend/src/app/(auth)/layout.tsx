import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: { default: 'Sign in', template: '%s | PricePlus' },
};

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '24px' }}>
      {children}
    </div>
  );
}
