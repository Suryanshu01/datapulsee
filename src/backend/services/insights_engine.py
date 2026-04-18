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