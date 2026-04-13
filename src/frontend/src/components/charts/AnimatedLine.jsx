import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer,
} from "recharts";

const TIP = {
  backgroundColor: "#fff", border: "1px solid #E5E7EB",
  borderRadius: 6, color: "#1A1A2E", fontSize: 12,
};
const AXIS = { fill: "#6B7280", fontSize: 11 };

export default function AnimatedLine({ data, config }) {
  if (!data?.length || !config?.x || !config?.y) return null;

  const chartData = data.slice(0, 50);
  const interval = Math.max(0, Math.floor(chartData.length / 8));

  return (
    <div className="chart-area">
      <ResponsiveContainer width="100%" height={280}>
        <AreaChart data={chartData} margin={{ top: 8, right: 8, bottom: 32, left: 0 }}>
          <defs>
            <linearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#42145F" stopOpacity={0.15} />
              <stop offset="100%" stopColor="#42145F" stopOpacity={0} />
            </linearGradient>
          </defs>
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
            stroke="#42145F"
            strokeWidth={2.5}
            fill="url(#areaGrad)"
            dot={false}
            activeDot={{ r: 5, fill: "#42145F", strokeWidth: 0 }}
            animationDuration={1200}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
