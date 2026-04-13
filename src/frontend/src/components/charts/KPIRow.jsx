import KPICard from "./KPICard";

export default function KPIRow({ kpis, scrollable = false }) {
  if (!kpis || kpis.length === 0) return null;

  return (
    <div
      className="kpi-row"
      style={scrollable ? { overflowX: "auto", flexWrap: "nowrap" } : {}}
    >
      {kpis.slice(0, scrollable ? kpis.length : 4).map((kpi, i) => (
        <KPICard
          key={i}
          label={kpi.label}
          value={kpi.value}
          formatted={kpi.formatted}
          delta={kpi.delta}
          deltaLabel={kpi.delta_label}
          sparklineData={kpi.sparkline_data}
          minVal={kpi.min}
          maxVal={kpi.max}
        />
      ))}
    </div>
  );
}
