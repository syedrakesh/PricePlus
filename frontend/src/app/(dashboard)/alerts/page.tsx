'use client';

import useSWR from 'swr';
import { alertsApi } from '@/lib/api';
import { Card, CardHeader, CardBody } from '@/components/ui/Card';
import { Badge, StatusBadge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { EmptyState, PageLoader } from '@/components/ui/Spinner';
import styles from './page.module.css';

export default function AlertsPage() {
  const { data: rules, isLoading: rulesLoading, mutate: mutateRules } = useSWR('alert-rules', () => alertsApi.listRules());
  const { data: alerts, isLoading: alertsLoading } = useSWR('alerts', () => alertsApi.listAlerts());

  async function handleToggle(id: string) {
    await alertsApi.toggleRule(id);
    mutateRules();
  }

  async function handleDelete(id: string) {
    if (!confirm('Delete this alert rule?')) return;
    await alertsApi.deleteRule(id);
    mutateRules();
  }

  const conditionLabel: Record<string, string> = {
    any_change: 'Any change',
    price_drop: 'Price drops',
    price_rise: 'Price rises',
    price_drop_pct: 'Price drops by %',
    price_rise_pct: 'Price rises by %',
    out_of_stock: 'Goes out of stock',
    back_in_stock: 'Comes back in stock',
  };

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <div>
          <h1>Alerts</h1>
          <p>Your alert rules and notification history</p>
        </div>
      </div>

      {/* Alert Rules */}
      <Card>
        <CardHeader>
          <h3>Alert Rules</h3>
          <Badge variant="accent">{rules?.total ?? 0}</Badge>
        </CardHeader>
        {rulesLoading ? (
          <PageLoader />
        ) : !rules?.rules.length ? (
          <EmptyState
            icon="🔔"
            title="No alert rules"
            description="Alert rules are created automatically when you track products and set conditions. Coming from the product tracking page."
          />
        ) : (
          <div className={styles.ruleList}>
            {rules.rules.map(rule => (
              <div key={rule.id} className={styles.ruleRow}>
                <div className={styles.ruleCondition}>
                  <span className={styles.ruleLabel}>
                    {conditionLabel[rule.condition_type] ?? rule.condition_type}
                  </span>
                  {rule.threshold_pct !== null && (
                    <span className={styles.ruleThreshold}>by ≥{rule.threshold_pct}%</span>
                  )}
                  {rule.threshold_price !== null && (
                    <span className={styles.ruleThreshold}>below ${rule.threshold_price}</span>
                  )}
                </div>
                <div className={styles.ruleMeta}>
                  <Badge variant="default">{rule.channel}</Badge>
                  <StatusBadge status={rule.is_enabled ? 'active' : 'paused'} />
                  {rule.last_triggered_at && (
                    <span className={styles.ruleTriggered}>
                      Last: {new Date(rule.last_triggered_at).toLocaleDateString()}
                    </span>
                  )}
                </div>
                <div className={styles.ruleActions}>
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => handleToggle(rule.id)}
                  >
                    {rule.is_enabled ? 'Pause' : 'Enable'}
                  </Button>
                  <Button size="sm" variant="danger" onClick={() => handleDelete(rule.id)}>
                    Delete
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* Fired alerts */}
      <Card>
        <CardHeader>
          <h3>Notification History</h3>
          <Badge variant="default">{alerts?.total ?? 0}</Badge>
        </CardHeader>
        {alertsLoading ? (
          <PageLoader />
        ) : !alerts?.alerts.length ? (
          <EmptyState icon="📭" title="No alerts fired yet" description="Alerts will appear here when price changes trigger your rules." />
        ) : (
          <div className={styles.alertList}>
            {alerts.alerts.map(alert => (
              <div key={alert.id} className={styles.alertRow}>
                <span className={styles.alertIcon}>{alert.delivered ? '✅' : '⏳'}</span>
                <div className={styles.alertInfo}>
                  <span className={styles.alertSummary}>{alert.trigger_summary ?? 'Price change detected'}</span>
                  <span className={styles.alertTime}>{new Date(alert.created_at).toLocaleString()}</span>
                </div>
                <Badge variant="default">{alert.channel}</Badge>
                <StatusBadge status={alert.delivered ? 'active' : 'pending'} />
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
