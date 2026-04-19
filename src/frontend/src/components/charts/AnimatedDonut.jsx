import {
  PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend,
} from "recharts";

const COLORS = ["#42145F", "#6B4C8A", "#0F7B3F", "#D4760A", "#3B82F6", "#C4314B", "#8B5CF6", "#059669"];
const TIP = {
  backgroundColor: "var(--surface-2)", border: "1px solid var(--border)",
  borderRadius: 6, color: "var(--text)", fontSize: 12,
};

export default function AnimatedDonut({ data, config }) {
  if (!data?.length || !config?.x || !config?.y) return null;

  const chartData = data.slice(0, 10);

  // Find largest slice index for slight offset
  let largestIdx = 0;
  let largestVal = 0;
  chartData.forEach((d, i) => {
    const v = typeof d[config.y] === "number" ? d[config.y] : 0;
    if (v > largestVal) { largestVal = v; largestIdx = i; }
  });

  return (
    <div className="chart-area">
      <ResponsiveContainer width="100%" height={280}>
        <PieChart>
          <Pie
            data={chartData}
            dataKey={config.y}
            nameKey={config.x}
            cx="50%"
            cy="50%"
            outerRadius={100}
            innerRadius={45}
            paddingAngle={2}
            animationDuration={800}
            label={({ name, percent }) =>
              `${String(name).slice(0, 10)} ${(percent * 100).toFixed(0)}%`
            }
            labelLine={false}
          >
            {chartData.map((_, i) => (
              <Cell key={i} fill={COLORS[i % COLORS.length]} />
            ))}
          </Pie>
          <Tooltip contentStyle={TIP} />
          <Legend wrapperStyle={{ fontSize: 12, color: "var(--text-3)" }} />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}
