/**
 * Format a number for display in KPI cards and chart axes.
 * Used consistently everywhere a number is shown to a user.
 */
export function formatNumber(num) {
  if (num === null || num === undefined) return "—";
  if (typeof num !== "number") return String(num);
  if (Math.abs(num) >= 1_000_000) return (num / 1_000_000).toFixed(1) + "M";
  if (Math.abs(num) >= 1_000) return (num / 1_000).toFixed(1) + "K";
  if (Number.isInteger(num)) return num.toLocaleString();
  return num.toFixed(1);
}
