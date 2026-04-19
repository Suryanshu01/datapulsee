import { BarChart, Bar, XAxis, YAxis, Cell, Tooltip, ResponsiveContainer, LabelList } from 'recharts';
import { formatNumber } from '../../utils/formatNumber';

const POSITIVE_COLOR = 'var(--success)';
const NEGATIVE_COLOR = 'var(--danger)';

export default function WaterfallChart({ drivers, comparison }) {
  if (!drivers || !drivers.length) return null;

  const data = drivers.slice(0, 8).map((d) => ({
    name: d.dimension_value,
    value: d.change,
    contribution: d.contribution_pct,
    label: `${formatNumber(d.change)} (${Math.abs(d.contribution_pct)}%)`,
  }));

  return (
    <div style={{ margin: '16px 0' }}>
      {comparison && (
        <div style={{ fontSize: 12, color: 'var(--text-3)', marginBottom: 8 }}>
          Comparing {comparison}
        </div>
      )}
      <ResponsiveContainer width="100%" height={Math.max(180, data.length * 44)}>
        <BarChart data={data} layout="vertical" margin={{ left: 80, right: 100, top: 4, bottom: 4 }}>
          <XAxis type="number" hide />
          <YAxis
            type="category"
            dataKey="name"
            tick={{ fontSize: 13, fill: 'var(--text)' }}
            axisLine={false}
            tickLine={false}
            width={70}
          />
          <Tooltip
            formatter={(v) => formatNumber(v)}
            contentStyle={{
              background: 'var(--surface-2)',
              border: '1px solid var(--border)',
              borderRadius: 6,
              fontSize: 12,
              color: 'var(--text)',
            }}
          />
          <Bar
            dataKey="value"
            radius={[0, 4, 4, 0]}
            animationDuration={800}
            animationEasing="ease-out"
          >
            {data.map((entry, i) => (
              <Cell key={i} fill={entry.value >= 0 ? POSITIVE_COLOR : NEGATIVE_COLOR} />
            ))}
            <LabelList
              dataKey="label"
              position="right"
              style={{ fontSize: 11, fontWeight: 600, fill: 'var(--text, #1A1A2E)' }}
            />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
