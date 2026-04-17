import { useState, useRef, useEffect } from "react";
import { LayoutDashboard } from "lucide-react";
import ChartRenderer from "./charts/ChartRenderer";
import KPIRow from "./charts/KPIRow";
import WaterfallChart from "./charts/WaterfallChart";

const MODES = [
  { id: "auto",      label: "Auto" },
  { id: "change",    label: "What Changed" },
  { id: "compare",   label: "Compare" },
  { id: "breakdown", label: "Breakdown" },
  { id: "summary",   label: "Summary" },
];

const SUGGESTION_CATEGORIES = [
  {
    id: "trends", label: "Trends & Changes",
    questions: [
      "How has performance changed over time?",
      "Show me the month-over-month trend",
      "When did we see the biggest increase or drop?",
      "Is there a seasonal pattern in the data?",
    ],
  },
  {
    id: "top", label: "Rankings & Top Results",
    questions: [
      "What are the top 5 by total value?",
      "Which category or group performs best?",
      "Show me the highest and lowest values",
      "What is driving the most volume?",
    ],
  },
  {
    id: "breakdown", label: "Breakdown & Segments",
    questions: [
      "Break this down by category",
      "How is performance split across groups?",
      "What percentage does each segment represent?",
      "Show the distribution of totals",
    ],
  },
  {
    id: "summary", label: "Quick Summaries",
    questions: [
      "Give me a plain-English summary",
      "What are the 3 most important things to know?",
      "Are there any unusual patterns or outliers?",
      "What should I be paying attention to?",
    ],
  },
];

export default function ChatInterface({ messages, onAsk, loading, semanticLayer, onGoToDashboard }) {
  const [input, setInput] = useState("");
  const [mode, setMode] = useState("auto");
  const [simpleMode, setSimpleMode] = useState(true);
  const bottomRef = useRef();

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Wrap onAsk to automatically include simpleMode
  const handleAsk = (question, askMode) => {
    onAsk(question, askMode ?? mode, simpleMode);
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!input.trim() || loading) return;
    handleAsk(input.trim(), mode);
    setInput("");
  };

  const hasMessages = messages.length > 1;

  return (
    <div className="chat-layout">
      {/* Mode selector */}
      <div className="mode-bar">
        {onGoToDashboard && (
          <button
            className="btn btn-ghost"
            onClick={onGoToDashboard}
            style={{ fontSize: 13, padding: "4px 10px", marginRight: 8 }}
          >
            <LayoutDashboard size={14} style={{ marginRight: 4 }} /> Overview
          </button>
        )}
        <span className="mode-bar-label">Mode:</span>
        {MODES.map((m) => (
          <button
            key={m.id}
            className={`mode-chip ${mode === m.id ? "active" : ""}`}
            onClick={() => setMode(m.id)}
          >
            {m.label}
          </button>
        ))}
        <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 6, padding: "4px", background: "#F3F4F6", borderRadius: 20 }}>
          <button
            onClick={() => setSimpleMode(true)}
            style={{
              padding: "4px 12px", borderRadius: 16, border: "none", fontSize: 12, fontWeight: 500,
              cursor: "pointer", fontFamily: "inherit",
              background: simpleMode ? "#42145F" : "transparent",
              color: simpleMode ? "white" : "#6B7280",
              transition: "all 0.15s",
            }}
          >
            Simple
          </button>
          <button
            onClick={() => setSimpleMode(false)}
            style={{
              padding: "4px 12px", borderRadius: 16, border: "none", fontSize: 12, fontWeight: 500,
              cursor: "pointer", fontFamily: "inherit",
              background: !simpleMode ? "#42145F" : "transparent",
              color: !simpleMode ? "white" : "#6B7280",
              transition: "all 0.15s",
            }}
          >
            Detailed
          </button>
        </div>
      </div>

      {/* Messages / Welcome */}
      <div className="messages-area">
        {!hasMessages ? (
          <WelcomeScreen onAsk={handleAsk} mode={mode} />
        ) : (
          <>
            {messages.map((msg, i) => (
              <MessageBubble
                key={i}
                msg={msg}
                onAsk={handleAsk}
                mode={mode}
                semanticLayer={semanticLayer}
              />
            ))}
            {loading && <LoadingMessage />}
            <div ref={bottomRef} />
          </>
        )}
      </div>

      {/* Input bar */}
      <form className="chat-input-bar" onSubmit={handleSubmit}>
        <input
          className="chat-input"
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask anything about your data..."
          disabled={loading}
        />
        <button className="send-btn" type="submit" disabled={loading || !input.trim()}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><line x1="12" y1="19" x2="12" y2="5"/><polyline points="5 12 12 5 19 12"/></svg>
        </button>
      </form>
    </div>
  );
}

/* ── Welcome Screen ──────────────────────────────────────────── */
function WelcomeScreen({ onAsk, mode }) {
  return (
    <div className="welcome-screen">
      <div style={{ textAlign: "center", marginBottom: 28 }}>
        <div className="welcome-title">What would you like to know?</div>
        <p className="welcome-sub">Pick a question below, or type your own</p>
      </div>
      <div className="suggestion-grid">
        {SUGGESTION_CATEGORIES.map((cat) => (
          <div key={cat.id} className="suggestion-category-card">
            <div className="suggestion-cat-name" style={{ fontWeight: 600, fontSize: 13, marginBottom: 10, color: "#1A1A2E" }}>
              {cat.label}
            </div>
            {cat.questions.map((q) => (
              <button key={q} className="suggestion-item" onClick={() => onAsk(q, mode)}>
                {q}
              </button>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

/* ── Message Bubble ──────────────────────────────────────────── */
function MessageBubble({ msg, onAsk, mode, semanticLayer }) {
  const [showTable, setShowTable] = useState(false);

  if (msg.role === "system") {
    return (
      <div className="msg system">
        <div className="msg-bubble">{msg.content}</div>
      </div>
    );
  }

  if (msg.role === "user") {
    return (
      <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 16 }}>
        <div className="user-bubble">{msg.content}</div>
      </div>
    );
  }

  if (msg.role === "error") {
    return (
      <div className="assistant-message">
        <div className="error-card">
          <div className="error-card-title">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--danger)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
            {msg.content}
          </div>
          {msg.errorDetail && (
            <div className="error-card-detail">{msg.errorDetail}</div>
          )}
          <div className="error-card-actions">
            <button
              className="btn btn-primary"
              style={{ fontSize: 13, padding: "6px 14px" }}
              onClick={() => onAsk(msg.originalQuestion, mode)}
            >
              Try again
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (msg.role === "clarification") {
    return (
      <div className="assistant-message">
        <div className="clarification-question">{msg.content}</div>
        <div className="clarification-options">
          {msg.options?.map((opt) => (
            <button key={opt} className="clarification-chip" onClick={() => onAsk(opt, mode)}>
              {opt}
            </button>
          ))}
        </div>
      </div>
    );
  }

  // Assistant — visual-first hierarchy
  return (
    <div className="assistant-message">
      {/* Intent classification badge */}
      {msg.intent && (
        <div className="intent-tag-row">
          <span className={`intent-tag intent-tag-${msg.intent}`}>
            {msg.intent === "change" && "🔄 "}
            {msg.intent === "compare" && "⚖️ "}
            {msg.intent === "breakdown" && "📊 "}
            {msg.intent === "summary" && "📋 "}
            {msg.intent === "general" && "💡 "}
            {msg.intent.charAt(0).toUpperCase() + msg.intent.slice(1)} Analysis
          </span>
        </div>
      )}

      {/* 0. Verdict (compare intent) */}
      {msg.verdict && (
        <div style={{
          fontSize: 15, fontWeight: 600, color: "#1A1A2E",
          padding: "12px 16px", background: "#F0ECFA", borderRadius: 8,
          marginBottom: 12, borderLeft: "4px solid #42145F",
        }}>
          {msg.verdict}
        </div>
      )}

      {/* 1. KPI Cards */}
      {msg.kpis?.length > 0 && <KPIRow kpis={msg.kpis} />}

      {/* 2. Hero Chart */}
      {msg.data?.length > 0 && msg.chartType && msg.chartType !== "kpi_only" && msg.chartType !== "table" && (
        <ChartRenderer
          data={msg.data}
          chartType={msg.chartType}
          config={msg.chartConfig}
          kpis={msg.kpis}
        />
      )}

      {/* 2b. Driver Waterfall Chart (change intent) */}
      {msg.driverAnalysis?.drivers?.length > 0 && (
        <WaterfallChart
          drivers={msg.driverAnalysis.drivers}
          comparison={msg.driverAnalysis.comparison}
        />
      )}

      {/* 3. Insight line */}
      {msg.insightLine && (
        <p className="insight-line">{msg.insightLine}</p>
      )}

      {/* 4. Explanation with purple left border */}
      {msg.content && (
        <p className="explanation">{msg.content}</p>
      )}

      {/* 4b. Action insight */}
      {msg.actionInsight && (
        <div style={{
          background: "#FEF9EE", border: "1px solid #FDE68A", borderRadius: 8,
          padding: "10px 14px", marginTop: 12, fontSize: 14, fontWeight: 500,
          color: "#92400E", lineHeight: 1.5,
          animation: "fadeSlideIn 400ms ease-out 600ms both",
        }}>
          {msg.actionInsight}
        </div>
      )}

      {/* Trust signals — always visible */}
      {msg.sql && (
        <div className="trust-badges-row">
          {msg.queryValidated && (
            <span className="trust-badge trust-badge-success">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><path d="M20 6L9 17l-5-5"/></svg>
              Query validated
            </span>
          )}
          {msg.confidence && (
            <span className={`trust-badge trust-badge-${msg.confidence.level === "high" ? "success" : msg.confidence.level === "medium" ? "warning" : "danger"}`}>
              Confidence: {msg.confidence.level}
            </span>
          )}
          {msg.coveragePct != null && (
            <span className="trust-badge trust-badge-neutral">
              Coverage: {msg.coveragePct}%
            </span>
          )}
          {msg.intent && (
            <span className="trust-badge trust-badge-intent">
              {msg.intent}
            </span>
          )}
          {msg.retried && (
            <span className="trust-badge trust-badge-warning">
              Self-corrected
            </span>
          )}
        </div>
      )}

      {/* Cached badge */}
      {msg.cached && <span className="cached-badge">Cached result</span>}

      {/* 5. Raw data toggle */}
      {msg.data?.length > 0 && (
        <details className="raw-data-toggle" open={showTable}>
          <summary onClick={(e) => { e.preventDefault(); setShowTable(!showTable); }}>
            View raw data ({msg.totalRows} rows)
          </summary>
          {showTable && (
            <div className="msg-table-wrap">
              <table className="msg-table">
                <thead>
                  <tr>{msg.columns?.slice(0, 8).map((c) => <th key={c}>{c}</th>)}</tr>
                </thead>
                <tbody>
                  {msg.data.slice(0, 20).map((row, ri) => (
                    <tr key={ri}>
                      {msg.columns?.slice(0, 8).map((c) => (
                        <td key={c}>
                          {typeof row[c] === "number" ? row[c].toLocaleString() : String(row[c] ?? "")}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
              {msg.totalRows > 20 && (
                <div className="msg-table-note">Showing 20 of {msg.totalRows.toLocaleString()} rows</div>
              )}
            </div>
          )}
        </details>
      )}

      {/* 6. Follow-up chips */}
      {msg.followUps?.length > 0 && (
        <div className="follow-up-chips">
          {msg.followUps.map((q) => (
            <button key={q} className="follow-up-chip" onClick={() => onAsk(q, "auto")}>
              {q}
            </button>
          ))}
        </div>
      )}


      {/* 7. Transparency — collapsed <details> */}
      {msg.sql && (
        <details className="transparency-toggle">
          <summary>How was this answered?</summary>
          <div className="transparency-content">
            {msg.queryValidated && (
              <span className="validation-badge">✓ Query validated — read-only, no destructive operations</span>
            )}
            <span className="intent-badge">{msg.intent}</span>
            {msg.retried && <span className="retried-pill" style={{ marginLeft: 6 }}>Self-corrected</span>}
            {msg.confidence && (
              <p style={{ marginTop: 6 }}>
                Confidence: <strong>{msg.confidence.level}</strong> — {msg.confidence.reason}
              </p>
            )}
            {msg.coveragePct != null && (
              <p>Coverage: {msg.totalRows?.toLocaleString()} of {msg.totalRowsInDataset?.toLocaleString()} rows ({msg.coveragePct}%)</p>
            )}
            {msg.metricsUsed?.length > 0 && (
              <div className="lineage-section">
                <div className="lineage-label">Metrics &amp; Sources</div>
                {msg.metricsUsed.map((m, i) => (
                  <div key={i} className="lineage-item">
                    <span className="lineage-name">{typeof m === 'string' ? m : m.name}</span>
                    {m.expr && <code className="lineage-expr">{m.expr}</code>}
                    <span className="lineage-source">from Data Dictionary</span>
                  </div>
                ))}
                {msg.dataCoverage && (
                  <div className="lineage-coverage">
                    Data coverage: {msg.dataCoverage.rows_matched} of {msg.dataCoverage.total_rows} rows ({msg.dataCoverage.coverage_pct}%)
                  </div>
                )}
              </div>
            )}
            <p style={{ marginTop: 8, marginBottom: 4, fontSize: 11, color: "#6B7280" }}>SQL</p>
            <code>{msg.sql}</code>
          </div>
        </details>
      )}

      {/* Copy as markdown */}
      <CopyButton msg={msg} />
    </div>
  );
}

/* ── Copy Button ─────────────────────────────────────────────── */
function CopyButton({ msg }) {
  const [copied, setCopied] = useState(false);

  if (!msg.sql) return null;

  const handleCopy = () => {
    let md = "";
    if (msg.insightLine) md += `**${msg.insightLine}**\n\n`;
    md += msg.content + "\n";
    if (msg.data?.length && msg.columns?.length) {
      md += "\n| " + msg.columns.join(" | ") + " |\n";
      md += "| " + msg.columns.map(() => "---").join(" | ") + " |\n";
      msg.data.slice(0, 10).forEach((row) => {
        md += "| " + msg.columns.map((c) => String(row[c] ?? "")).join(" | ") + " |\n";
      });
    }
    navigator.clipboard.writeText(md);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <button className="copy-btn" onClick={handleCopy} style={{ marginTop: 8 }}>
      {copied ? "Copied" : "Copy as markdown"}
    </button>
  );
}

/* ── Loading indicator (step-by-step thinking) ───────────────── */
function LoadingMessage() {
  const steps = [
    { icon: "🔍", text: "Understanding your question..." },
    { icon: "📐", text: "Selecting relevant metrics & dimensions..." },
    { icon: "🔧", text: "Writing SQL query..." },
    { icon: "⚡", text: "Executing against your dataset..." },
    { icon: "✍️", text: "Generating explanation..." },
  ];
  const [visibleCount, setVisibleCount] = useState(0);

  useEffect(() => {
    setVisibleCount(1);
    const timers = steps.slice(1).map((_, i) =>
      setTimeout(() => setVisibleCount(i + 2), (i + 1) * 900)
    );
    return () => timers.forEach(clearTimeout);
  }, []);

  return (
    <div className="assistant-message">
      <div className="thinking-steps">
        {steps.slice(0, visibleCount).map((step, i) => (
          <div
            key={i}
            className={`thinking-step ${i === visibleCount - 1 ? "active" : "done"}`}
          >
            <span className="thinking-icon">{i < visibleCount - 1 ? "✓" : step.icon}</span>
            <span className="thinking-text">{step.text}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
