"""
Two-agent query pipeline for DataPulse.

Inspired by Azure SQL Blog's "Collaborating Agents" pattern:
  Agent 1 (Analyst)    — intent detection + schema selection
  Agent 2 (SQL Writer) — generates DuckDB SQL using only relevant columns
  Agent 3 (Explainer)  — produces explanation, KPIs, chart config, follow-ups

This separation dramatically improves SQL quality because Agent 2 sees
only the relevant columns, reducing hallucination of non-existent fields.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import duckdb
import pandas as pd
from fastapi import HTTPException

from config import VALID_INTENTS, SQL_RETRY_LIMIT
from utils.llm_client import generate, strip_markdown_fences
from utils.sql_sanitizer import sanitize_sql
from services.driver_analysis import (
    auto_detect_periods,
    run_multi_dimension_analysis,
)

logger = logging.getLogger(__name__)


# ── Agent 1: The Analyst ──────────────────────────────────────────────────

def run_analyst(
    question: str,
    semantic_layer: dict[str, Any],
    mode: str,
    conversation_history: list[dict] | None = None,
) -> dict[str, Any]:
    """
    Agent 1 classifies intent, selects relevant metrics/dimensions, and
    creates a query plan. If the question is ambiguous, it returns a
    clarification request instead.

    Returns dict with keys:
      intent, relevant_metrics, relevant_dimensions, time_dimension,
      plan, needs_clarification, clarification_question, clarification_options
    """
    mode_hints = {
        "change": "The user explicitly wants to understand what changed over time.",
        "compare": "The user explicitly wants a side-by-side comparison.",
        "breakdown": "The user explicitly wants to decompose totals into parts.",
        "summary": "The user explicitly wants a high-level summary with trends.",
        "auto": "Choose the best analysis strategy for this question.",
    }
    mode_hint = mode_hints.get(mode, mode_hints["auto"])

    conv_context = ""
    if conversation_history:
        conv_parts = []
        for entry in conversation_history[-3:]:
            conv_parts.append(f'  Q: "{entry.get("question", "")}"\n  -> Intent: {entry.get("intent", "unknown")}, Metrics: {entry.get("metrics", [])}')
        conv_context = "PREVIOUS CONVERSATION:\n" + "\n".join(conv_parts) + "\n\n"

    prompt = f"""You are Agent 1 (The Analyst) in a two-agent data analysis pipeline.

Your job: understand the user's question, pick the right metrics and dimensions from the semantic layer, and create a plan for the SQL Writer agent.

SEMANTIC LAYER:
{json.dumps(semantic_layer, indent=2)}

USER QUESTION: "{question}"
MODE HINT: {mode_hint}

{conv_context}INSTRUCTIONS:
1. Classify the intent as one of: change | compare | breakdown | summary | general
2. Select ONLY the metrics and dimensions relevant to answering this question
3. Identify the time dimension if the question involves temporal analysis
4. Write a clear plan describing what SQL should compute
5. If the question is ambiguous (e.g. "best product" - best by what?), set needs_clarification to true and provide a clarifying question with 2-4 clickable options
6. If there is previous conversation context, resolve pronouns like "that", "it", "this" using the metrics and dimensions from previous questions.

Return ONLY valid JSON (no markdown fences):
{{
  "intent": "change|compare|breakdown|summary|general",
  "relevant_metrics": ["metric_name_1", "metric_name_2"],
  "relevant_dimensions": ["dimension_name_1"],
  "time_dimension": "time_dim_name_or_null",
  "plan": "Clear description of what the SQL should compute",
  "needs_clarification": false,
  "clarification_question": null,
  "clarification_options": null
}}

If needs_clarification is true, return:
{{
  "intent": "general",
  "relevant_metrics": [],
  "relevant_dimensions": [],
  "time_dimension": null,
  "plan": null,
  "needs_clarification": true,
  "clarification_question": "Best by which metric?",
  "clarification_options": ["Revenue", "Units Sold", "Growth Rate"]
}}"""

    raw = generate(prompt)
    cleaned = strip_markdown_fences(raw)

    try:
        result = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        logger.warning("Analyst agent returned invalid JSON: %s", cleaned[:300])
        raise HTTPException(
            status_code=500,
            detail=f"Analyst agent returned invalid JSON: {exc}",
        )

    # Validate intent
    if result.get("intent") not in VALID_INTENTS:
        result["intent"] = "general"

    result.setdefault("needs_clarification", False)
    result.setdefault("relevant_metrics", [])
    result.setdefault("relevant_dimensions", [])
    result.setdefault("time_dimension", None)

    return result


# ── Agent 2: The SQL Writer ───────────────────────────────────────────────

def _build_relevant_schema(
    full_schema: list[dict],
    semantic_layer: dict[str, Any],
    analyst_result: dict[str, Any],
) -> list[dict]:
    """
    Build a focused schema containing only columns relevant to the analyst's plan.
    This reduces context for the SQL Writer, improving accuracy.
    """
    relevant_columns: set[str] = set()

    # Add columns from relevant metrics
    for metric_name in analyst_result.get("relevant_metrics", []):
        for m in semantic_layer.get("metrics", []):
            if m.get("name") == metric_name:
                relevant_columns.add(m.get("column", ""))

    # Add columns from relevant dimensions
    for dim_name in analyst_result.get("relevant_dimensions", []):
        for d in semantic_layer.get("dimensions", []):
            if d.get("name") == dim_name:
                relevant_columns.add(d.get("column", ""))

    # Add time dimension column
    time_dim = analyst_result.get("time_dimension")
    if time_dim:
        for td in semantic_layer.get("time_dimensions", []):
            if td.get("name") == time_dim:
                relevant_columns.add(td.get("column", ""))
        # Also check regular dimensions for backward compat
        for d in semantic_layer.get("dimensions", []):
            if d.get("name") == time_dim:
                relevant_columns.add(d.get("column", ""))

    # Filter full schema to only relevant columns
    # If nothing matched (e.g. bad metric names), fall back to full schema
    filtered = [col for col in full_schema if col["column"] in relevant_columns]
    return filtered if filtered else full_schema


def run_sql_writer(
    plan: str,
    relevant_schema: list[dict],
    table_name: str,
    semantic_layer: dict[str, Any],
    intent: str,
) -> str:
    """
    Agent 2 generates a DuckDB SQL query based on the analyst's plan
    and only the relevant columns' schema.

    Returns a SQL string.
    """
    # Include sample values from semantic layer for better WHERE clauses
    schema_with_context = []
    for col in relevant_schema:
        col_info = dict(col)
        col_name = col["column"]
        # Enrich with sample values from dimensions
        for d in semantic_layer.get("dimensions", []):
            if d.get("column") == col_name and "sample_values" in d:
                col_info["sample_values"] = d["sample_values"]
        for td in semantic_layer.get("time_dimensions", []):
            if td.get("column") == col_name and "sample_values" in td:
                col_info["sample_values"] = td["sample_values"]
        schema_with_context.append(col_info)

    # Enrich schema_with_context with metric expr so the SQL Writer
    # can use the exact aggregation expressions from the semantic layer.
    metric_exprs = {
        m["column"]: m["expr"]
        for m in semantic_layer.get("metrics", [])
        if "column" in m and "expr" in m
    }
    for col_info in schema_with_context:
        if col_info["column"] in metric_exprs:
            col_info["metric_expr"] = metric_exprs[col_info["column"]]

    prompt = f"""You are a DuckDB SQL expert. You generate SQL queries based on the user's request and the provided schema.

CRITICAL RULES — FOLLOW EVERY ONE:
1. ALWAYS use double quotes around column names: SELECT "region", SUM("disbursed_amount") FROM dataset
2. When the user asks about totals, sums, averages, counts, or any aggregate concept, you MUST use GROUP BY with the appropriate aggregation function (SUM, AVG, COUNT, MIN, MAX).
3. NEVER return raw metric columns without aggregation when a dimension is also selected. If you SELECT a dimension (like "region") AND a metric (like "disbursed_amount"), you MUST aggregate the metric and GROUP BY the dimension.
4. When asked for "top N", ALWAYS aggregate first, then ORDER BY the aggregate DESC, then LIMIT N.
5. For time-based questions, use the time dimension column for GROUP BY and ORDER BY.
6. Use the metric expressions from the semantic layer. If the semantic layer says expr is SUM("disbursed_amount"), use exactly that expression.
7. ALWAYS alias aggregated columns with AS: SUM("disbursed_amount") AS total_disbursed_amount
8. Return ONLY the SQL query. No markdown, no backticks, no explanation. Just raw SQL.

CORRECT EXAMPLES:
- "Top 5 regions by revenue" → SELECT "region", SUM("revenue") AS total_revenue FROM dataset GROUP BY "region" ORDER BY total_revenue DESC LIMIT 5
- "Average score by category" → SELECT "category", AVG("score") AS avg_score FROM dataset GROUP BY "category" ORDER BY avg_score DESC
- "Monthly trend of sales" → SELECT "month", SUM("sales") AS total_sales FROM dataset GROUP BY "month" ORDER BY "month"
- "Total by product type" → SELECT "product_type", SUM("amount") AS total_amount FROM dataset GROUP BY "product_type" ORDER BY total_amount DESC

WRONG (NEVER DO THIS):
- SELECT "region", "revenue" FROM dataset ORDER BY "revenue" DESC LIMIT 5  ← MISSING GROUP BY AND AGGREGATION
- SELECT * FROM dataset LIMIT 10  ← TOO GENERIC, NO AGGREGATION

The table name is: {table_name}
The schema is: {json.dumps(schema_with_context)}
The analysis plan is: {plan}
The intent is: {intent}"""

    raw = generate(prompt)
    # Strip any accidental fences
    sql = strip_markdown_fences(raw).strip()
    if sql.lower().startswith("sql"):
        sql = sql[3:].strip()
    return sql


def execute_with_retry(
    conn: duckdb.DuckDBPyConnection,
    sql: str,
    relevant_schema: list[dict],
    table_name: str,
    semantic_layer: dict[str, Any],
    intent: str,
    plan: str,
) -> tuple[pd.DataFrame, str, bool]:
    """
    Execute SQL with up to SQL_RETRY_LIMIT self-correction attempts.

    Returns (dataframe, final_sql, retried_flag).
    """
    last_sql = sql
    for attempt in range(SQL_RETRY_LIMIT + 1):
        try:
            result_df = conn.execute(last_sql).fetchdf()
            return result_df, last_sql, attempt > 0
        except Exception as err:
            if attempt < SQL_RETRY_LIMIT:
                logger.warning(
                    "SQL attempt %d failed: %s. Retrying...", attempt + 1, err
                )
                last_sql = _fix_sql(
                    last_sql, str(err), relevant_schema, table_name
                )
            else:
                raise HTTPException(
                    status_code=500,
                    detail=f"Query failed after {SQL_RETRY_LIMIT + 1} attempts: {err}",
                )

    # Should not reach here, but satisfy type checker
    raise HTTPException(status_code=500, detail="Query execution failed unexpectedly")


def _fix_sql(
    broken_sql: str,
    error_message: str,
    schema: list[dict],
    table_name: str,
) -> str:
    """Ask the LLM to fix broken SQL given the error message."""
    prompt = f"""A DuckDB SQL query failed. Fix it.

FAILED QUERY:
{broken_sql}

ERROR:
{error_message}

TABLE: "{table_name}"
COLUMNS: {json.dumps(schema)}

Return ONLY the corrected SQL. No explanations, no markdown fences."""

    raw = generate(prompt)
    fixed = strip_markdown_fences(raw).strip()
    if fixed.lower().startswith("sql"):
        fixed = fixed[3:].strip()
    return fixed


# ── Fix C: Post-Execution Validation ─────────────────────────────────────

def validate_query_result(sql: str, data: list[dict], columns: list[str]) -> dict:
    """
    Check if the query result looks reasonable.

    Detects duplicate dimension values — the classic sign of a missing GROUP BY.
    If duplicates are found, the caller should retry with a corrected prompt.
    """
    issues = []

    for col in columns:
        values = [row[col] for row in data if row.get(col) is not None]
        if len(values) != len(set(str(v) for v in values)):
            issues.append(
                f"Column '{col}' has duplicate values. The query may be missing GROUP BY."
            )

    return {"valid": len(issues) == 0, "issues": issues}


def _fix_sql_aggregation(
    broken_sql: str,
    schema: list[dict],
    table_name: str,
    plan: str,
) -> str:
    """
    Ask the LLM to add GROUP BY and aggregation to a query that returned
    duplicate dimension values.
    """
    prompt = f"""The previous SQL query returned duplicate values in a dimension column.
This means it is missing GROUP BY and aggregation. Fix it.

FAILED QUERY:
{broken_sql}

PROBLEM: The query returns individual rows instead of aggregated groups.
You MUST:
1. Add SUM() or AVG() around every numeric column that is a metric
2. Add GROUP BY for every non-aggregated (dimension) column
3. Add ORDER BY the aggregated value DESC
4. Keep LIMIT if present

TABLE: "{table_name}"
SCHEMA: {json.dumps(schema)}
ORIGINAL PLAN: {plan}

Return ONLY the corrected SQL. No markdown, no backticks."""

    raw = generate(prompt)
    fixed = strip_markdown_fences(raw).strip()
    if fixed.lower().startswith("sql"):
        fixed = fixed[3:].strip()
    return fixed


# ── Agent 3: The Explainer ────────────────────────────────────────────────

def run_explainer(
    question: str,
    sql: str,
    result_data: list[dict],
    intent: str,
    semantic_layer: dict[str, Any],
    result_columns: list[str],
    driver_analysis: dict | None = None,
    simple_mode: bool = True,
) -> dict[str, Any]:
    """
    Agent 3 generates a structured explanation with KPIs, chart config,
    insight line, and follow-up suggestions.

    Returns dict with keys:
      explanation, insight_line, chart_type, chart_config, kpis, follow_ups
    """
    sample_rows = result_data[:20]

    intent_guidance = {
        "change": "Focus on what changed, by how much, and the likely driver. Use a waterfall or bar chart.",
        "compare": "Highlight differences between groups. Use grouped bars for comparison.",
        "breakdown": "Show composition and proportions. Use a donut chart or stacked bar.",
        "summary": "Provide dashboard-level overview. Suggest KPI cards with sparklines.",
        "general": "Choose the most informative visualization for this data.",
    }

    driver_context = ""
    if driver_analysis and driver_analysis.get("best_dimension"):
        best_dim = driver_analysis["best_dimension"]
        best_result = driver_analysis["results"].get(best_dim, {})
        driver_context = f"""
DRIVER ANALYSIS RESULTS (these are computed mathematically, not estimated — use these exact numbers):
{json.dumps(best_result, indent=2)}

When explaining "why" something changed, reference the driver analysis numbers directly.
Example: "South region contributed 60% of the decline (-₹6K), making it the primary driver."
DO NOT invent numbers. Use only the numbers from the driver analysis above.
"""

    if simple_mode:
        tone_instruction = """
TONE — Use VERY simple language. Imagine explaining to a 10-year-old child.
- No jargon, no abbreviations, no technical terms
- Use words like "more", "less", "biggest", "smallest", "growing", "falling"
- Example: Instead of "Revenue declined 22% MoM" say "The money coming in went down by about a fifth compared to last month"
"""
    else:
        tone_instruction = """
TONE — Use precise business language with specific numbers.
Include percentages, absolute values, and period comparisons.
Use standard business terminology (YoY, MoM, default rate, disbursement, etc.)
"""

    verdict_instruction = ""
    if intent == "compare":
        verdict_instruction = """
Also include a "verdict" field: a single sentence declaring which item leads and by how much.
Example: "North processes loans 3 days faster than South, but approves 12% fewer applications."
Keep it factual — reference specific numbers from the data.
"""

    prompt = f"""You are Agent 3 (The Explainer) in a data analysis pipeline.
Your job: explain the query results to a non-technical business user and suggest the best visualization.

ORIGINAL QUESTION: "{question}"
INTENT: {intent}
SQL USED: {sql}
RESULT COLUMNS: {json.dumps(result_columns)}
RESULTS (first 20 rows): {json.dumps(sample_rows)}
SEMANTIC LAYER CONTEXT: {json.dumps(semantic_layer.get("data_summary", ""))}
{driver_context}
GUIDANCE: {intent_guidance.get(intent, intent_guidance["general"])}
{tone_instruction}
{verdict_instruction}
Return ONLY valid JSON (no markdown fences):
{{
  "explanation": "3-5 sentences explaining the results in plain English. Be specific with numbers.",
  "insight_line": "One bold sentence summarizing the KEY finding (max 15 words)",
    "action_insight": "ACTION: Consider... (one actionable sentence under 20 words, specific to the data)",
  "verdict": "null or one sentence declaring a winner with specific numbers (compare intent only)",
  "chart_type": "bar|grouped_bar|line|area|donut|kpi|waterfall|table",
  "chart_config": {{
    "x": "column_for_x_axis",
    "y": "column_for_y_axis",
    "group_by": "optional_grouping_column_or_null"
  }},
  "kpis": [
    {{
      "label": "Metric Name",
      "value": 12400,
      "formatted": "12.4K",
      "delta": -22,
      "delta_label": "vs last period"
    }}
  ],
  "follow_ups": [
    "Suggested follow-up question 1",
    "Suggested follow-up question 2",
    "Suggested follow-up question 3"
  ]
}}

Rules for action_insight:
- Start with "ACTION: Consider..." or "ACTION: This suggests..." or "ACTION: Look into..."
- Be specific to the data — reference an actual number or group
- Must be actionable (something the user can do)
- Keep it under 20 words
- Bad: "ACTION: Keep monitoring the data" (too vague)
- Good: "ACTION: Consider tightening approval criteria in South — default rates are 2x the average"

CHART SELECTION RULES:
- "change" intent -> "waterfall" or "bar" (show drivers of change)
- "compare" intent -> "grouped_bar" (side-by-side)
- "breakdown" intent -> "donut" or "bar" (composition)
- "summary" intent -> "kpi" (dashboard cards with sparklines)
- Time series data -> "line" or "area"
- Single number result -> "kpi"
- If unsure, default to "bar"

KPI RULES:
- Extract 2-4 key numbers from the results
- Always include delta (% change) if time comparison is possible
- Format large numbers: 1000 -> "1K", 100000 -> "100K", 1000000 -> "1M"
- For Indian context use: lakhs (L) and crores (Cr)

FOLLOW-UP RULES:
- Suggest exactly 3 natural next questions based on the results
- Make them specific to the data, not generic
- Examples: "Why did South region drop?", "Compare by product type", "Show monthly trend"

IMPORTANT:
- chart_config x and y MUST be actual column names from RESULT COLUMNS
- If result has only 1 row and 1 column, chart_type should be "kpi"
- Always include at least 1 KPI"""

    raw = generate(prompt)
    cleaned = strip_markdown_fences(raw)

    try:
        result = json.loads(cleaned)
    except json.JSONDecodeError:
        logger.warning("Explainer returned invalid JSON, using fallback")
        return _fallback_explanation(result_data, result_columns, intent)

    # Validate chart config columns exist in results
    config = result.get("chart_config", {})
    if config.get("x") and config["x"] not in result_columns:
        config["x"] = result_columns[0] if result_columns else None
    if config.get("y") and config["y"] not in result_columns:
        config["y"] = result_columns[-1] if len(result_columns) > 1 else result_columns[0] if result_columns else None
    result["chart_config"] = config

    result.setdefault("explanation", "Results retrieved successfully.")
    result.setdefault("insight_line", "")
    result.setdefault("action_insight", None)
    result.setdefault("verdict", None)
    result.setdefault("chart_type", "table")
    result.setdefault("kpis", [])
    result.setdefault("follow_ups", [])

    # Normalize "null" string to None for verdict
    if result.get("verdict") in ("null", "None", ""):
        result["verdict"] = None

    return result


def _fallback_explanation(
    result_data: list[dict],
    result_columns: list[str],
    intent: str,
) -> dict[str, Any]:
    """Return a safe fallback when the Explainer agent fails."""
    chart_type = "table"
    config: dict[str, Any] = {}

    if len(result_data) == 1 and len(result_columns) == 1:
        chart_type = "kpi"
    elif len(result_columns) >= 2:
        chart_type = "bar"
        config = {"x": result_columns[0], "y": result_columns[-1]}

    return {
        "explanation": "Results retrieved successfully. See the data below for details.",
        "insight_line": "",
        "chart_type": chart_type,
        "chart_config": config,
        "kpis": [],
        "follow_ups": [],
    }


# ── Pipeline Orchestrator ─────────────────────────────────────────────────

def run_pipeline(
    question: str,
    schema: list[dict],
    semantic_layer: dict[str, Any],
    table_name: str,
    mode: str,
    conn: duckdb.DuckDBPyConnection,
    total_rows_in_dataset: int,
    simple_mode: bool = True,
    conversation_history: list[dict] | None = None,
) -> dict[str, Any]:
    """
    Run the full three-agent pipeline:
      1. Analyst -> intent + relevant schema
      2. SQL Writer -> DuckDB query
      3. SQL Sanitizer -> safety validation
      4. Execute query
      5. Explainer -> explanation + KPIs + chart + follow-ups

    Returns a complete response dict ready for the API.
    """
    # Step 1: Analyst
    analyst_result = run_analyst(question, semantic_layer, mode, conversation_history=conversation_history)

    # Handle disambiguation
    if analyst_result.get("needs_clarification"):
        return {
            "needs_clarification": True,
            "clarification_question": analyst_result.get("clarification_question", "Could you be more specific?"),
            "clarification_options": analyst_result.get("clarification_options", []),
            "intent": analyst_result.get("intent", "general"),
        }

    intent = analyst_result["intent"]
    plan = analyst_result.get("plan", question)

    # Step 2: Build focused schema for SQL Writer
    relevant_schema = _build_relevant_schema(schema, semantic_layer, analyst_result)

    # Step 3: SQL Writer
    sql = run_sql_writer(plan, relevant_schema, table_name, semantic_layer, intent)

    # Step 3b: SQL Sanitizer — validate before execution
    query_validated = False
    validation = sanitize_sql(sql)
    if not validation["safe"]:
        logger.warning("SQL sanitizer blocked query: %s. Retrying.", validation["reason"])
        retry_prompt = f"Your previous SQL was blocked for safety: {validation['reason']}. Generate a safe SELECT-only query. Original plan: {plan}"
        sql = run_sql_writer(retry_prompt, relevant_schema, table_name, semantic_layer, intent)
        validation = sanitize_sql(sql)
        if not validation["safe"]:
            raise HTTPException(
                status_code=400,
                detail=f"Could not generate safe query: {validation['reason']}",
            )
    else:
        sql = validation["sql"]  # Use the cleaned version
    query_validated = True

    # Step 4: Execute with retry
    result_df, final_sql, retried = execute_with_retry(
        conn, sql, relevant_schema, table_name, semantic_layer, intent, plan
    )

    result_data = result_df.to_dict(orient="records")
    result_columns = list(result_df.columns)
    rows_returned = len(result_data)

    # Step 4b: Fix C — validate for duplicate dimension values (missing GROUP BY)
    if rows_returned > 1:
        validation_result = validate_query_result(final_sql, result_data, result_columns)
        if not validation_result["valid"]:
            logger.warning(
                "Query result has duplicate dimension values: %s. Retrying with aggregation fix.",
                validation_result["issues"],
            )
            fixed_sql = _fix_sql_aggregation(final_sql, relevant_schema, table_name, plan)
            try:
                fixed_df = conn.execute(fixed_sql).fetchdf()
                final_sql = fixed_sql
                result_data = fixed_df.to_dict(orient="records")
                result_columns = list(fixed_df.columns)
                rows_returned = len(result_data)
                retried = True
            except Exception as fix_err:
                logger.warning("Aggregation fix failed: %s. Using original results.", fix_err)

    # Step 4c: Driver Analysis for "change" intent
    driver_analysis_payload = None
    if intent == "change":
        time_dims = semantic_layer.get("time_dimensions", [])
        dimensions = semantic_layer.get("dimensions", [])

        if time_dims and dimensions:
            time_col = time_dims[0]["column"]
            dim_cols = [d["column"] for d in dimensions]
            # Resolve the first relevant metric's column
            metric_col = None
            relevant_metrics = analyst_result.get("relevant_metrics", [])
            if relevant_metrics:
                metric_name = relevant_metrics[0]
                for m in semantic_layer.get("metrics", []):
                    if m.get("name") == metric_name:
                        metric_col = m.get("column")
                        break

            if metric_col:
                periods = auto_detect_periods(conn, time_col)
                if periods["current"] and periods["previous"] and periods["current"] != periods["previous"]:
                    multi_result = run_multi_dimension_analysis(
                        conn, metric_col, time_col, dim_cols,
                        periods["current"], periods["previous"]
                    )
                    # Build flat driver payload for the API response
                    best_dim = multi_result.get("best_dimension")
                    if best_dim:
                        best = multi_result["results"][best_dim]
                        driver_analysis_payload = {
                            "total_change": best.get("total_change"),
                            "total_change_pct": best.get("total_change_pct"),
                            "comparison": f"{periods['current']} vs {periods['previous']}",
                            "best_dimension": best_dim,
                            "drivers": best.get("drivers", []),
                        }
                    # Pass full multi_result to explainer for narration
                    multi_result_for_explainer = multi_result
                else:
                    multi_result_for_explainer = None
            else:
                multi_result_for_explainer = None
        else:
            multi_result_for_explainer = None
    else:
        multi_result_for_explainer = None

    # Step 5: Explainer
    explainer_result = run_explainer(
        question, final_sql, result_data, intent, semantic_layer, result_columns,
        driver_analysis=multi_result_for_explainer,
        simple_mode=simple_mode,
    )

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

    # Step 6: Metrics matching (for transparency — enriched with expr)
    metrics_used = _find_matched_metrics_enriched(question, semantic_layer, analyst_result)

    # Step 7: Confidence
    confidence_level, confidence_reason = _compute_confidence(
        retried, rows_returned, metrics_used
    )

    # Step 8: Coverage
    coverage_pct = round((rows_returned / total_rows_in_dataset) * 100) if total_rows_in_dataset > 0 else None
    data_coverage = {
        "rows_matched": rows_returned,
        "total_rows": total_rows_in_dataset,
        "coverage_pct": coverage_pct,
    } if coverage_pct is not None else None

    return {
        "needs_clarification": False,
        "intent": intent,
        "sql": final_sql,
        "query_explanation": plan,
        "data": result_data[:200],
        "columns": result_columns,
        "total_rows": rows_returned,
        "total_rows_in_dataset": total_rows_in_dataset,
        "explanation": explainer_result.get("explanation", ""),
        "insight_line": explainer_result.get("insight_line", ""),
        "chart_type": explainer_result.get("chart_type", "table"),
        "chart_config": explainer_result.get("chart_config", {}),
        "kpis": explainer_result.get("kpis", []),
        "follow_ups": explainer_result.get("follow_ups", []),
        "metrics_used": metrics_used,
        "retried": retried,
        "confidence": {"level": confidence_level, "reason": confidence_reason},
        "coverage_pct": coverage_pct,
        "data_coverage": data_coverage,
        "driver_analysis": driver_analysis_payload,
        "query_validated": query_validated,
        "cached": False,
        "action_insight": explainer_result.get("action_insight"),
        "verdict": explainer_result.get("verdict"),
        "verification": verification_status,
    }


def _find_matched_metrics_enriched(
    question: str,
    semantic_layer: dict[str, Any],
    analyst_result: dict[str, Any],
) -> list[dict]:
    """
    Return metric/dimension dicts relevant to this query, enriched with
    expr and source for the data lineage transparency panel.
    """
    matched_names: set[str] = set(analyst_result.get("relevant_metrics", []))

    question_lower = question.lower()
    for metric in semantic_layer.get("metrics", []):
        name = metric.get("name", "")
        # Check name words
        if any(word in question_lower for word in name.lower().split() if len(word) > 3):
            matched_names.add(name)
        # Check synonyms
        for syn in metric.get("synonyms", []):
            if syn.lower() in question_lower:
                matched_names.add(name)

    result = []
    # Add matched metrics with expr
    for metric in semantic_layer.get("metrics", []):
        if metric.get("name") in matched_names:
            result.append({
                "name": metric["name"],
                "expr": metric.get("expr", ""),
                "source": "Data Dictionary",
            })

    # Add relevant dimensions
    for dim_name in analyst_result.get("relevant_dimensions", []):
        for d in semantic_layer.get("dimensions", []):
            if d.get("name") == dim_name:
                result.append({
                    "name": dim_name,
                    "type": "dimension",
                    "source": "Data Dictionary",
                })
                break

    return result


def _compute_confidence(
    retried: bool,
    rows_returned: int,
    metrics_matched: list,
) -> tuple[str, str]:
    """Derive confidence level from signals."""
    has_metric = len(metrics_matched) >= 1
    sufficient_rows = rows_returned >= 10
    few_rows = rows_returned < 3

    if not retried and has_metric and sufficient_rows:
        return (
            "high",
            "Exact metric match, query succeeded first try, sufficient data returned.",
        )

    if retried and few_rows:
        return (
            "low",
            "Query required self-correction and returned very few rows.",
        )

    reasons = []
    if retried:
        reasons.append("query needed self-correction")
    if not has_metric:
        reasons.append("no direct metric match")
    if not sufficient_rows and not few_rows:
        reasons.append("limited rows returned")
    reason_str = "; ".join(reasons) if reasons else "results look plausible"
    return "medium", f"Moderate confidence - {reason_str}."
