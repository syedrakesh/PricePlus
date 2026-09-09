'use client';

import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine, Dot,
} from 'recharts';
import type { TimelineEntry } from '@/lib/api';
import styles from './PriceChart.module.css';

interface PriceChartProps {
  entries: TimelineEntry[];
  currency?: string;
}

function formatDate(isoStr: string) {
  const d = new Date(isoStr);
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

function formatPrice(val: number) {
  return `$${val.toFixed(2)}`;
}

const CustomDot = (props: { cx?: number; cy?: number; payload?: TimelineEntry }) => {
  const { cx, cy, payload } = props;
  if (!payload || payload.kind !== 'change' || cx === undefined || cy === undefined) return null;

  const color = payload.change_type === 'price_decrease' ? '#10b981'
    : payload.change_type === 'price_increase' ? '#ef4444'
    : payload.change_type === 'became_unavailable' ? '#f59e0b'
    : '#3b82f6';

  return <circle cx={cx} cy={cy} r={6} fill={color} stroke="#080c18" strokeWidth={2} />;
};

const CustomTooltip = ({ active, payload }: { active?: boolean; payload?: Array<{ payload: TimelineEntry }> }) => {
  if (!active || !payload?.length) return null;
  const entry = payload[0].payload;

  return (
    <div className={styles.tooltip}>
      <div className={styles.tooltipTime}>{formatDate(entry.timestamp)}</div>
      {entry.price !== null && (
        <div className={styles.tooltipPrice}>{formatPrice(entry.price)}</div>
      )}
      {entry.kind === 'change' && entry.change_type && (
        <div className={styles.tooltipChange}>{entry.change_type.replace(/_/g, ' ')}</div>
      )}
      {entry.pct_change !== null && (
        <div className={styles.tooltipPct} style={{ color: entry.pct_change < 0 ? '#10b981' : '#ef4444' }}>
          {entry.pct_change > 0 ? '+' : ''}{entry.pct_change.toFixed(1)}%
        </div>
      )}
    </div>
  );
};

export function PriceChart({ entries, currency = 'USD' }: PriceChartProps) {
  // Reverse to chronological order for chart (oldest → newest)
  const chartData = [...entries].reverse().filter(e => e.price !== null);

  if (chartData.length === 0) {
    return (
      <div className={styles.empty}>
        <span>📊</span>
        <p>No price data yet</p>
      </div>
    );
  }

  const prices = chartData.map(e => e.price as number);
  const minPrice = Math.min(...prices);
  const maxPrice = Math.max(...prices);
  const padding = (maxPrice - minPrice) * 0.1 || 1;

  return (
    <div className={styles.chart}>
      <ResponsiveContainer width="100%" height={280}>
        <LineChart data={chartData} margin={{ top: 8, right: 24, left: 8, bottom: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1f2a47" vertical={false} />
          <XAxis
            dataKey="timestamp"
            tickFormatter={(v) => {
              const d = new Date(v);
              return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
            }}
            tick={{ fill: '#64748b', fontSize: 11 }}
            axisLine={false}
            tickLine={false}
            interval="preserveStartEnd"
          />
          <YAxis
            domain={[minPrice - padding, maxPrice + padding]}
            tickFormatter={formatPrice}
            tick={{ fill: '#64748b', fontSize: 11 }}
            axisLine={false}
            tickLine={false}
            width={68}
          />
          <Tooltip content={<CustomTooltip />} />
          <Line
            type="monotone"
            dataKey="price"
            stroke="#6366f1"
            strokeWidth={2}
            dot={<CustomDot />}
            activeDot={{ r: 5, fill: '#6366f1', stroke: '#080c18', strokeWidth: 2 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
