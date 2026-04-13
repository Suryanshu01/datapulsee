import { useState, useCallback } from "react";
import UploadPanel from "./components/UploadPanel";
import ChatInterface from "./components/ChatInterface";
import SemanticLayer from "./components/SemanticLayer";
import DataPreview from "./components/DataPreview";
import AutoDashboard from "./components/AutoDashboard";

const API = import.meta.env.VITE_API_URL || "";

export default function App() {
  const [session, setSession]         = useState(null);
  const [messages, setMessages]       = useState([]);
  const [loading, setLoading]         = useState(false);
  const [activePanel, setActivePanel] = useState("dashboard"); // dashboard | chat | semantic | preview

  const handleUploadResult = useCallback((data, displayName) => {
    setSession({ ...data, filename: displayName });
    setActivePanel("dashboard");
    setMessages([{
      role: "system",
      content: `Dataset ready — ${displayName} · ${data.row_count.toLocaleString()} rows · ${data.schema.length} columns`,
    }]);
  }, []);

  const handleUpload = useCallback(async (file) => {
    setLoading(true);
    try {
      const form = new FormData();
      form.append("file", file);
      const res = await fetch(`${API}/api/upload`, { method: "POST", body: form });
      if (!res.ok) { const e = await res.json().catch(() => null); throw new Error(e?.detail || res.statusText); }
      handleUploadResult(await res.json(), file.name);
    } catch (err) { alert("Upload failed: " + err.message); }
    setLoading(false);
  }, [handleUploadResult]);

  const handleSampleLoad = useCallback(async (filename) => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/api/samples/${filename}`);
      if (!res.ok) { const e = await res.json().catch(() => null); throw new Error(e?.detail || res.statusText); }
      handleUploadResult(await res.json(), filename);
    } catch (err) { alert("Failed to load sample: " + err.message); }
    setLoading(false);
  }, [handleUploadResult]);

  const handleAsk = useCallback(async (question, mode = "auto", simpleMode = true) => {
    if (!session?.session_id) return;
    // Transition to chat view when a question is asked
    setActivePanel("chat");
    setMessages((prev) => [...prev, { role: "user", content: question }]);
    setLoading(true);
    try {
      const res = await fetch(`${API}/api/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: session.session_id, question, mode, simple_mode: simpleMode }),
      });
      if (!res.ok) { const e = await res.json().catch(() => null); throw new Error(e?.detail || res.statusText); }
      const data = await res.json();

      if (data.needs_clarification) {
        setMessages((prev) => [...prev, {
          role: "clarification",
          content: data.clarification_question,
          options: data.clarification_options || [],
        }]);
      } else {
        setMessages((prev) => [...prev, {
          role: "assistant",
          content: data.explanation,
          insightLine: data.insight_line,
          data: data.data,
          columns: data.columns,
          sql: data.sql,
          queryExplanation: data.query_explanation,
          chartType: data.chart_type,
          chartConfig: data.chart_config,
          kpis: data.kpis || [],
          followUps: data.follow_ups || [],
          intent: data.intent,
          totalRows: data.total_rows,
          totalRowsInDataset: data.total_rows_in_dataset,
          metricsUsed: data.metrics_used,
          retried: data.retried,
          confidence: data.confidence,
          coveragePct: data.coverage_pct,
          dataCoverage: data.data_coverage,
          driverAnalysis: data.driver_analysis,
          queryValidated: data.query_validated,
          cached: data.cached,
          actionInsight: data.action_insight,
          verdict: data.verdict,
        }]);
      }
    } catch (err) {
      setMessages((prev) => [...prev, { role: "assistant", content: "Sorry, I couldn't answer that. " + err.message }]);
    }
    setLoading(false);
  }, [session]);

  /* ── Landing ─────────────────────────────────────────────── */
  if (!session) {
    return (
      <div className="landing">
        <div className="landing-inner">
          <div className="landing-logo">
            <div className="landing-logo-mark">DP</div>
            <span className="landing-logo-name">DataPulse</span>
          </div>
          <div className="hero-badge">
            <span className="hero-badge-dot" />
            Runs locally · No data leaves your device
          </div>
          <div className="hero-text">
            <h1 className="hero-title">Talk to your data.<br />Get answers you trust.</h1>
            <p className="hero-sub">
              Upload any spreadsheet and ask questions in plain English.
              No SQL, no formulas, no training required.
            </p>
          </div>
          <UploadPanel onUpload={handleUpload} onSampleLoad={handleSampleLoad} loading={loading} />
        </div>
      </div>
    );
  }

  /* ── Workspace ───────────────────────────────────────────── */
  return (
    <div className="workspace">
      <aside className="sidebar">
        <div className="sidebar-logo">
          <div className="logo-mark">DP</div>
          <span className="logo-name">DataPulse</span>
        </div>

        <div className="nav-group">
          <div className="nav-group-label">Workspace</div>
          <button
            className={`nav-item ${activePanel === "dashboard" ? "active" : ""}`}
            onClick={() => setActivePanel("dashboard")}
          >
            <span className="nav-item-icon">📊</span>
            <span className="nav-item-label">Overview</span>
          </button>
          <button
            className={`nav-item ${activePanel === "chat" ? "active" : ""}`}
            onClick={() => setActivePanel("chat")}
          >
            <span className="nav-item-icon">💬</span>
            <span className="nav-item-label">Chat</span>
          </button>
          <button
            className={`nav-item ${activePanel === "semantic" ? "active" : ""}`}
            onClick={() => setActivePanel("semantic")}
          >
            <span className="nav-item-icon">📖</span>
            <span className="nav-item-label">Data Dictionary</span>
          </button>
          <button
            className={`nav-item ${activePanel === "preview" ? "active" : ""}`}
            onClick={() => setActivePanel("preview")}
          >
            <span className="nav-item-icon">🔍</span>
            <span className="nav-item-label">Data Preview</span>
          </button>
        </div>

        <div className="sidebar-footer">
          <div className="dataset-card">
            <div className="dataset-card-name" title={session.filename}>
              {session.filename}
            </div>
            <div className="dataset-card-meta">
              <span className="dataset-pill-tag">{session.row_count?.toLocaleString()} rows</span>
              <span className="dataset-pill-tag">{session.schema?.length} cols</span>
            </div>
          </div>
          <button
            className="new-file-btn"
            onClick={() => { setSession(null); setMessages([]); setActivePanel("dashboard"); }}
          >
            <span>+</span> <span>New dataset</span>
          </button>
        </div>
      </aside>

      <main className="main-area">
        {activePanel === "dashboard" && (
          <AutoDashboard
            session={session}
            onStartChat={(q) => handleAsk(q)}
          />
        )}

        {activePanel === "chat" && (
          <ChatInterface
            messages={messages}
            onAsk={handleAsk}
            loading={loading}
            semanticLayer={session.semantic_layer}
            onGoToDashboard={() => setActivePanel("dashboard")}
          />
        )}

        {activePanel === "semantic" && (
          <SemanticLayer
            semanticLayer={session.semantic_layer}
            sessionId={session.session_id}
            onStartChatting={() => setActivePanel("chat")}
          />
        )}

        {activePanel === "preview" && (
          <DataPreview
            schema={session.schema}
            sample={session.sample}
            stats={session.stats}
            rowCount={session.row_count}
          />
        )}
      </main>
    </div>
  );
}
