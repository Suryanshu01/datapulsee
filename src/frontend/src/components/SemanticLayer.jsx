import { useState } from "react";

const API = import.meta.env.VITE_API_URL || "";

const TYPE_COLORS = {
  categorical: { color: "#42145F", bg: "rgba(66,20,95,0.06)" },
  temporal:    { color: "#3B82F6", bg: "rgba(59,130,246,0.06)" },
  geographic:  { color: "#0F7B3F", bg: "rgba(15,123,63,0.06)" },
  date:        { color: "#3B82F6", bg: "rgba(59,130,246,0.06)" },
};

export default function SemanticLayer({ semanticLayer, sessionId, onStartChatting }) {
  const [layer, setLayer] = useState(semanticLayer);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState(null);

  const handleSave = async () => {
    setSaving(true);
    setStatus(null);
    try {
      const res = await fetch(`${API}/api/semantic-layer`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, semantic_layer: layer }),
      });
      if (!res.ok) throw new Error();
      setStatus("saved");
      setTimeout(() => setStatus(null), 2500);
    } catch {
      setStatus("error");
      setTimeout(() => setStatus(null), 3000);
    }
    setSaving(false);
  };

  const updateMetric = (i, field, value) => setLayer((p) => {
    const m = [...p.metrics];
    m[i] = { ...m[i], [field]: value };
    return { ...p, metrics: m };
  });

  const updateDimension = (i, value) => setLayer((p) => {
    const d = [...p.dimensions];
    d[i] = { ...d[i], description: value };
    return { ...p, dimensions: d };
  });

  const updateTimeDimension = (i, value) => setLayer((p) => {
    const td = [...(p.time_dimensions || [])];
    td[i] = { ...td[i], description: value };
    return { ...p, time_dimensions: td };
  });

  const saveLabel = status === "saved" ? "Saved" : status === "error" ? "Failed" : saving ? "Saving..." : "Save Changes";

  return (
    <div className="dict-page">
      <div className="dict-topbar">
        <div className="dict-topbar-text">
          <h2>Data Dictionary</h2>
          <p>AI-generated definitions — review and edit to make answers more accurate</p>
        </div>
        <div className="dict-topbar-actions">
          <button
            className="btn btn-ghost"
            onClick={handleSave}
            disabled={saving}
            style={
              status === "error" ? { borderColor: "var(--danger)", color: "var(--danger)" }
              : status === "saved" ? { borderColor: "var(--success)", color: "var(--success)" }
              : {}
            }
          >
            {saveLabel}
          </button>
          {onStartChatting && (
            <button className="btn btn-primary" onClick={onStartChatting}>
              Start Chatting &rarr;
            </button>
          )}
        </div>
      </div>

      <div className="dict-body">
        {/* Summary */}
        {layer?.data_summary && (
          <div className="summary-banner">
            <span className="summary-banner-icon">AI</span>
            <div>
              <div className="summary-banner-title">Dataset Summary</div>
              <div className="summary-banner-text">{layer.data_summary}</div>
            </div>
          </div>
        )}

        {/* Metrics */}
        {layer?.metrics?.length > 0 && (
          <div className="dict-section">
            <div className="dict-section-hd">
              <span className="dict-section-title">Metrics</span>
              <span className="dict-count">{layer.metrics.length}</span>
            </div>
            <div className="dict-grid">
              {layer.metrics.map((m, i) => (
                <div key={i} className="dict-card">
                  <div className="dict-card-top">
                    <span className="dict-card-name">{m.name}</span>
                    {m.expr && <code className="dict-card-sql">{m.expr}</code>}
                    {!m.expr && m.sql && <code className="dict-card-sql">{m.sql}</code>}
                  </div>
                  <label className="dict-field-label">What does this measure?</label>
                  <input
                    className="dict-field-input"
                    value={m.description || m.definition || ""}
                    onChange={(e) => updateMetric(i, m.description !== undefined ? "description" : "definition", e.target.value)}
                    placeholder="Describe what this metric means..."
                  />
                  {m.synonyms?.length > 0 && (
                    <span className="dict-field-src">Synonyms: {m.synonyms.join(", ")}</span>
                  )}
                  <span className="dict-field-src">Column: {m.column}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Dimensions */}
        {layer?.dimensions?.length > 0 && (
          <div className="dict-section">
            <div className="dict-section-hd">
              <span className="dict-section-title">Dimensions</span>
              <span className="dict-count">{layer.dimensions.length}</span>
            </div>
            <div className="dict-grid">
              {layer.dimensions.map((d, i) => {
                const ts = TYPE_COLORS[d.data_type || d.type] || TYPE_COLORS.categorical;
                return (
                  <div key={i} className="dict-card">
                    <div className="dict-card-top">
                      <span className="dict-card-name">{d.name}</span>
                      <span className="dict-type-tag" style={{ color: ts.color, background: ts.bg }}>
                        {d.data_type || d.type}
                      </span>
                    </div>
                    <label className="dict-field-label">What does this represent?</label>
                    <input
                      className="dict-field-input"
                      value={d.description || ""}
                      onChange={(e) => updateDimension(i, e.target.value)}
                      placeholder="Describe what this dimension means..."
                    />
                    {d.sample_values?.length > 0 && (
                      <span className="dict-field-src">Values: {d.sample_values.join(", ")}</span>
                    )}
                    <span className="dict-field-src">Column: {d.column}</span>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Time Dimensions */}
        {layer?.time_dimensions?.length > 0 && (
          <div className="dict-section">
            <div className="dict-section-hd">
              <span className="dict-section-title">Time Dimensions</span>
              <span className="dict-count">{layer.time_dimensions.length}</span>
            </div>
            <div className="dict-grid">
              {layer.time_dimensions.map((td, i) => (
                <div key={i} className="dict-card">
                  <div className="dict-card-top">
                    <span className="dict-card-name">{td.name}</span>
                    <span className="dict-type-tag" style={{
                      color: TYPE_COLORS.temporal.color,
                      background: TYPE_COLORS.temporal.bg,
                    }}>
                      {td.granularity || "temporal"}
                    </span>
                  </div>
                  <label className="dict-field-label">What time period?</label>
                  <input
                    className="dict-field-input"
                    value={td.description || ""}
                    onChange={(e) => updateTimeDimension(i, e.target.value)}
                    placeholder="Describe this time dimension..."
                  />
                  <span className="dict-field-src">Column: {td.column}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {!layer?.metrics?.length && !layer?.dimensions?.length && !layer?.time_dimensions?.length && (
          <div className="dict-empty">
            <span className="dict-empty-icon">-</span>
            <p className="dict-empty-text">
              No definitions were auto-generated.<br />
              You can proceed to chat or add definitions manually.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
