import { useState, useEffect } from "react";
import Sparkline from "./Sparkline";
import { formatNumber } from "../../utils/formatNumber";

/**
 * useCountUp — animates a number from 0 to target over 800ms.
 * Uses ease-out cubic so it feels snappy, not mechanical.
 */
function useCountUp(target, duration = 800) {
  const [value, setValue] = useState(0);
  useEffect(() => {
    if (target == null || isNaN(target)) return;
    setValue(0);
    const start = performance.now();
    const animate = (now) => {
      const progress = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setValue(Math.round(target * eased));
      if (progress < 1) requestAnimationFrame(animate);
    };
    requestAnimationFrame(animate);
  }, [target, duration]);
  return value;
}

export default function KPICard({ label, value, formatted, delta, deltaLabel, sparklineData, minVal, maxVal }) {
  const numericValue = typeof value === "number" ? value : parseFloat(value);
  const isNumeric = !isNaN(numericValue);
  const animatedValue = useCountUp(isNumeric ? numericValue : 0);

  // Use formatted string if provided; otherwise format the animated counter
  const displayValue = formatted || (isNumeric ? formatNumber(animatedValue) : String(value ?? "—"));

  const deltaClass = delta > 0 ? "positive" : delta < 0 ? "negative" : "neutral";
  const deltaArrow = delta > 0 ? "↑" : delta < 0 ? "↓" : "→";

  return (
    <div className="kpi-card">
      <div className="kpi-label">{label}</div>
      <div className="kpi-value">{displayValue}</div>
      {delta != null && (
        <div className={`kpi-delta ${deltaClass}`}>
          {deltaArrow} {Math.abs(delta)}%{deltaLabel ? ` ${deltaLabel}` : ""}
        </div>
      )}
      {(minVal != null || maxVal != null) && (
        <div style={{ fontSize: 11, color: "var(--text-3)", marginTop: 4, fontFamily: "var(--font-mono)", letterSpacing: "0.04em" }}>
          {minVal != null && `Min ${formatNumber(minVal)}`}
          {minVal != null && maxVal != null && " · "}
          {maxVal != null && `Max ${formatNumber(maxVal)}`}
        </div>
      )}
      {sparklineData && sparklineData.length > 1 && (
        <div className="sparkline-wrap">
          <Sparkline data={sparklineData} />
        </div>
      )}
    </div>
  );
}
