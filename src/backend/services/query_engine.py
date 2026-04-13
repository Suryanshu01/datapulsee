"""
NL→SQL query pipeline for DataPulse.

This module is the core of DataPulse's intelligence.  Given a natural language
question, a dataset schema, and a semantic layer, it:

  1. Calls Gemini to detect the question's *intent* and generate a DuckDB SQL query.
  2. Executes the SQL against the in-memory DuckDB connection.
  3. If execution fails, sends the error back to Gemini for one self-correction attempt.
  4. Returns the result DataFrame, the final SQL, the intent, chart hints, and a
     flag indicating whether a retry was needed.

The retry flag feeds directly into the confidence indicator on the frontend —
a query that needed correction gets lower confidence than one that ran first time.

Intent categories (mapped to the 4 NatWest use cases):
  - change     : "Why did X change?" — driver analysis
  - compare    : "A vs B" — side-by-side metrics
  - breakdown  : "What makes up X?" — decomposition by dimension
  - summary    : "Give me a weekly summary" — aggregated trends
  - general    : catch-all for anything else
"""

from __future__ import annotations

import json
import logging

import duckdb
import pandas as pd
from fastapi import HTTPException

from utils.gemini_client import generate, strip_markdown_fences

logger = logging.getLogger(__name__)

# Mode → intent hint injected into the Gemini prompt so that explicit mode
# selection on the frontend biases the query strategy appropriately.
_MODE_HINTS: dict[str, str] = {
    "change": (
        "Focus on identifying what changed between periods. "
        "Compare values over time and highlight the biggest movers."
    ),
    "compare": (
        "Focus on side-by-side comparison between groups or time periods. "
        "Return both values and the delta/percentage difference."
    ),
    "breakdown": (
        "Decompose the total into its constituent parts using GROUP BY. "
        "Surface the top contributors and any outliers."
    ),
    "summary": (
        "Produce a concise aggregate summary covering trends, anomalies, and shifts. "
        "Use time-based aggregation where a date column exists."
    ),
    "auto": "Choose the most appropriate analysis strategy for the question.",
}


def detect_intent_and_plan(
    question: str,
    schema: list[dict],
    semantic_layer: dict,
    table_name: str,
    mode: str,
) -> dict:
    """
    Use Gemini to classify question intent and generate a DuckDB SQL query.

    Returns a dict with keys: intent, sql, explanation_of_query,
    chart_type, chart_config.  Raises HTTP 500 if Gemini's response
    cannot be parsed as JSON.
    """
    mode_hint = _MODE_HINTS.get(mode, _MODE_HINTS["auto"])

    prompt = f"""You are a data analyst assistant helping a business user query their dataset.

Dataset table name: "{table_name}"
Column schema: {json.dumps(schema)}
Semantic layer (metric and dimension definitions): {json.dumps(semantic_layer)}

User question: "{question}"
Analysis mode hint: {mode_hint}

Your task:
1. Classify the question intent as one of: change | compare | breakdown | summary | general
2. Write a correct DuckDB SQL query to answer the question

Return ONLY valid JSON (no markdown fences) with this structure:
{{
  "intent": "change|compare|breakdown|summary|general",
  "sql": "SELECT ... FROM \"{table_name}\" ...",
  "explanation_of_query": "One sentence: what this SQL does in plain English",
  "chart_type": "bar|line|pie|table|number",
  "chart_config": {{"x": "column_name", "y": "column_name", "group_by": "optional_column_or_null"}}
}}

SQL rules:
- Always double-quote column names: "column_name"
- Use the exact column names from the schema — do not invent columns
- For temporal analysis, detect and use date/month/year columns automatically
- For breakdowns, always include a GROUP BY clause
- For comparisons, use CASE WHEN or self-joins as appropriate
- Keep queries simple and correct — prefer a working simple query over a clever broken one
- Limit result rows to 50 unless the question explicitly asks for more"""

    raw = generate(prompt)
    cleaned = strip_markdown_fences(raw)

    try:
        plan = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Could not parse Gemini's query plan as JSON: {exc}. Raw: {cleaned[:300]}",
        )

    return plan


def execute_query(
    conn: duckdb.DuckDBPyConnection,
    sql: str,
    schema: list[dict],
    table_name: str,
) -> tuple[pd.DataFrame, str, bool]:
    """
    Execute *sql* against *conn*.  On failure, ask Gemini to fix the SQL and retry once.

    Returns
    -------
    result_df : pd.DataFrame
        Query results.
    final_sql : str
        The SQL that actually ran (may differ from *sql* if a retry occurred).
    retried : bool
        True if the first attempt failed and a corrected query was used.
    """
    try:
        result_df = conn.execute(sql).fetchdf()
        return result_df, sql, False
    except Exception as first_error:  # noqa: BLE001
        logger.warning("SQL execution failed, attempting self-correction. Error: %s", first_error)
        fixed_sql = _fix_sql(sql, str(first_error), schema, table_name)
        try:
            result_df = conn.execute(fixed_sql).fetchdf()
            return result_df, fixed_sql, True
        except Exception as second_error:  # noqa: BLE001
            raise HTTPException(
                status_code=500,
                detail=(
                    f"Query failed after self-correction attempt. "
                    f"Original error: {first_error}. "
                    f"Retry error: {second_error}"
                ),
            )


def _fix_sql(
    broken_sql: str,
    error_message: str,
    schema: list[dict],
    table_name: str,
) -> str:
    """
    Ask Gemini to produce a corrected SQL given the broken query and its error.

    Returns the corrected SQL string.
    """
    prompt = f"""A DuckDB SQL query failed. Fix it so it runs correctly.

Failed query:
{broken_sql}

Error message:
{error_message}

Table: "{table_name}"
Schema: {json.dumps(schema)}

Return ONLY the corrected SQL query — no explanations, no markdown fences, just the SQL."""

    raw = generate(prompt)
    # Strip any accidental fences or "sql" prefix
    fixed = raw.strip().lstrip("`").rstrip("`")
    if fixed.lower().startswith("sql\n"):
        fixed = fixed[4:]
    return fixed.strip()


def compute_confidence(
    retried: bool,
    rows_returned: int,
    metrics_matched: list[str],
) -> tuple[str, str]:
    """
    Derive a confidence level for the answer from three signals.

    Signals and their weight:
      - retried         : SQL needed self-correction → lowers confidence
      - metrics_matched : named semantic-layer metrics found in the question → raises confidence
      - rows_returned   : very few rows may indicate a partial or wrong query

    Returns (level, reason) where level is "high" | "medium" | "low".
    """
    has_metric_match = len(metrics_matched) >= 1
    sufficient_rows = rows_returned >= 10
    few_rows = rows_returned < 3

    if not retried and has_metric_match and sufficient_rows:
        return (
            "high",
            "Exact metric match, query succeeded on first attempt, and sufficient data was returned.",
        )

    if retried and few_rows:
        return (
            "low",
            "Query required self-correction and returned very few rows — results may be incomplete.",
        )

    # Everything else is medium
    reasons = []
    if retried:
        reasons.append("query needed self-correction")
    if not has_metric_match:
        reasons.append("no named metric directly matched")
    if not sufficient_rows and not few_rows:
        reasons.append("limited rows returned")
    reason_str = "; ".join(reasons) if reasons else "results look plausible"
    return "medium", f"Moderate confidence — {reason_str}."


def find_matched_metrics(question: str, semantic_layer: dict) -> list[str]:
    """
    Return the names of semantic-layer metrics whose names appear in *question*.

    This is a simple keyword match — good enough to power the confidence
    indicator and the 'Metrics Used' display in the TransparencyPanel.
    """
    question_lower = question.lower()
    matched = []
    for metric in semantic_layer.get("metrics", []):
        name_lower = metric.get("name", "").lower()
        # Match if any word in the metric name appears in the question
        if any(word in question_lower for word in name_lower.split() if len(word) > 3):
            matched.append(metric["name"])
    return matched
