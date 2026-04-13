import { useState } from "react";

export default function TrustPanel({ message }) {
  const [expanded, setExpanded] = useState(false);

  if (!message?.sql) return null;

  return (
    <div className="trust-panel">
      <h3 className="trust-title">
        <span className="trust-icon">🔍</span> Trust & Transparency
      </h3>

      <div className="trust-section">
        <div className="trust-label">Intent Detected</div>
        <div className="trust-badge">{message.intent || "general"}</div>
      </div>

      <div className="trust-section">
        <div className="trust-label">What this query does</div>
        <p className="trust-text">{message.queryExplanation}</p>
      </div>

      <div className="trust-section">
        <button className="sql-toggle" onClick={() => setExpanded(!expanded)}>
          {expanded ? "▾" : "▸"} SQL Query Used
        </button>
        {expanded && (
          <pre className="sql-block">{message.sql}</pre>
        )}
      </div>

      <div className="trust-section">
        <div className="trust-label">Rows Returned</div>
        <p className="trust-text">{message.totalRows?.toLocaleString()}</p>
      </div>

      <div className="trust-footer">
        <span className="trust-note">All queries run locally on your data via DuckDB. No data leaves your machine.</span>
      </div>
    </div>
  );
}
