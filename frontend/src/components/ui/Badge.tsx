import styles from './Badge.module.css';

type BadgeVariant = 'default' | 'success' | 'warning' | 'danger' | 'info' | 'accent';

interface BadgeProps {
  children: React.ReactNode;
  variant?: BadgeVariant;
}

export function Badge({ children, variant = 'default' }: BadgeProps) {
  return <span className={[styles.badge, styles[variant]].join(' ')}>{children}</span>;
}

export function StatusBadge({ status }: { status: string }) {
  const map: Record<string, BadgeVariant> = {
    active: 'success', trialing: 'info', past_due: 'warning',
    canceled: 'danger', free: 'default', error: 'danger', paused: 'warning',
    running: 'accent', completed: 'success', failed: 'danger', pending: 'default',
  };
  return <Badge variant={map[status] ?? 'default'}>{status.replace(/_/g, ' ')}</Badge>;
}
