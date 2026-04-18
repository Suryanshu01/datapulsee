# CLAUDE.md — DataPulse Feature Implementation Guide

## Context

DataPulse is a self-service data intelligence tool for the NatWest Group India Hackathon (top 53 of 2080 teams). Users upload CSVs, ask NL questions, get visual answers. Stack: FastAPI + DuckDB + Groq LLM + React 18 + Vite.

**THE BIG IDEA**: "Data Talks to You" — instead of just answering questions, DataPulse proactively finds insights, flags anomalies, detects PII, and cross-verifies its own answers. The data speaks first before you ask anything.

## Coding Rules

- Python: type hints, docstrings on public functions
- No new pip dependencies — use only stdlib + what is in requirements.txt (duckdb, pandas, numpy, fastapi, groq, pydantic). Exception: openpyxl for xlsx support.
- No new npm dependencies — lucide-react and recharts are already installed
- CSS: always use `var(--token)` from `:root` in index.css, never hardcode hex colors in JSX inline styles
- Git: `git commit -s` for DCO sign-off

## File Locations

```
src/backend/
  main.py, config.py
  routes/       -> upload.py, query.py, semantic.py, dashboard.py
  services/     -> query_pipeline.py, driver_analysis.py, schema_analyzer.py, semantic_engine.py, chart_recommender.py, explanation.py
  utils/        -> llm_client.py, duckdb_manager.py, cache.py, sql_sanitizer.py
  models/       -> schemas.py

src/frontend/src/
  App.jsx, main.jsx, index.css
  components/   -> ChatInterface.jsx, AutoDashboard.jsx, SemanticLayer.jsx, DataPreview.jsx, UploadPanel.jsx, TrustPanel.jsx
  components/charts/ -> ChartRenderer.jsx, KPICard.jsx, KPIRow.jsx, WaterfallChart.jsx, AnimatedBar.jsx, AnimatedLine.jsx, AnimatedDonut.jsx, Sparkline.jsx
  utils/        -> formatNumber.js
```

## CSS Variables Available (in :root and [data-theme="dark"])

```
--bg --surface --surface-2 --surface-3 --border --border-md
--primary --primary-light --primary-bg --primary-hover
--success --success-bg --warning --warning-bg --danger --danger-bg --info
--text --text-2 --text-3
--shadow-sm --shadow-md --shadow-lg
--r --r-sm --r-xs --font --font-mono
```

---

# TASK LIST — Execute in exact order

---

## TASK 1: Create Insights Engine (Backend)

Create NEW file `src/backend/services/insights_engine.py`. This is the core differentiator — "Data Talks to You." It runs 5 deterministic analyses (ZERO LLM calls) on upload.

### Create this file with this exact content:

```python
"""
Proactive Insights Engine for DataPulse.
"Data Talks to You" — surfaces insights BEFORE the user asks anything.

All computations are deterministic (pure SQL + math). No LLM involved.
This ensures every insight is verifiable and trustworthy.

Five analysis types:
  1. Anomaly Detection — z-score flagging per metric x time period
  2. Concentration Risk — share % per metric x dimension
  3. Trend Reversals — direction changes in time series
  4. Data Quality — null rates, duplicate rows
  5. Correlations — Pearson correlation between metric pairs
"""

from __future__ import annotations

import logging
import math
from typing import Any

import duckdb

logger = logging.getLogger(__name__)


def generate_insights(
    conn: duckdb.DuckDBPyConnection,
    semantic_layer: dict[str, Any],
    table_name: str = "dataset",
) -> list[dict[str, Any]]:
    """
    Run all insight detectors and return a prioritized list of insight cards.
    Each card: type, severity (high/medium/low), title, description, suggested_question.
    """
    insights: list[dict[str, Any]] = []
    metrics = semantic_layer.get("metrics", [])
    dimensions = semantic_layer.get("dimensions", [])
    time_dims = semantic_layer.get("time_dimensions", [])

    if time_dims and metrics:
        insights.extend(_detect_anomalies(conn, metrics, time_dims[0], table_name))
    if dimensions and metrics:
        insights.extend(_detect_concentration(conn, metrics, dimensions, table_name))
    if time_dims and metrics:
        insights.extend(_detect_trend_reversals(conn, metrics, time_dims[0], table_name))
    insights.extend(_check_data_quality(conn, semantic_layer, table_name))
    if len(metrics) >= 2:
        insights.extend(_detect_correlations(conn, metrics, table_name))

    severity_order = {"high": 0, "medium": 1, "low": 2}
    insights.sort(key=lambda x: severity_order.get(x.get("severity", "low"), 3))
    return insights[:8]


def _detect_anomalies(conn, metrics, time_dim, table_name):
    results = []
    time_col = time_dim.get("column", "")
    if not time_col:
        return results
    for metric in metrics[:3]:
        col = metric.get("column", "")
        if not col:
            continue
        try:
            rows = conn.execute(f"""
                WITH period_values AS (
                    SELECT CAST("{time_col}" AS VARCHAR) AS period, SUM("{col}") AS value
                    FROM "{table_name}" GROUP BY CAST("{time_col}" AS VARCHAR)
                ),
                stats AS (
                    SELECT AVG(value) AS mean_val, STDDEV(value) AS std_val FROM period_values
                )
                SELECT p.period, p.value, s.mean_val, s.std_val,
                    CASE WHEN s.std_val > 0 THEN ABS(p.value - s.mean_val) / s.std_val ELSE 0 END AS z_score
                FROM period_values p, stats s WHERE s.std_val > 0
                ORDER BY z_score DESC LIMIT 3
            """).fetchdf().to_dict(orient="records")
            for row in rows:
                z = float(row["z_score"])
                if z < 2.0:
                    continue
                value = float(row["value"])
                mean = float(row["mean_val"])
                period = str(row["period"])
                direction = "above" if value > mean else "below"
                pct_diff = round(abs(value - mean) / mean * 100, 1) if mean != 0 else 0
                metric_name = metric.get("name", col).replace("_", " ")
                results.append({
                    "type": "anomaly", "severity": "high" if z > 3 else "medium",
                    "title": f"Unusual {metric_name} in {period}",
                    "description": f"{metric_name.capitalize()} was {_fmt(value)} in {period} — {pct_diff}% {direction} the average of {_fmt(mean)}. This is {round(z, 1)} standard deviations from normal.",
                    "metric": metric.get("name"), "period": period, "z_score": round(z, 1),
                    "suggested_question": f"Why did {metric_name} change in {period}?",
                })
        except Exception as exc:
            logger.debug("Anomaly detection failed for %s: %s", col, exc)
    return results


def _detect_concentration(conn, metrics, dimensions, table_name):
    results = []
    for metric in metrics[:2]:
        col = metric.get("column", "")
        if not col:
            continue
        for dim in dimensions[:3]:
            dim_col = dim.get("column", "")
            if not dim_col:
                continue
            try:
                rows = conn.execute(f"""
                    SELECT "{dim_col}" AS dim_value, SUM("{col}") AS value,
                        SUM("{col}") * 100.0 / NULLIF(SUM(SUM("{col}")) OVER (), 0) AS pct
                    FROM "{table_name}" GROUP BY "{dim_col}" ORDER BY value DESC LIMIT 5
                """).fetchdf().to_dict(orient="records")
                if rows and float(rows[0]["pct"]) > 45:
                    top = rows[0]
                    metric_name = metric.get("name", col).replace("_", " ")
                    dim_name = dim.get("name", dim_col).replace("_", " ")
                    pct = round(float(top["pct"]), 1)
                    results.append({
                        "type": "concentration", "severity": "high" if pct > 60 else "medium",
                        "title": f"High concentration in {dim_name}",
                        "description": f"{str(top['dim_value'])} accounts for {pct}% of all {metric_name}. Changes in this single {dim_name} disproportionately affect totals.",
                        "metric": metric.get("name"), "dimension": dim.get("name"),
                        "top_value": str(top["dim_value"]), "concentration_pct": pct,
                        "suggested_question": f"Break down {metric_name} by {dim_name}",
                    })
            except Exception as exc:
                logger.debug("Concentration check failed: %s", exc)
    return results


def _detect_trend_reversals(conn, metrics, time_dim, table_name):
    results = []
    time_col = time_dim.get("column", "")
    if not time_col:
        return results
    for metric in metrics[:3]:
        col = metric.get("column", "")
        if not col:
            continue
        try:
            rows = conn.execute(f"""
                SELECT CAST("{time_col}" AS VARCHAR) AS period, SUM("{col}") AS value
                FROM "{table_name}" GROUP BY CAST("{time_col}" AS VARCHAR) ORDER BY period ASC
            """).fetchdf().to_dict(orient="records")
            if len(rows) < 4:
                continue
            values = [float(r["value"]) for r in rows]
            periods = [str(r["period"]) for r in rows]
            deltas = [values[i] - values[i - 1] for i in range(1, len(values))]
            for i in range(3, len(deltas)):
                prev_signs = [1 if d > 0 else -1 for d in deltas[i - 3:i]]
                curr_sign = 1 if deltas[i] > 0 else -1
                if all(s == prev_signs[0] for s in prev_signs) and curr_sign != prev_signs[0]:
                    was_growing = prev_signs[0] > 0
                    metric_name = metric.get("name", col).replace("_", " ")
                    reversal_period = periods[i + 1]
                    pct_change = round(deltas[i] / values[i] * 100, 1) if values[i] != 0 else 0
                    results.append({
                        "type": "trend_reversal", "severity": "medium",
                        "title": f"{metric_name.capitalize()} reversed trend",
                        "description": f"{metric_name.capitalize()} had been {'growing' if was_growing else 'declining'} for {len(prev_signs)} consecutive periods but {'declined' if was_growing else 'grew'} {abs(pct_change)}% in {reversal_period}.",
                        "metric": metric.get("name"), "period": reversal_period,
                        "suggested_question": f"What changed in {reversal_period} for {metric_name}?",
                    })
                    break
        except Exception as exc:
            logger.debug("Trend reversal detection failed: %s", exc)
    return results


def _check_data_quality(conn, semantic_layer, table_name):
    results = []
    all_cols = []
    for group in ["metrics", "dimensions", "time_dimensions"]:
        for item in semantic_layer.get(group, []):
            col = item.get("column", "")
            if col:
                all_cols.append(col)
    if not all_cols:
        return results
    try:
        total_rows = conn.execute(f'SELECT COUNT(*) FROM "{table_name}"').fetchone()[0]
        if total_rows == 0:
            return results
        null_issues = []
        for col in all_cols:
            try:
                null_count = conn.execute(f'SELECT COUNT(*) FROM "{table_name}" WHERE "{col}" IS NULL').fetchone()[0]
                if null_count > 0:
                    pct = round(null_count / total_rows * 100, 1)
                    if pct >= 1.0:
                        null_issues.append({"column": col, "pct": pct, "count": null_count})
            except Exception:
                pass
        if null_issues:
            null_issues.sort(key=lambda x: x["pct"], reverse=True)
            worst = null_issues[0]
            severity = "high" if worst["pct"] > 10 else "medium" if worst["pct"] > 5 else "low"
            col_list = ", ".join(f'{n["column"]} ({n["pct"]}%)' for n in null_issues[:3])
            results.append({
                "type": "data_quality", "severity": severity,
                "title": f"Missing data in {len(null_issues)} column{'s' if len(null_issues) > 1 else ''}",
                "description": f"Found missing values in: {col_list}. Insights involving these columns may be incomplete.",
                "null_columns": null_issues,
                "suggested_question": "Give me a summary of the data quality",
            })
        total_cells = total_rows * len(all_cols)
        total_nulls = sum(n["count"] for n in null_issues) if null_issues else 0
        quality_pct = round((1 - total_nulls / total_cells) * 100, 1) if total_cells > 0 else 100
        results.append({
            "type": "data_quality_score", "severity": "low" if quality_pct >= 95 else "medium" if quality_pct >= 80 else "high",
            "title": f"Data quality: {quality_pct}%",
            "description": f"Across {total_rows:,} rows and {len(all_cols)} columns, {quality_pct}% of values are present and complete.",
            "quality_pct": quality_pct, "total_rows": total_rows, "total_columns": len(all_cols),
            "suggested_question": "Give me a plain-English summary",
        })
    except Exception as exc:
        logger.debug("Data quality check failed: %s", exc)
    return results


def _detect_correlations(conn, metrics, table_name):
    results = []
    check_metrics = metrics[:4]
    for i in range(len(check_metrics)):
        for j in range(i + 1, len(check_metrics)):
            col_a = check_metrics[i].get("column", "")
            col_b = check_metrics[j].get("column", "")
            if not col_a or not col_b:
                continue
            try:
                row = conn.execute(f'SELECT CORR("{col_a}", "{col_b}") AS correlation FROM "{table_name}"').fetchone()
                if row and row[0] is not None:
                    r = float(row[0])
                    if abs(r) > 0.7 and not math.isnan(r):
                        name_a = check_metrics[i].get("name", col_a).replace("_", " ")
                        name_b = check_metrics[j].get("name", col_b).replace("_", " ")
                        direction = "positive" if r > 0 else "negative"
                        results.append({
                            "type": "correlation", "severity": "low",
                            "title": f"Strong {direction} correlation found",
                            "description": f"{name_a.capitalize()} and {name_b} have a {'strong' if abs(r) > 0.85 else 'moderate'} {direction} correlation (r = {round(r, 2)}). {'When one increases, the other tends to increase too.' if r > 0 else 'When one increases, the other tends to decrease.'}",
                            "metric_a": check_metrics[i].get("name"), "metric_b": check_metrics[j].get("name"),
                            "correlation": round(r, 2),
                            "suggested_question": f"Compare {name_a} vs {name_b} over time",
                        })
            except Exception as exc:
                logger.debug("Correlation check failed: %s", exc)
    return results


def _fmt(val: float) -> str:
    abs_val = abs(val)
    if abs_val >= 1_000_000_000:
        return f"{val / 1_000_000_000:.1f}B"
    if abs_val >= 1_000_000:
        return f"{val / 1_000_000:.1f}M"
    if abs_val >= 1_000:
        return f"{val / 1_000:.1f}K"
    if abs_val >= 1:
        return f"{val:.0f}"
    return f"{val:.2f}"
```

---

## TASK 2: Create PII Detector (Backend)

Create NEW file `src/backend/services/pii_detector.py`:

```python
"""
PII detector for DataPulse. Scans columns for sensitive data patterns.
Flagged columns have sample_values excluded from LLM prompts.
"""

from __future__ import annotations

import re
import logging
from typing import Any

import duckdb

logger = logging.getLogger(__name__)

_EMAIL_RE = re.compile(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$')
_PHONE_RE = re.compile(r'^[\+]?[\d\s\-\(\)]{10,}$')
_AADHAAR_RE = re.compile(r'^\d{4}\s?\d{4}\s?\d{4}$')
_PAN_RE = re.compile(r'^[A-Z]{5}\d{4}[A-Z]$')


def _luhn_check(num_str: str) -> bool:
    digits = [int(d) for d in num_str if d.isdigit()]
    if len(digits) < 13 or len(digits) > 19:
        return False
    checksum = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        checksum += d
    return checksum % 10 == 0


def scan_for_pii(conn, schema, table_name="dataset", sample_size=100):
    flagged = []
    string_cols = [c["column"] for c in schema if "VARCHAR" in c["type"].upper() or "TEXT" in c["type"].upper()]
    for col_name in string_cols:
        try:
            rows = conn.execute(f'SELECT DISTINCT CAST("{col_name}" AS VARCHAR) AS val FROM "{table_name}" WHERE "{col_name}" IS NOT NULL LIMIT {sample_size}').fetchdf().to_dict(orient="records")
            values = [str(r["val"]).strip() for r in rows if r["val"]]
            if not values:
                continue
            total = len(values)
            email_m = sum(1 for v in values if _EMAIL_RE.match(v))
            if email_m > total * 0.3:
                flagged.append({"column": col_name, "pii_type": "email", "confidence": "high" if email_m > total * 0.7 else "medium", "match_pct": round(email_m / total * 100)})
                continue
            phone_m = sum(1 for v in values if _PHONE_RE.match(v))
            if phone_m > total * 0.3:
                flagged.append({"column": col_name, "pii_type": "phone_number", "confidence": "high" if phone_m > total * 0.7 else "medium", "match_pct": round(phone_m / total * 100)})
                continue
            cc_m = sum(1 for v in values if _luhn_check(v))
            if cc_m > total * 0.2:
                flagged.append({"column": col_name, "pii_type": "credit_card", "confidence": "high", "match_pct": round(cc_m / total * 100)})
                continue
            name_lower = col_name.lower()
            pii_hints = {"email": "email", "phone": "phone_number", "mobile": "phone_number", "ssn": "national_id", "aadhaar": "aadhaar", "pan": "pan_card", "passport": "national_id", "card_number": "credit_card", "account_number": "account"}
            for hint, pii_type in pii_hints.items():
                if hint in name_lower:
                    flagged.append({"column": col_name, "pii_type": pii_type, "confidence": "low", "match_pct": 0, "reason": "column_name_match"})
                    break
        except Exception as exc:
            logger.debug("PII scan failed for %s: %s", col_name, exc)
    return flagged


def sanitize_semantic_layer(semantic_layer, pii_columns):
    pii_col_names = {item["column"] for item in pii_columns}
    sanitized = dict(semantic_layer)
    for group_key in ["dimensions", "time_dimensions"]:
        new_group = []
        for item in sanitized.get(group_key, []):
            item_copy = dict(item)
            if item_copy.get("column") in pii_col_names:
                item_copy.pop("sample_values", None)
                item_copy["pii_redacted"] = True
            new_group.append(item_copy)
        sanitized[group_key] = new_group
    return sanitized
```

---

## TASK 3: Add Insights Endpoint to Dashboard Route

In `src/backend/routes/dashboard.py`:

1. Add import at top (after existing imports):
```python
from services.insights_engine import generate_insights
```

2. Add this endpoint BEFORE the `_safe_float` helper function at the bottom:

```python
@router.get("/api/insights/{session_id}")
async def get_insights(session_id: str) -> dict:
    """Proactive insights — anomalies, concentrations, trend reversals, data quality, correlations. All deterministic."""
    session = get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    try:
        insights = generate_insights(session["conn"], session["semantic_layer"])
    except Exception as exc:
        logger.warning("Insights generation failed: %s", exc)
        insights = []
    return {"insights": insights}
```

---

## TASK 4: Wire PII Detection into Upload

In `src/backend/routes/upload.py`:

1. Add import at top:
```python
from services.pii_detector import scan_for_pii, sanitize_semantic_layer
```

2. In `upload_dataset` function, AFTER `semantic_layer = await generate_semantic_layer(schema, sample, stats)` and BEFORE `create_session(...)`, add:
```python
    pii_columns = scan_for_pii(conn, schema)
    if pii_columns:
        semantic_layer = sanitize_semantic_layer(semantic_layer, pii_columns)
```

3. Add `"pii_columns": pii_columns,` to the return dict of `upload_dataset`.

4. Do the SAME two changes in the `load_sample` function: add pii scan after semantic layer generation, add pii_columns to return dict.

5. Add xlsx support. Change `_ALLOWED_EXTENSIONS`:
```python
_ALLOWED_EXTENSIONS = (".csv", ".tsv", ".xlsx")
```

6. In `upload_dataset`, replace the `conn.execute(f"CREATE TABLE {table_name} AS SELECT * FROM read_csv_auto('{tmp_path}')")` line with:
```python
    if file.filename.endswith(".xlsx"):
        import pandas as pd
        df = pd.read_excel(tmp_path, engine="openpyxl")
        conn.execute(f"CREATE TABLE {table_name} AS SELECT * FROM df")
    else:
        conn.execute(f"CREATE TABLE {table_name} AS SELECT * FROM read_csv_auto('{tmp_path}')")
```

7. Add `openpyxl>=3.1.0` to `requirements.txt`.

---

## TASK 5: Answer Verification in Query Pipeline

In `src/backend/services/query_pipeline.py`, in the `run_pipeline` function:

Find the comment `# Step 6: Metrics matching`. INSERT BEFORE it:

```python
    # Step 5b: Answer Verification — cross-check primary KPI against raw data
    verification_status = None
    if explainer_result.get("kpis") and intent != "change":
        try:
            first_kpi = explainer_result["kpis"][0]
            kpi_value = first_kpi.get("value")
            if kpi_value is not None and isinstance(kpi_value, (int, float)):
                primary_metric_col = None
                for m_name in analyst_result.get("relevant_metrics", []):
                    for m in semantic_layer.get("metrics", []):
                        if m.get("name") == m_name:
                            primary_metric_col = m.get("column")
                            break
                    if primary_metric_col:
                        break
                if primary_metric_col:
                    verify_result = conn.execute(f'SELECT SUM("{primary_metric_col}") FROM {table_name}').fetchone()
                    if verify_result and verify_result[0] is not None:
                        verified_total = float(verify_result[0])
                        if kpi_value != 0:
                            deviation = abs(verified_total - kpi_value) / abs(kpi_value)
                            verification_status = "verified" if deviation < 0.05 else "plausible"
                        else:
                            verification_status = "plausible"
        except Exception:
            verification_status = "skipped"
```

Add `"verification": verification_status,` to the return dict of `run_pipeline`.

In `src/backend/models/schemas.py`, add to `QueryResponse`:
```python
    verification: Optional[str] = None
```

---

## TASK 6: Conversation Context

### In `src/backend/models/schemas.py`:
Add field to `QuestionRequest`:
```python
    conversation_history: list[dict[str, Any]] = Field(
        default=[], description="Last 2-3 Q&A pairs for context resolution",
    )
```

### In `src/backend/routes/query.py`:
Add `conversation_history=req.conversation_history,` to the `run_pipeline(...)` call.

### In `src/backend/services/query_pipeline.py`:
1. Add `conversation_history: list[dict] | None = None,` parameter to `run_pipeline`.
2. Add `conversation_history: list[dict] | None = None,` parameter to `run_analyst`.
3. Pass it: where `run_analyst` is called inside `run_pipeline`, add `conversation_history`.
4. Inside `run_analyst`, build conversation context and inject into the prompt.

Before the prompt f-string in `run_analyst`, add:
```python
    conv_context = ""
    if conversation_history:
        conv_parts = []
        for entry in conversation_history[-3:]:
            conv_parts.append(f'  Q: "{entry.get("question", "")}"\n  -> Intent: {entry.get("intent", "unknown")}, Metrics: {entry.get("metrics", [])}')
        conv_context = "PREVIOUS CONVERSATION:\n" + "\n".join(conv_parts) + "\n\n"
```

In the prompt, add `{conv_context}` right before `USER QUESTION: "{question}"`.

Add instruction #6 to the INSTRUCTIONS list in the prompt:
```
6. If there is previous conversation context, resolve pronouns like "that", "it", "this" using the metrics and dimensions from previous questions.
```

---

## TASK 7: Frontend — Conversation History, Response Time, PII State

In `src/frontend/src/App.jsx`:

1. Add state: `const [conversationHistory, setConversationHistory] = useState([]);`

2. In `handleAsk`, after `setLoading(true);` add: `const startTime = Date.now();`

3. In the fetch body, add `conversation_history: conversationHistory.slice(-3),`

4. In the assistant message object, add after `verdict: data.verdict,`:
```jsx
          responseTime: ((Date.now() - startTime) / 1000).toFixed(1),
          verification: data.verification,
```

5. After the `setMessages` call for assistant role, add:
```jsx
        setConversationHistory((prev) => [...prev, {
          question,
          intent: data.intent,
          metrics: (data.metrics_used || []).map((m) => typeof m === "string" ? m : m.name),
        }]);
```

6. In the "New dataset" button onClick, add `setConversationHistory([]);`

---

## TASK 8: Frontend — Insights Feed and PII Banner on Dashboard

In `src/frontend/src/components/AutoDashboard.jsx`:

1. Add state: `const [insights, setInsights] = useState([]);`

2. In the useEffect that fetches dashboard, add after the story fetch:
```jsx
    fetch(`${API}/api/insights/${session.session_id}`)
      .then((r) => r.json())
      .then((d) => setInsights(d.insights || []))
      .catch(() => setInsights([]));
```

3. In the JSX, AFTER the semantic-banner section and BEFORE the data story section, add PII banner:
```jsx
        {session?.pii_columns?.length > 0 && (
          <div className="pii-banner">
            <div className="pii-banner-content">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--success)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
              <span><strong>{session.pii_columns.length} column{session.pii_columns.length > 1 ? "s" : ""} flagged as potentially sensitive</strong> — {session.pii_columns.map((p) => p.column).join(", ")}. Sample values excluded from AI prompts.</span>
            </div>
          </div>
        )}
```

4. AFTER the data story section and BEFORE Section B (KPI Cards), add insights feed:
```jsx
        {insights.length > 0 && (
          <section className="dash-section">
            <div className="dash-section-title" style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ fontSize: 16 }}>💡</span>
              Data Talks to You
              <span style={{ fontSize: 12, fontWeight: 400, color: "var(--text-3)", marginLeft: 4 }}>
                {insights.length} insight{insights.length !== 1 ? "s" : ""} found — pure statistics, no AI
              </span>
            </div>
            <div className="insights-grid">
              {insights.filter((ins) => ins.type !== "data_quality_score").map((insight, i) => (
                <div key={i} className={`insight-card insight-${insight.severity}`} style={{ animationDelay: `${i * 80}ms` }}>
                  <div className="insight-card-header">
                    <span>{insight.severity === "high" ? "⚠️" : insight.severity === "medium" ? "📊" : "💡"}</span>
                    <span className="insight-card-type">{insight.type.replace(/_/g, " ")}</span>
                  </div>
                  <div className="insight-card-title">{insight.title}</div>
                  <div className="insight-card-desc">{insight.description}</div>
                  {insight.suggested_question && (
                    <button className="insight-dive-btn" onClick={() => onStartChat(insight.suggested_question)}>Dive deeper →</button>
                  )}
                </div>
              ))}
            </div>
          </section>
        )}
        {insights.filter((ins) => ins.type === "data_quality_score").map((dq, i) => (
          <div key={i} className="data-quality-badge">
            <span className={`dq-score ${dq.quality_pct >= 95 ? "dq-good" : dq.quality_pct >= 80 ? "dq-ok" : "dq-bad"}`}>{dq.quality_pct}%</span>
            <span className="dq-label">Data Quality</span>
            <span className="dq-detail">{dq.description}</span>
          </div>
        ))}
```

5. Add CSS to `src/frontend/src/index.css`:

```css
/* Insights Feed */
.insights-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 12px; }
.insight-card { background: var(--surface); border: 1px solid var(--border); border-radius: var(--r); padding: 16px; animation: fadeSlideIn 400ms ease-out both; transition: box-shadow 0.15s; }
.insight-card:hover { box-shadow: var(--shadow-md); }
.insight-high { border-left: 3px solid var(--danger); }
.insight-medium { border-left: 3px solid var(--warning); }
.insight-low { border-left: 3px solid var(--info); }
.insight-card-header { display: flex; align-items: center; gap: 6px; margin-bottom: 6px; }
.insight-card-type { font-size: 10px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-3); }
.insight-card-title { font-size: 14px; font-weight: 600; color: var(--text); margin-bottom: 6px; line-height: 1.3; }
.insight-card-desc { font-size: 13px; color: var(--text-2); line-height: 1.5; margin-bottom: 10px; }
.insight-dive-btn { background: none; border: none; color: var(--primary); font-size: 13px; font-weight: 600; cursor: pointer; padding: 0; font-family: var(--font); }
.insight-dive-btn:hover { text-decoration: underline; }

/* PII Banner */
.pii-banner { display: flex; align-items: center; background: var(--success-bg); border: 1px solid rgba(15,123,63,0.15); border-radius: var(--r); padding: 12px 16px; margin-bottom: 16px; animation: fadeSlideIn 400ms ease-out; }
.pii-banner-content { display: flex; align-items: flex-start; gap: 10px; font-size: 13px; color: var(--text); line-height: 1.5; }

/* Data Quality Badge */
.data-quality-badge { display: flex; align-items: center; gap: 10px; padding: 10px 16px; background: var(--surface); border: 1px solid var(--border); border-radius: var(--r); margin-bottom: 16px; }
.dq-score { font-size: 18px; font-weight: 700; min-width: 48px; text-align: center; }
.dq-good { color: var(--success); }
.dq-ok { color: var(--warning); }
.dq-bad { color: var(--danger); }
.dq-label { font-size: 13px; font-weight: 600; color: var(--text); }
.dq-detail { font-size: 12px; color: var(--text-2); flex: 1; }
```

---

## TASK 9: Response Time + Verification Badges in Chat

In `src/frontend/src/components/ChatInterface.jsx`, find the trust-badges-row. ADD after the existing self-corrected badge:

```jsx
          {msg.verification && (
            <span className={`trust-badge ${msg.verification === "verified" ? "trust-badge-success" : "trust-badge-neutral"}`}>
              {msg.verification === "verified" ? (
                <><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><path d="M20 6L9 17l-5-5"/></svg> Answer verified</>
              ) : "Plausible result"}
            </span>
          )}
          {msg.responseTime && (
            <span className="trust-badge trust-badge-neutral">
              ⚡ {msg.responseTime}s
            </span>
          )}
```

---

## TASK 10: Fix Hardcoded Colors for Dark Mode

Search ALL `.jsx` files in `src/frontend/src/components/` for hardcoded hex colors in inline styles. Replace them:

| Hardcoded | Replace with |
|-----------|-------------|
| `"#1A1A2E"` | `"var(--text)"` |
| `"#6B7280"` | `"var(--text-2)"` |
| `"#9CA3AF"` | `"var(--text-3)"` |
| `"#374151"` | `"var(--text)"` |
| `"#FFFFFF"` | `"var(--surface)"` |
| `"#F3F4F6"` | `"var(--surface-2)"` |
| `"#E5E7EB"` | `"var(--border)"` |
| `"#42145F"` | `"var(--primary)"` |
| `"#F0ECFA"` | `"var(--primary-bg)"` |
| `"#FEF9EE"` | `"var(--warning-bg)"` |
| `"#FDE68A"` | `"var(--border)"` |
| `"#92400E"` | `"var(--warning)"` |
| `"#D4760A"` | `"var(--warning)"` |

Files to check: `ChatInterface.jsx`, `AutoDashboard.jsx`, `SemanticLayer.jsx`.

Do NOT change hex colors inside chart SVG components (ChartRenderer, AnimatedBar, AnimatedLine, AnimatedDonut, WaterfallChart) — Recharts needs raw hex for SVG fills.

---

## TASK 11: Final Verification

```bash
cd src/backend && python -c "from services.insights_engine import generate_insights; print('OK')"
cd src/backend && python -c "from services.pii_detector import scan_for_pii; print('OK')"
cd src/backend && python -c "from main import app; print('OK')"
cd src/frontend && npm run build
cd ../.. && pytest tests/ -v --tb=short
```

Then commit:
```bash
git add -A && git commit -s -m "feat: Data Talks to You — proactive insights, PII detection, answer verification, conversation context

- Insights Engine: anomaly detection, concentration risk, trend reversals,
  data quality scoring, correlation surfacing (all deterministic, zero LLM)
- PII Detector: email, phone, credit card, Aadhaar, PAN scanning with
  automatic sample_values redaction from LLM prompts
- Answer Verification: cross-checks KPI values against raw aggregation
- Conversation Context: last 3 Q&A pairs for pronoun resolution
- Response time badge, data quality score, metric tooltips
- Dark mode color fixes, Excel upload support"
```

---

## Critical Notes

- ALL insight computations MUST be deterministic — zero LLM calls in insights_engine.py
- The insights endpoint must complete in under 1 second for datasets up to 50K rows
- PII detection runs on upload, NOT on every query — it is a one-time scan
- Conversation history is capped at last 3 exchanges to avoid prompt bloat
- Max 8 insight cards displayed — more overwhelms users and defeats Clarity pillar
- Do NOT modify the three-agent pipeline logic beyond the verification step
