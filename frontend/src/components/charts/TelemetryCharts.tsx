'use client';

import React from 'react';
import {
  AreaChart, Area, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend
} from 'recharts';
import styles from './TelemetryCharts.module.css';

export interface TelemetryEvent {
  id: string;
  timestamp: string;
  action: string;
  product_title: string;
  store_domain: string;
  price: number | null;
  status_code: number;
  latency_ms: number;
  details: string;
}

interface TelemetryChartsProps {
  events: TelemetryEvent[];
}

const ACTION_COLORS: Record<string, string> = {
  PULLED: '#6366f1',
  DISCOVERED: '#3b82f6',
  DISPATCHED: '#10b981',
  ERROR: '#ef4444',
};

const CustomTooltip = ({ active, payload }: { active?: boolean; payload?: Array<{ payload: TelemetryEvent }> }) => {
  if (!active || !payload?.length) return null;
  const evt = payload[0].payload;

  return (
    <div className={styles.tooltip}>
      <div className={styles.tooltipTime}>
        ⏱ {new Date(evt.timestamp).toLocaleTimeString()}
      </div>
      <div className={styles.tooltipTitle}>{evt.product_title}</div>
      <div className={styles.tooltipMeta}>
        <span>Domain: <strong>{evt.store_domain}</strong></span>
        <span>Action: <strong style={{ color: ACTION_COLORS[evt.action] || '#8b5cf6' }}>{evt.action}</strong></span>
        {evt.latency_ms > 0 && (
          <span>Latency: <strong>{evt.latency_ms}ms</strong></span>
        )}
        {evt.price !== null && evt.price !== undefined && (
          <span>Price: <strong>${evt.price.toFixed(2)}</strong></span>
        )}
      </div>
    </div>
  );
};

export function TelemetryCharts({ events }: TelemetryChartsProps) {
  if (!events || events.length === 0) {
    return (
      <div className={styles.emptyCharts}>
        <span>📊</span>
        <p>Telemetry graphs will populate as live background workers execute tasks.</p>
      </div>
    );
  }

  // Latency chronological series (oldest to newest)
  const latencyData = [...events]
    .reverse()
    .map(e => ({
      ...e,
      timeFormatted: new Date(e.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
      latency: e.latency_ms || 0,
    }));

  // Action count aggregation for Pie Chart
  const actionCounts: Record<string, number> = {};
  events.forEach(e => {
    actionCounts[e.action] = (actionCounts[e.action] || 0) + 1;
  });

  const pieData = Object.entries(actionCounts).map(([name, value]) => ({
    name,
    value,
    color: ACTION_COLORS[name] || '#8b5cf6',
  }));

  // Calculate Avg Latency & Success Rate
  const totalEvents = events.length;
  const validLatencies = events.filter(e => e.latency_ms > 0).map(e => e.latency_ms);
  const avgLatency = validLatencies.length ? Math.round(validLatencies.reduce((a, b) => a + b, 0) / validLatencies.length) : 0;
  const successCount = events.filter(e => e.status_code >= 200 && e.status_code < 300).length;
  const successRate = totalEvents ? Math.round((successCount / totalEvents) * 100) : 100;

  return (
    <div className={styles.container}>
      {/* Metric Visual Cards */}
      <div className={styles.visualStatsRow}>
        <div className={styles.visualStatCard}>
          <div className={styles.visualStatHeader}>
            <span>⚡ Avg Request Latency</span>
            <span className={styles.visualStatBadge}>{avgLatency} ms</span>
          </div>
          <div className={styles.sparklineBar}>
            <div className={styles.sparklineFill} style={{ width: `${Math.min(100, (avgLatency / 1000) * 100)}%` }} />
          </div>
        </div>

        <div className={styles.visualStatCard}>
          <div className={styles.visualStatHeader}>
            <span>✅ Worker Success Rate</span>
            <span className={styles.visualStatBadge} style={{ background: 'rgba(16, 185, 129, 0.15)', color: '#10b981' }}>
              {successRate}%
            </span>
          </div>
          <div className={styles.sparklineBar}>
            <div className={styles.sparklineFill} style={{ width: `${successRate}%`, background: '#10b981' }} />
          </div>
        </div>

        <div className={styles.visualStatCard}>
          <div className={styles.visualStatHeader}>
            <span>📊 Ring Buffer Load</span>
            <span className={styles.visualStatBadge} style={{ background: 'rgba(99, 102, 241, 0.15)', color: '#6366f1' }}>
              {events.length} / 50 events
            </span>
          </div>
          <div className={styles.sparklineBar}>
            <div className={styles.sparklineFill} style={{ width: `${(events.length / 50) * 100}%`, background: '#6366f1' }} />
          </div>
        </div>
      </div>

      {/* Two Column Visual Charts */}
      <div className={styles.chartsGrid}>
        {/* Latency Trend Area Chart */}
        <div className={styles.chartBox}>
          <div className={styles.chartHeader}>
            <div>
              <h4 className={styles.chartTitle}>HTTP & Worker Request Latency Stream</h4>
              <p className={styles.chartSub}>Real-time execution latency across recent worker cycles (ms)</p>
            </div>
          </div>
          <div className={styles.chartCanvas}>
            <ResponsiveContainer width="100%" height={200}>
              <AreaChart data={latencyData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <defs>
                  <linearGradient id="latencyGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#6366f1" stopOpacity={0.4} />
                    <stop offset="95%" stopColor="#6366f1" stopOpacity={0.0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" vertical={false} />
                <XAxis
                  dataKey="timeFormatted"
                  tick={{ fill: '#64748b', fontSize: 10 }}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  tick={{ fill: '#64748b', fontSize: 10 }}
                  axisLine={false}
                  tickLine={false}
                  unit="ms"
                />
                <Tooltip content={<CustomTooltip />} />
                <Area
                  type="monotone"
                  dataKey="latency"
                  stroke="#6366f1"
                  strokeWidth={2}
                  fillOpacity={1}
                  fill="url(#latencyGradient)"
                  activeDot={{ r: 5, fill: '#6366f1', stroke: '#080c18', strokeWidth: 2 }}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Action Type Donut Chart */}
        <div className={styles.chartBox}>
          <div className={styles.chartHeader}>
            <div>
              <h4 className={styles.chartTitle}>Telemetry Action Breakdown</h4>
              <p className={styles.chartSub}>Proportion of worker tasks by event classification</p>
            </div>
          </div>
          <div className={styles.chartCanvas}>
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie
                  data={pieData}
                  innerRadius={50}
                  outerRadius={75}
                  paddingAngle={4}
                  dataKey="value"
                >
                  {pieData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} stroke="rgba(15, 20, 32, 0.8)" strokeWidth={2} />
                  ))}
                </Pie>
                <Tooltip
                  content={({ active, payload }) => {
                    if (!active || !payload?.length) return null;
                    const item = payload[0];
                    return (
                      <div className={styles.tooltip}>
                        <strong>{item.name}</strong>: {item.value} events
                      </div>
                    );
                  }}
                />
                <Legend
                  verticalAlign="bottom"
                  height={36}
                  formatter={(value: string) => (
                    <span style={{ color: 'var(--color-text-2)', fontSize: '11px', fontWeight: 600 }}>
                      {value}
                    </span>
                  )}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </div>
  );
}
