"""
Auto-dashboard route for DataPulse.

GET /api/dashboard/{session_id}

Returns pre-computed analytics for instant display after dataset upload:
  - KPI summary per metric (sum, min, max, avg)
  - Time trend (primary metric over time dimension)
  - Top dimension breakdown (primary metric by first categorical dimension)

All queries use direct SQL on the in-memory DuckDB connection — no LLM calls,
so the dashboard loads in under 1 second.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from utils.duckdb_manager import get_session
from utils.llm_client import generate
from services.insights_engine import generate_insights

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/api/dashboard/{session_id}")
async def get_dashboard(session_id: str) -> dict:
    """
    Return pre-computed dashboard data for a session.

    Runs SQL directly against DuckDB — no LLM involved — so it's instant.
    Errors in individual sections are silently skipped so the dashboard
    always returns something even on partial failures.
    """
    session = get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found.")

    conn = session["conn"]
    semantic = session["semantic_layer"]
    schema = session["schema"]
    filename = session.get("filename", "Dataset")
    row_count = session.get("row_count", 0)

    dashboard: dict = {
        "filename": filename,
        "row_count": row_count,
        "column_count": len(schema),
        "date_range": None,
        "kpis": [],
        "time_trend": None,
        "top_dimension": None,
    }

    metrics = semantic.get("metrics", [])
    time_dims = semantic.get("time_dimensions", [])
    dimensions = semantic.get("dimensions", [])

    # ── KPIs: one card per metric (SUM, MIN, MAX, AVG) ────────────────────
    seen_columns: set[str] = set()
    for metric in metrics:
        col = metric.get("column", "")
        if not col or col in seen_columns:
            continue
        seen_columns.add(col)
        try:
            row = conn.execute(f"""
                SELECT
                    SUM("{col}")   AS total,
                    MIN("{col}")   AS min_val,
                    MAX("{col}")   AS max_val,
                    AVG("{col}")   AS avg_val,
                    COUNT("{col}") AS count_val
                FROM dataset
            """).fetchone()
            dashboard["kpis"].append({
                "name": metric["name"],
                "description": metric.get("description", ""),
                "column": col,
                "total": _safe_float(row[0]),
                "min": _safe_float(row[1]),
                "max": _safe_float(row[2]),
                "avg": _safe_float(row[3]),
                "count": int(row[4] or 0),
                "sparkline": [],
            })
            # ── Sparkline: time-series values for this KPI ────────────────
            if time_dims:
                time_col = time_dims[0]["column"]
                try:
                    spark_rows = conn.execute(f"""
                        SELECT "{time_col}" AS period, SUM("{col}") AS value
                        FROM dataset
                        GROUP BY "{time_col}"
                        ORDER BY "{time_col}"
                    """).fetchdf().to_dict(orient="records")
                    dashboard["kpis"][-1]["sparkline"] = [
                        round(float(r["value"]), 2) for r in spark_rows
                    ]
                except Exception as spark_exc:
                    logger.debug("Sparkline query failed for '%s': %s", col, spark_exc)
        except Exception as exc:
            logger.warning("KPI query failed for column '%s': %s", col, exc)

    # ── Date range from time dimension ────────────────────────────────────
    if time_dims:
        time_col = time_dims[0]["column"]
        try:
            row = conn.execute(f"""
                SELECT MIN("{time_col}")::VARCHAR, MAX("{time_col}")::VARCHAR
                FROM dataset
            """).fetchone()
            if row and row[0]:
                dashboard["date_range"] = {"from": str(row[0]), "to": str(row[1])}
        except Exception as exc:
            logger.warning("Date range query failed: %s", exc)

    # ── Time trend: primary metric over time ──────────────────────────────
    # Use only metrics whose name starts with "total_" (the SUM variants from Fix A)
    sum_metrics = [m for m in metrics if m["name"].startswith("total_")]
    primary_metrics = sum_metrics if sum_metrics else metrics

    if time_dims and primary_metrics:
        time_col = time_dims[0]["column"]
        metric_col = primary_metrics[0]["column"]
        metric_name = primary_metrics[0]["name"]
        try:
            rows = conn.execute(f"""
                SELECT "{time_col}" AS period, SUM("{metric_col}") AS value
                FROM dataset
                GROUP BY "{time_col}"
                ORDER BY "{time_col}"
            """).fetchdf().to_dict(orient="records")
            dashboard["time_trend"] = {
                "time_column": time_col,
                "metric_name": metric_name,
                "metric_column": metric_col,
                "data": [
                    {"period": str(r["period"]), "value": _safe_float(r["value"])}
                    for r in rows
                ],
            }
        except Exception as exc:
            logger.warning("Time trend query failed: %s", exc)

    # ── Top dimension breakdown ───────────────────────────────────────────
    if dimensions and primary_metrics:
        dim_col = dimensions[0]["column"]
        dim_name = dimensions[0]["name"]
        metric_col = primary_metrics[0]["column"]
        metric_name = primary_metrics[0]["name"]
        try:
            rows = conn.execute(f"""
                SELECT "{dim_col}" AS dimension_value, SUM("{metric_col}") AS value
                FROM dataset
                GROUP BY "{dim_col}"
                ORDER BY value DESC
                LIMIT 8
            """).fetchdf().to_dict(orient="records")
            dashboard["top_dimension"] = {
                "dimension_column": dim_col,
                "dimension_name": dim_name,
                "metric_name": metric_name,
                "metric_column": metric_col,
                "data": [
                    {"label": str(r["dimension_value"]), "value": _safe_float(r["value"])}
                    for r in rows
                ],
            }
        except Exception as exc:
            logger.warning("Dimension breakdown query failed: %s", exc)

    return dashboard


@router.get("/api/story/{session_id}")
async def generate_story(session_id: str) -> dict:
    """
    Generate a plain-English data story (5 bullets) from the dataset using the LLM.

    Gathers summary statistics from DuckDB then asks the LLM to write
    a simple narrative that a non-technical reader can understand instantly.
    """
    session = get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found.")

    conn = session["conn"]
    semantic = session["semantic_layer"]

    stats_context: list[str] = []

    # Row count
    try:
        row_count = conn.execute("SELECT COUNT(*) FROM dataset").fetchone()[0]
        stats_context.append(f"Dataset has {row_count} rows.")
    except Exception:
        pass

    # Metrics: total, min, max, avg
    for metric in semantic.get("metrics", []):
        col = metric.get("column", "")
        if not col:
            continue
        try:
            result = conn.execute(f"""
                SELECT SUM("{col}"), MIN("{col}"), MAX("{col}"), AVG("{col}")
                FROM dataset
            """).fetchone()
            if result and result[0] is not None:
                stats_context.append(
                    f"Metric '{metric['name']}': total={round(float(result[0]), 2)}, "
                    f"min={round(float(result[1]), 2)}, max={round(float(result[2]), 2)}, "
                    f"avg={round(float(result[3]), 2)}"
                )
        except Exception:
            pass

    # Dimensions: top values by count
    for dim in semantic.get("dimensions", []):
        col = dim.get("column", "")
        if not col:
            continue
        try:
            rows = conn.execute(f"""
                SELECT "{col}", COUNT(*) AS cnt
                FROM dataset
                GROUP BY "{col}"
                ORDER BY cnt DESC
                LIMIT 5
            """).fetchdf().to_dict(orient="records")
            values = [f"{r[col]} ({r['cnt']})" for r in rows]
            stats_context.append(
                f"Dimension '{dim['name']}': top values: {', '.join(values)}"
            )
        except Exception:
            pass

    # Time range
    for td in semantic.get("time_dimensions", []):
        col = td.get("column", "")
        if not col:
            continue
        try:
            result = conn.execute(f"""
                SELECT MIN("{col}")::VARCHAR, MAX("{col}")::VARCHAR FROM dataset
            """).fetchone()
            if result and result[0]:
                stats_context.append(f"Time range: {result[0]} to {result[1]}")
        except Exception:
            pass

    # Top metric by top dimension
    metrics = semantic.get("metrics", [])
    dimensions = semantic.get("dimensions", [])
    if metrics and dimensions:
        m_col = metrics[0].get("column", "")
        d_col = dimensions[0].get("column", "")
        if m_col and d_col:
            try:
                rows = conn.execute(f"""
                    SELECT "{d_col}", SUM("{m_col}") AS total
                    FROM dataset
                    GROUP BY "{d_col}"
                    ORDER BY total DESC
                    LIMIT 3
                """).fetchdf().to_dict(orient="records")
                breakdown = [f"{r[d_col]}: {round(float(r['total']), 1)}" for r in rows]
                stats_context.append(
                    f"Top {dimensions[0]['name']} by {metrics[0]['name']}: "
                    f"{', '.join(breakdown)}"
                )
            except Exception:
                pass

    if not stats_context:
        return {"story": ["Dataset loaded. Start exploring with a question."]}

    stats_text = "\n".join(stats_context)

    prompt = f"""You are explaining a dataset to someone who has never seen a spreadsheet before.
Write exactly 5 bullet points about this data. Each bullet should be one clear, simple finding.

Rules:
- Use plain language a 10-year-old could understand
- Every bullet must reference a specific number from the data
- Highlight anything surprising, unusual, or important with \u26a0
- Do NOT use jargon (no "YoY", "KPIs", "aggregation", "metrics")
- Start each bullet with a simple subject ("The South region...", "Loan applications...", "The busiest month...")
- Final bullet should be the most important takeaway or a warning

Here is the data summary:
{stats_text}

Return ONLY the 5 bullets, each starting with \u2022. No intro text, no conclusion."""

    try:
        story_text = generate(prompt)
        bullets = [
            b.strip().lstrip("\u2022").strip()
            for b in story_text.split("\n")
            if b.strip().startswith("\u2022")
        ]
        if not bullets:
            # Fallback: take any non-empty lines
            bullets = [b.strip() for b in story_text.split("\n") if b.strip() and len(b.strip()) > 10][:5]
    except Exception as exc:
        logger.warning("Story generation failed: %s", exc)
        bullets = ["Story could not be generated. Ask a question to explore your data."]

    return {"story": bullets}


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


def _safe_float(val) -> float:
    """Convert a value to float safely, returning 0.0 on failure."""
    try:
        return round(float(val or 0), 2)
    except (TypeError, ValueError):
        return 0.0
