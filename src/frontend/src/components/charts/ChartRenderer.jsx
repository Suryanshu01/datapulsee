import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
  AreaChart, Area, PieChart, Pie, Legend, ReferenceLine,
} from "recharts";
import { formatNumber } from "../../utils/formatNumber";
import KPIRow from "./KPIRow";

// Gradient from darkest (rank 1) to lightest — visual hierarchy for rankings
const BAR_COLORS = ["#42145F", "#5A2D7A", "#6B4C8A", "#7D6B99", "#9E8FB3", "#B8ACC6", "#D1C9D9"];
const DONUT_COLORS = ["#42145F", "#6B4C8A", "#0F7B3F", "#D4760A", "#3B82F6", "#C4314B", "#8B5CF6", "#059669"];

const TIP = {
  backgroundColor: "#fff",
  border: "1px solid #E5E7EB",
  borderRadius: 6,
  color: "#1A1A2E",
  fontSize: 12,
  boxShadow: "0 2px 8px rgba(0,0,0,0.08)",
};
const AXIS = { fontSize: 11, fill: "#6B7280" };

/** Deduplicate rows by x-axis key, summing numeric values for duplicates. */
function deduplicateData(data, xKey) {
  if (!data || !xKey) return data || [];
  const map = new Map();
  data.forEach((row) => {
    const key = row[xKey];
    if (map.has(key)) {
      const existing = map.get(key);
      Object.keys(row).forEach((k) => {
        if (k !== xKey && typeof row[k] === "number") {
          existing[k] = (existing[k] || 0) + row[k];
        }
      });
    } else {
      map.set(key, { ...row });
    }
  });
  return Array.from(map.values());
}

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div style={TIP}>
      <div style={{ fontWeight: 600, marginBottom: 4 }}>{label}</div>
      {payload.map((p) => (
        <div key={p.dataKey} style={{ color: p.color || "#42145F" }}>
          {p.name}: {formatNumber(p.value)}
        </div>
      ))}
    </div>
  );
}

export default function ChartRenderer({ data, chartType, config, kpis }) {
  if (!data?.length && !kpis?.length) return null;

  const xKey = config?.x;
  const yKey = config?.y;
  const raw = data?.slice(0, 50) || [];
  const deduplicated = deduplicateData(raw, xKey);

  // kpi_only — just show KPI row, no chart
  if (chartType === "kpi_only" || chartType === "kpi") {
    return kpis?.length ? <KPIRow kpis={kpis} /> : null;
  }

  if (!xKey || !yKey) return null;

  if (chartType === "bar" || chartType === "grouped_bar") {
    const barValues = deduplicated.map((d) => d[yKey]).filter((v) => typeof v === "number");
    const barAvg = barValues.length > 0
      ? barValues.reduce((a, b) => a + b, 0) / barValues.length
      : 0;

    return (
      <div className="chart-container">
        <ResponsiveContainer width="100%" height={280}>
          <BarChart data={deduplicated} margin={{ top: 8, right: 64, bottom: 36, left: 0 }}>
            <XAxis
              dataKey={xKey}
              tick={AXIS}
              angle={deduplicated.length > 7 ? -35 : 0}
              textAnchor={deduplicated.length > 7 ? "end" : "middle"}
              interval={0}
              tickFormatter={(v) => String(v).slice(0, 14)}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              tick={AXIS}
              axisLine={false}
              tickLine={false}
              width={60}
              tickFormatter={formatNumber}
            />
            <Tooltip content={<CustomTooltip />} cursor={{ fill: "rgba(66,20,95,0.04)" }} />
            <Bar dataKey={yKey} radius={[4, 4, 0, 0]} animationDuration={800} animationEasing="ease-out">
              {deduplicated.map((_, i) => (
                <Cell key={i} fill={BAR_COLORS[Math.min(i, BAR_COLORS.length - 1)]} />
              ))}
            </Bar>
            {barValues.length > 1 && (
              <ReferenceLine
                y={barAvg}
                stroke="#9CA3AF"
                strokeDasharray="4 4"
                strokeWidth={1}
                label={{ value: `Avg: ${formatNumber(barAvg)}`, position: "right", fontSize: 10, fill: "#9CA3AF" }}
              />
            )}
          </BarChart>
        </ResponsiveContainer>
      </div>
    );
  }

  if (chartType === "horizontal_bar") {
    return (
      <div className="chart-container">
        <ResponsiveContainer width="100%" height={Math.max(200, deduplicated.length * 36)}>
          <BarChart
            data={deduplicated}
            layout="vertical"
            margin={{ top: 4, right: 60, bottom: 4, left: 80 }}
          >
            <XAxis type="number" tick={AXIS} axisLine={false} tickLine={false} tickFormatter={formatNumber} />
            <YAxis
              type="category"
              dataKey={xKey}
              tick={AXIS}
              axisLine={false}
              tickLine={false}
              width={75}
              tickFormatter={(v) => String(v).slice(0, 16)}
            />
            <Tooltip content={<CustomTooltip />} cursor={{ fill: "rgba(66,20,95,0.04)" }} />
            <Bar dataKey={yKey} radius={[0, 4, 4, 0]} animationDuration={800} animationEasing="ease-out">
              {deduplicated.map((_, i) => (
                <Cell key={i} fill={BAR_COLORS[Math.min(i, BAR_COLORS.length - 1)]} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    );
  }

  if (chartType === "line" || chartType === "area") {
    const lineValues = deduplicated.map((d) => d[yKey]).filter((v) => typeof v === "number");
    const maxVal = lineValues.length > 0 ? Math.max(...lineValues) : null;
    const minVal = lineValues.length > 0 ? Math.min(...lineValues) : null;
    const maxPoint = maxVal !== null ? deduplicated.find((d) => d[yKey] === maxVal) : null;
    const minPoint = minVal !== null ? deduplicated.find((d) => d[yKey] === minVal) : null;

    return (
      <div className="chart-container">
        <ResponsiveContainer width="100%" height={280}>
          <AreaChart data={deduplicated} margin={{ top: 20, right: 8, bottom: 36, left: 0 }}>
            <defs>
              <linearGradient id="areaFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#42145F" stopOpacity={0.2} />
                <stop offset="100%" stopColor="#42145F" stopOpacity={0} />
              </linearGradient>
            </defs>
            <XAxis
              dataKey={xKey}
              tick={AXIS}
              interval={Math.max(0, Math.floor(deduplicated.length / 8))}
              tickFormatter={(v) => String(v).slice(0, 10)}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              tick={AXIS}
              axisLine={false}
              tickLine={false}
              width={60}
              tickFormatter={formatNumber}
            />
            <Tooltip content={<CustomTooltip />} />
            <Area
              type="monotone"
              dataKey={yKey}
              stroke="#42145F"
              strokeWidth={2.5}
              fill="url(#areaFill)"
              activeDot={{ r: 5, fill: "#42145F", strokeWidth: 0 }}
              animationDuration={1200}
              animationEasing="ease-out"
              dot={(props) => {
                const { cx, cy, payload } = props;
                const isMax = maxPoint && payload === maxPoint;
                const isMin = minPoint && payload === minPoint;
                if (!isMax && !isMin) return null;
                const color = isMax ? "#0F7B3F" : "#C4314B";
                const label = isMax ? "▲ High" : "▼ Low";
                return (
                  <g key={`${cx}-${cy}`}>
                    <circle cx={cx} cy={cy} r={5} fill={color} stroke="white" strokeWidth={2} />
                    <text x={cx} y={cy - 12} textAnchor="middle" fontSize={10} fill={color} fontWeight={600}>
                      {label}
                    </text>
                  </g>
                );
              }}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    );
  }

  if (chartType === "donut" || chartType === "pie") {
    return (
      <div className="chart-container">
        <ResponsiveContainer width="100%" height={280}>
          <PieChart>
            <Pie
              data={deduplicated}
              dataKey={yKey}
              nameKey={xKey}
              cx="50%"
              cy="50%"
              innerRadius={55}
              outerRadius={100}
              paddingAngle={2}
              animationDuration={800}
              animationEasing="ease-out"
            >
              {deduplicated.map((_, i) => (
                <Cell key={i} fill={DONUT_COLORS[i % DONUT_COLORS.length]} />
              ))}
            </Pie>
            <Tooltip content={<CustomTooltip />} />
            <Legend wrapperStyle={{ fontSize: 12, color: "#6B7280" }} />
          </PieChart>
        </ResponsiveContainer>
      </div>
    );
  }

  // table / unknown — caller handles inline
  return null;
}
