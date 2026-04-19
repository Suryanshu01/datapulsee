import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer,
} from "recharts";

const TIP = {
  backgroundColor: "var(--surface-2)", border: "1px solid var(--border)",
  borderRadius: 6, color: "var(--text)", fontSize: 12,
};
const AXIS = { fill: "var(--text-3)", fontSize: 11 };

export default function AnimatedLine({ data, config }) {
  if (!data?.length || !config?.x || !config?.y) return null;

  const chartData = data.slice(0, 50);
  const interval = Math.max(0, Math.floor(chartData.length / 8));

  return (
    <div className="chart-area">
      <ResponsiveContainer width="100%" height={280}>
        <AreaChart data={chartData} margin={{ top: 8, right: 8, bottom: 32, left: 0 }}>
          <XAxis
            dataKey={config.x}
            tick={AXIS}
            interval={interval}
            tickFormatter={(v) => String(v).slice(0, 10)}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            tick={AXIS}
            tickFormatter={(v) => v.toLocaleString()}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip contentStyle={TIP} />
          <Area
            type="monotone"
            dataKey={config.y}
            stroke="var(--primary)"
            strokeWidth={2.5}
            fill="var(--primary-bg)"
            dot={false}
            activeDot={{ r: 5, fill: "var(--primary)", strokeWidth: 0 }}
            animationDuration={1200}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
