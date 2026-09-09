import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: { default: 'PricePlus', template: '%s | PricePlus' },
  description: 'Shopify competitor price monitoring — track prices, get alerts, win on pricing.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
