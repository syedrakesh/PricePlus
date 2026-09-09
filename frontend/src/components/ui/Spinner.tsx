import styles from './Spinner.module.css';

export function Spinner({ size = 24 }: { size?: number }) {
  return (
    <div className={styles.spinner} style={{ width: size, height: size }} aria-label="Loading" role="status" />
  );
}

export function PageLoader() {
  return (
    <div className={styles.page}>
      <Spinner size={40} />
      <span className={styles.text}>Loading…</span>
    </div>
  );
}

export function EmptyState({ icon, title, description, action }: {
  icon?: string; title: string; description?: string; action?: React.ReactNode;
}) {
  return (
    <div className={styles.empty}>
      {icon && <span className={styles.emptyIcon}>{icon}</span>}
      <h3 className={styles.emptyTitle}>{title}</h3>
      {description && <p className={styles.emptyDesc}>{description}</p>}
      {action && <div className={styles.emptyAction}>{action}</div>}
    </div>
  );
}
