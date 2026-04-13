import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
} from "recharts";

const COLORS = ["#42145F", "#6B4C8A", "#0F7B3F", "#C4314B", "#D4760A", "#3B82F6"];
const TIP = {
  backgroundColor: "#fff", border: "1px solid #E5E7EB",
  borderRadius: 6, color: "#1A1A2E", fontSize: 12,
};
const AXIS = { fill: "#6B7280", fontSize: 11 };

export default function AnimatedBar({ data, config }) {
  if (!data?.length || !config?.x || !config?.y) return null;

  const chartData = data.slice(0, 30);
  const groupBy = config.group_by;

  // Find max value for highlighting
  const maxVal = Math.max(...chartData.map((d) => d[config.y] ?? 0));

  return (
    <div className="chart-area">
      <ResponsiveContainer width="100%" height={280}>
        <BarChart data={chartData} margin={{ top: 8, right: 8, bottom: 32, left: 0 }}>
          <XAxis
            dataKey={config.x}
            tick={AXIS}
            angle={chartData.length > 8 ? -35 : 0}
            textAnchor={chartData.length > 8 ? "end" : "middle"}
            interval={0}
            tickFormatter={(v) => String(v).slice(0, 12)}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            tick={AXIS}
            tickFormatter={(v) => v.toLocaleString()}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip contentStyle={TIP} cursor={{ fill: "rgba(66,20,95,0.04)" }} />
          <Bar
            dataKey={config.y}
            radius={[4, 4, 0, 0]}
            maxBarSize={48}
            animationDuration={600}
          >
            {chartData.map((entry, i) => (
              <Cell
                key={i}
                fill={entry[config.y] === maxVal ? COLORS[0] : COLORS[1]}
                style={{ animationDelay: `${i * 100}ms` }}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
