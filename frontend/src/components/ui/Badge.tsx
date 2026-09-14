import styles from './Badge.module.css';
import { CSSProperties } from 'react';

type BadgeVariant = 'default' | 'success' | 'warning' | 'danger' | 'info' | 'accent';

interface BadgeProps {
  children: React.ReactNode;
  variant?: BadgeVariant;
  className?: string;
  style?: CSSProperties;
}

export function Badge({ children, variant = 'default', className, style }: BadgeProps) {
  return <span className={[styles.badge, styles[variant], className].filter(Boolean).join(' ')} style={style}>{children}</span>;
}

export function StatusBadge({ status }: { status: string }) {
  const map: Record<string, BadgeVariant> = {
    active: 'success', trialing: 'info', past_due: 'warning',
    canceled: 'danger', free: 'default', error: 'danger', paused: 'warning',
    paused_over_limit: 'warning', running: 'accent', completed: 'success', failed: 'danger', pending: 'default',
  };
  const label = status === 'paused_over_limit' ? 'Paused (Plan Limit)' : status.replace(/_/g, ' ');
  return <Badge variant={map[status] ?? 'default'}>{label}</Badge>;
}
