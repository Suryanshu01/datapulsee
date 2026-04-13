import { useMemo } from "react";

/**
 * Mini SVG sparkline with draw animation.
 * 20px tall, full width, single color, no axes.
 */
export default function Sparkline({ data, width = 100, height = 20, color = "#42145F" }) {
  const path = useMemo(() => {
    if (!data || data.length < 2) return "";
    const min = Math.min(...data);
    const max = Math.max(...data);
    const range = max - min || 1;
    const step = width / (data.length - 1);

    return data
      .map((v, i) => {
        const x = i * step;
        const y = height - ((v - min) / range) * (height - 2) - 1;
        return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
      })
      .join(" ");
  }, [data, width, height]);

  if (!path) return null;

  return (
    <svg width="100%" height={height} viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none">
      <path d={path} className="sparkline-path" style={{ stroke: color }} />
    </svg>
  );
}
