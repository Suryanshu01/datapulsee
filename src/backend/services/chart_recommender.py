"""
Chart type selection logic for DataPulse.

Gemini's query plan already suggests a chart_type and chart_config, but those
suggestions are sometimes malformed or use column names that don't exist in the
result.  This module validates and, where necessary, corrects the chart config
so the frontend always receives something it can render.

Chart types supported by the frontend:
  - bar    : grouped or simple bar chart (needs x and y columns)
  - line   : time-series line chart (needs x=temporal, y=numeric)
  - pie    : proportional breakdown (needs label and value columns)
  - table  : fallback for complex or multi-column results
  - number : single KPI callout (result must be exactly 1 row × 1 column)
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def validate_and_fix_chart_config(
    query_plan: dict,
    result_columns: list[str],
    result_row_count: int,
) -> tuple[str, dict]:
    """
    Return a (chart_type, chart_config) pair that is safe for the frontend to render.

    Validation steps:
      1. If the suggested chart is "number", confirm the result is 1×1.
      2. If the suggested chart needs x/y columns, confirm they exist in the result.
      3. Fall back to "table" if config is invalid or columns are missing.

    Parameters
    ----------
    query_plan : dict
        The raw query plan from Gemini (may have chart_type and chart_config keys).
    result_columns : list[str]
        Column names actually present in the query result DataFrame.
    result_row_count : int
        Number of rows in the result.
    """
    chart_type: str = query_plan.get("chart_type", "table")
    chart_config: dict = query_plan.get("chart_config") or {}

    if chart_type == "number":
        # "number" is only meaningful for a single scalar result
        if result_row_count == 1 and len(result_columns) == 1:
            return "number", {}
        # Otherwise fall back to table so the data isn't hidden
        return "table", {}

    if chart_type in ("bar", "line"):
        x_col = chart_config.get("x")
        y_col = chart_config.get("y")

        if x_col in result_columns and y_col in result_columns:
            return chart_type, chart_config

        # Attempt auto-repair: pick the first string column as x, first numeric as y
        repaired = _auto_assign_axes(result_columns)
        if repaired:
            logger.info(
                "Chart config repaired: Gemini suggested x=%s y=%s but columns are %s. "
                "Using x=%s y=%s instead.",
                x_col,
                y_col,
                result_columns,
                repaired["x"],
                repaired["y"],
            )
            return chart_type, repaired

        return "table", {}

    if chart_type == "pie":
        label_col = chart_config.get("x") or chart_config.get("label")
        value_col = chart_config.get("y") or chart_config.get("value")
        if label_col in result_columns and value_col in result_columns:
            return "pie", {"x": label_col, "y": value_col}
        return "table", {}

    # table or any unknown type — always safe
    return "table", {}


def _auto_assign_axes(columns: list[str]) -> dict | None:
    """
    Heuristically pick x and y columns when Gemini's suggestion is invalid.

    Returns {"x": col, "y": col} or None if suitable columns cannot be found.
    The caller will treat None as "fall back to table".
    """
    if len(columns) < 2:
        return None

    # Treat the first column as the category axis and the last as the value axis.
    # This is a safe assumption for most GROUP BY … ORDER BY queries.
    return {"x": columns[0], "y": columns[-1]}
