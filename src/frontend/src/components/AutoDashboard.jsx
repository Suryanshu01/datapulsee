import { useState, useEffect, useRef } from "react";
import { BarChart3, Newspaper } from "lucide-react";
import ChartRenderer from "./charts/ChartRenderer";
import KPIRow from "./charts/KPIRow";
import { formatNumber } from "../utils/formatNumber";

const API = import.meta.env.VITE_API_URL || "";

const STARTER_QUESTIONS = [
  "What changed last month?",
  "Compare across groups",
  "Break down by category",
  "Give me a summary",
];

function getInsightCategory(type) {
  const normalized = String(type || "").toLowerCase();
  if (normalized.includes("anomaly") || normalized.includes("outlier")) return "ANOMALY";
  if (normalized.includes("concentration") || normalized.includes("share")) return "CONCENTRATION";
  if (normalized.includes("quality") || normalized.includes("completeness")) return "QUALITY";
  if (normalized.includes("correlation") || normalized.includes("relationship")) return "CORRELATION";
  return "TREND";
}

export default function AutoDashboard({ session, onStartChat, onGoToDict }) {
  const [dashboard, setDashboard] = useState(null);
  const [loading, setLoading] = useState(true);
  const [story, setStory] = useState(null);
  const [input, setInput] = useState("");
  const [showBanner, setShowBanner] = useState(true);
  const [insights, setInsights] = useState([]);
  const [showDataTalksPanel, setShowDataTalksPanel] = useState(false);
  const topRef = useRef(null);

  // Scroll to top whenever the dashboard is shown
  useEffect(() => {
    topRef.current?.scrollIntoView({ block: "start", behavior: "instant" });
  }, [session?.session_id]);

  useEffect(() => {
    if (!session?.session_id) return;
    setLoading(true);
    setStory(null);
    fetch(`${API}/api/dashboard/${session.session_id}`)
      .then((r) => r.json())
      .then((d) => { setDashboard(d); setLoading(false); })
      .catch(() => setLoading(false));
    // Fetch data story in parallel
    fetch(`${API}/api/story/${session.session_id}`)
      .then((r) => r.json())
      .then((d) => setStory(d.story))
      .catch(() => setStory(null));
    // Fetch proactive insights
    fetch(`${API}/api/insights/${session.session_id}`)
      .then((r) => r.json())
      .then((d) => {
        const fetched = d.insights || [];
        setInsights(fetched);
      })
      .catch(() => setInsights([]));
  }, [session?.session_id]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (input.trim()) onStartChat(input.trim());
  };

  const handleSuggestion = (q) => onStartChat(q);

  if (loading) return <DashboardSkeleton />;
  if (!dashboard) return null;

  // Build KPI cards from dashboard data
  const kpiCards = dashboard.kpis
    .filter((k) => k.name.startsWith("total_"))
    .slice(0, 6)
    .map((k) => {
      let delta = undefined;
      let deltaLabel = undefined;
      if (k.sparkline?.length >= 2) {
        const prev = k.sparkline[k.sparkline.length - 2];
        const curr = k.sparkline[k.sparkline.length - 1];
        if (prev !== 0) {
          delta = Math.round(((curr - prev) / Math.abs(prev)) * 100);
          deltaLabel = "vs prior period";
        }
      }
      return {
        label: k.name.replace(/^total_/, "").replace(/_/g, " "),
        value: k.total,
        formatted: formatNumber(k.total),
        delta,
        deltaLabel,
        min: k.min,
        max: k.max,
        sparkline_data: k.sparkline?.length > 1 ? k.sparkline : undefined,
      };
    });

  // Time trend chart config
  const trendData = dashboard.time_trend?.data?.map((r) => ({
    [dashboard.time_trend.time_column]: r.period,
    value: r.value,
  }));
  const trendConfig = dashboard.time_trend
    ? { x: dashboard.time_trend.time_column, y: "value" }
    : null;

  // Dimension breakdown chart config
  const dimData = dashboard.top_dimension?.data?.map((r) => ({
    label: r.label,
    value: r.value,
  }));
  const dimConfig = dashboard.top_dimension ? { x: "label", y: "value" } : null;
  const dataQualityInsights = insights.filter((ins) => ins.type === "data_quality_score");
  const proactiveInsights = insights.filter((ins) => ins.type !== "data_quality_score");

  return (
    <div className="dashboard-page">
      {/* Scroll anchor — ensures page always starts at top */}
      <div ref={topRef} style={{ position: "absolute", top: 0 }} />

      {/* ── Section A: Overview Bar ─────────────────────────────── */}
      <div className="dashboard-overview">
        <BarChart3 size={16} color="var(--primary)" />
        <span style={{ fontWeight: 600, color: "var(--text)" }}>
          {dashboard.filename}
        </span>
        <span className="dash-pill">{dashboard.row_count?.toLocaleString()} rows</span>
        <span className="dash-pill">{dashboard.column_count} columns</span>
        {dashboard.date_range && (
          <span className="dash-pill">
            {dashboard.date_range.from} – {dashboard.date_range.to}
          </span>
        )}
        {proactiveInsights.length > 0 && (
          <button
            className="talks-panel-trigger"
            onClick={() => setShowDataTalksPanel(true)}
            type="button"
          >
            <span>Data Talks to You</span>
            <span className="talks-panel-count">{proactiveInsights.length}</span>
            <span className="talks-panel-new">NEW</span>
          </button>
        )}
      </div>

      <div className="dashboard-body">
        {/* ── Semantic layer banner ───────────────────────────────── */}
        {showBanner && (
          <div className="semantic-banner">
            <div className="semantic-banner-content">
              <span style={{ fontSize: 16 }}>✨</span>
              <span>
                DataPulse auto-detected{" "}
                <strong>{session?.semantic_layer?.metrics?.length || 0} metrics</strong>,{" "}
                <strong>{session?.semantic_layer?.dimensions?.length || 0} dimensions</strong>, and{" "}
                <strong>{session?.semantic_layer?.time_dimensions?.length || 0} time dimension{(session?.semantic_layer?.time_dimensions?.length || 0) !== 1 ? "s" : ""}</strong>.{" "}
              </span>
              <button className="semantic-banner-link" onClick={onGoToDict}>
                View Data Dictionary →
              </button>
            </div>
            <button className="semantic-banner-close" onClick={() => setShowBanner(false)}>✕</button>
          </div>
        )}

        {/* ── PII Banner ─────────────────────────────────────────── */}
        {session?.pii_columns?.length > 0 && (
          <div className="pii-banner">
            <div className="pii-banner-content">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--success)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
              <span><strong>{session.pii_columns.length} column{session.pii_columns.length > 1 ? "s" : ""} flagged as potentially sensitive</strong> — {session.pii_columns.map((p) => p.column).join(", ")}. Sample values excluded from AI prompts.</span>
            </div>
          </div>
        )}

        {/* ── Section A2: Data Story ──────────────────────────────── */}
        {story && story.length > 0 && (
          <div style={{
            background: "var(--surface)",
            border: "1px solid var(--border)",
            borderRadius: 12,
            padding: "20px 24px",
            marginBottom: 20,
            boxShadow: "0 1px 3px rgba(0,0,0,0.06)",
          }}>
            <div style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              marginBottom: 12,
              fontSize: 15,
              fontWeight: 600,
              color: "var(--text)",
            }}>
              <Newspaper size={16} color="var(--text)" />
              Here's what your data tells us
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {story.map((bullet, i) => (
                <div
                  key={i}
                  style={{
                    fontSize: 14,
                    lineHeight: 1.6,
                    color: "var(--text)",
                    paddingLeft: 16,
                    borderLeft: i === story.length - 1
                      ? "3px solid var(--warning)"
                      : "3px solid var(--border)",
                    animation: `fadeSlideIn 400ms ease-out ${i * 100}ms both`,
                  }}
                >
                  {bullet}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ── Data Quality Badge ──────────────────────────────────── */}
        {dataQualityInsights.map((dq, i) => (
          <div key={i} className="data-quality-badge">
            <span className={`dq-score ${dq.quality_pct >= 95 ? "dq-good" : dq.quality_pct >= 80 ? "dq-ok" : "dq-bad"}`}>{dq.quality_pct}%</span>
            <span className="dq-label">Data Quality</span>
            <span className="dq-detail">{dq.description}</span>
          </div>
        ))}

        {/* ── Data Talks Teaser (dedicated panel) ──────────────────── */}
        {proactiveInsights.length > 0 && (
          <section className="data-talks-teaser">
            <div>
              <span className="data-talks-teaser-pill">Innovation Feature</span>
              <div className="data-talks-teaser-title">Data Talks to You now has its own panel</div>
              <p className="data-talks-teaser-sub">
                {proactiveInsights.length} proactive insight{proactiveInsights.length !== 1 ? "s" : ""} detected from deterministic statistics.
                Open the panel to review them and jump into deeper analysis.
              </p>
            </div>
            <button
              className="btn btn-primary"
              type="button"
              onClick={() => setShowDataTalksPanel(true)}
            >
              Open Data Talks Panel
            </button>
          </section>
        )}

        {/* ── Section B: KPI Cards ────────────────────────────────── */}
        {kpiCards.length > 0 && (
          <section className="dash-section">
            <div className="dash-section-title">Key Metrics</div>
            <KPIRow kpis={kpiCards} scrollable={kpiCards.length > 4} />
          </section>
        )}

        {/* ── Section C: Primary Trend Chart ─────────────────────── */}
        {trendData?.length > 1 && trendConfig && (
          <section className="dash-section">
            <div className="dash-section-title">
              {dashboard.time_trend.metric_name.replace(/_/g, " ")} over time
            </div>
            <ChartRenderer
              data={trendData}
              chartType="area"
              config={trendConfig}
            />
          </section>
        )}

        {/* ── Section D: Dimension Breakdown ─────────────────────── */}
        {dimData?.length > 0 && dimConfig && (
          <section className="dash-section">
            <div className="dash-section-title">
              {dashboard.top_dimension.metric_name.replace(/_/g, " ")} by{" "}
              {dashboard.top_dimension.dimension_name.replace(/_/g, " ")}
            </div>
            <ChartRenderer
              data={dimData}
              chartType={dimData.length > 6 ? "horizontal_bar" : "bar"}
              config={dimConfig}
            />
          </section>
        )}

        {/* ── Section E: Start Exploring ──────────────────────────── */}
        <section className="dash-section dash-explore">
          <div className="dash-explore-title">Ready to explore deeper?</div>
          <form className="dash-explore-form" onSubmit={handleSubmit}>
            <input
              className="chat-input"
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask a question about your data..."
            />
            <button className="send-btn" type="submit" disabled={!input.trim()}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><line x1="12" y1="19" x2="12" y2="5"/><polyline points="5 12 12 5 19 12"/></svg>
            </button>
          </form>
          <div className="dash-suggestions">
            <span style={{ fontSize: 13, color: "var(--text-3)" }}>Or try:</span>
            {STARTER_QUESTIONS.map((q) => (
              <button
                key={q}
                className="follow-up-chip"
                onClick={() => handleSuggestion(q)}
              >
                {q}
              </button>
            ))}
          </div>
        </section>
      </div>

      {showDataTalksPanel && (
        <DataTalksPanel
          insights={proactiveInsights}
          onClose={() => setShowDataTalksPanel(false)}
          onStartChat={onStartChat}
        />
      )}
    </div>
  );
}

function DataTalksPanel({ insights, onClose, onStartChat }) {
  return (
    <div className="talks-panel-overlay" onClick={onClose}>
      <aside className="talks-panel" onClick={(e) => e.stopPropagation()}>
        <div className="talks-panel-header">
          <div>
            <div className="talks-panel-kicker">INNOVATION FEATURE</div>
            <h3 className="talks-panel-title">Data Talks to You</h3>
            <p className="talks-panel-subtitle">
              {insights.length} insight{insights.length !== 1 ? "s" : ""} found using deterministic stats (no AI inference).
            </p>
          </div>
          <button className="talks-panel-close" type="button" onClick={onClose} aria-label="Close Data Talks panel">
            ✕
          </button>
        </div>

        <div className="talks-panel-list">
          {insights.map((insight, i) => (
            <div key={i} className={`talks-insight-card insight-${insight.severity}`}>
              <span className={`insight-category-tag insight-category-${insight.severity}`}>
                {getInsightCategory(insight.type)}
              </span>
              <div className="insight-card-header">
                <span>{insight.severity === "high" ? "⚠️" : insight.severity === "medium" ? "📊" : "💡"}</span>
                <span className="insight-card-type">{insight.type.replace(/_/g, " ")}</span>
              </div>
              <div className="insight-card-title">{insight.title}</div>
              <div className="insight-card-desc">{insight.description}</div>
              {insight.suggested_question && (
                <button className="insight-dive-btn" onClick={() => onStartChat(insight.suggested_question)}>
                  Dive deeper →
                </button>
              )}
            </div>
          ))}
        </div>
      </aside>
    </div>
  );
}

function DashboardSkeleton() {
  return (
    <div className="dashboard-page">
      <div className="dashboard-overview">
        <div className="skeleton-bar" style={{ width: 280, height: 16 }} />
      </div>
      <div className="dashboard-body">
        <div className="kpi-row" style={{ marginBottom: 24 }}>
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="kpi-card">
              <div className="skeleton-bar" style={{ width: "60%", marginBottom: 8 }} />
              <div className="skeleton-bar" style={{ width: "80%", height: 24 }} />
            </div>
          ))}
        </div>
        <div className="skeleton-bar" style={{ width: "100%", height: 220, borderRadius: 8 }} />
      </div>
    </div>
  );
}
