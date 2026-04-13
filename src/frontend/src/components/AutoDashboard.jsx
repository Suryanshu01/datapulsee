import { useState, useEffect, useRef } from "react";
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

export default function AutoDashboard({ session, onStartChat }) {
  const [dashboard, setDashboard] = useState(null);
  const [loading, setLoading] = useState(true);
  const [story, setStory] = useState(null);
  const [input, setInput] = useState("");
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
    .map((k) => ({
      label: k.name.replace(/^total_/, "").replace(/_/g, " "),
      value: k.total,
      formatted: formatNumber(k.total),
      min: k.min,
      max: k.max,
      sparkline_data: k.sparkline?.length > 1 ? k.sparkline : undefined,
    }));

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

  return (
    <div className="dashboard-page">
      {/* Scroll anchor — ensures page always starts at top */}
      <div ref={topRef} style={{ position: "absolute", top: 0 }} />

      {/* ── Section A: Overview Bar ─────────────────────────────── */}
      <div className="dashboard-overview">
        <span style={{ fontSize: 16 }}>📊</span>
        <span style={{ fontWeight: 600, color: "#1A1A2E" }}>
          {dashboard.filename}
        </span>
        <span className="dash-pill">{dashboard.row_count?.toLocaleString()} rows</span>
        <span className="dash-pill">{dashboard.column_count} columns</span>
        {dashboard.date_range && (
          <span className="dash-pill">
            {dashboard.date_range.from} – {dashboard.date_range.to}
          </span>
        )}
      </div>

      <div className="dashboard-body">
        {/* ── Section A2: Data Story ──────────────────────────────── */}
        {story && story.length > 0 && (
          <div style={{
            background: "#FFFFFF",
            border: "1px solid #E5E7EB",
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
              color: "#1A1A2E",
            }}>
              <span style={{ fontSize: 18 }}>📰</span>
              Here's what your data tells us
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {story.map((bullet, i) => (
                <div
                  key={i}
                  style={{
                    fontSize: 14,
                    lineHeight: 1.6,
                    color: "#374151",
                    paddingLeft: 16,
                    borderLeft: i === story.length - 1
                      ? "3px solid #D4760A"
                      : "3px solid #E5E7EB",
                    animation: `fadeSlideIn 400ms ease-out ${i * 100}ms both`,
                  }}
                >
                  {bullet}
                </div>
              ))}
            </div>
          </div>
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
              &rarr;
            </button>
          </form>
          <div className="dash-suggestions">
            <span style={{ fontSize: 13, color: "#9CA3AF" }}>Or try:</span>
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
