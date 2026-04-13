"""
Deterministic driver analysis engine.
Computes which dimension values contributed most to a metric change.
No LLM involved — pure SQL + math for trustworthy, verifiable results.

Example: Revenue dropped ₹10L total.
  - South contributed -₹6L (60% of the decline)
  - East contributed -₹3L (30% of the decline)
  - North contributed -₹1L (10% of the decline)
"""

import duckdb
from typing import Optional


def compute_drivers(
    conn: duckdb.DuckDBPyConnection,
    metric_column: str,
    time_column: str,
    dimension_column: str,
    current_period: str,
    previous_period: str,
    table_name: str = "dataset",
    aggregation: str = "SUM",
) -> dict:
    """
    Compute contribution of each dimension value to the overall metric change
    between two time periods.

    Args:
        conn: DuckDB connection
        metric_column: The numeric column to analyze (e.g., "disbursed_amount")
        time_column: The time column (e.g., "month")
        dimension_column: The categorical column to break down by (e.g., "region")
        current_period: The current period value (e.g., "2024-06")
        previous_period: The comparison period value (e.g., "2024-05")
        table_name: Table to query (default "dataset")
        aggregation: SQL aggregation function (default "SUM")

    Returns:
        Dict with total_current, total_previous, total_change, total_change_pct,
        and a "drivers" array sorted by absolute contribution (largest first).
        Each driver has: dimension_value, current, previous, change, change_pct, contribution_pct
    """
    sql = f'''
        WITH current_data AS (
            SELECT "{dimension_column}" AS dim_value,
                   {aggregation}("{metric_column}") AS value
            FROM {table_name}
            WHERE CAST("{time_column}" AS VARCHAR) LIKE '{current_period}%'
            GROUP BY "{dimension_column}"
        ),
        previous_data AS (
            SELECT "{dimension_column}" AS dim_value,
                   {aggregation}("{metric_column}") AS value
            FROM {table_name}
            WHERE CAST("{time_column}" AS VARCHAR) LIKE '{previous_period}%'
            GROUP BY "{dimension_column}"
        )
        SELECT
            COALESCE(c.dim_value, p.dim_value) AS dim_value,
            COALESCE(c.value, 0) AS current_value,
            COALESCE(p.value, 0) AS previous_value,
            COALESCE(c.value, 0) - COALESCE(p.value, 0) AS change
        FROM current_data c
        FULL OUTER JOIN previous_data p ON c.dim_value = p.dim_value
        ORDER BY ABS(COALESCE(c.value, 0) - COALESCE(p.value, 0)) DESC
    '''

    try:
        rows = conn.execute(sql).fetchdf().to_dict(orient="records")
    except Exception as e:
        return {"error": str(e), "drivers": []}

    total_current = sum(r["current_value"] for r in rows)
    total_previous = sum(r["previous_value"] for r in rows)
    total_change = total_current - total_previous

    if total_previous != 0:
        total_change_pct = round((total_change / total_previous * 100), 1)
    else:
        total_change_pct = 0

    drivers = []
    for row in rows:
        change = row["change"]
        if total_change != 0:
            contribution = round((change / total_change * 100), 1)
        else:
            contribution = 0
        if row["previous_value"] != 0:
            change_pct = round((change / row["previous_value"] * 100), 1)
        else:
            change_pct = 0

        drivers.append({
            "dimension_value": str(row["dim_value"]),
            "current": round(float(row["current_value"]), 2),
            "previous": round(float(row["previous_value"]), 2),
            "change": round(float(change), 2),
            "change_pct": change_pct,
            "contribution_pct": contribution,
        })

    return {
        "total_current": round(total_current, 2),
        "total_previous": round(total_previous, 2),
        "total_change": round(total_change, 2),
        "total_change_pct": total_change_pct,
        "drivers": drivers,
        "top_driver": drivers[0]["dimension_value"] if drivers else None,
        "top_driver_contribution": drivers[0]["contribution_pct"] if drivers else 0,
    }


def auto_detect_periods(conn, time_column: str, table_name: str = "dataset") -> dict:
    """
    Auto-detect the two most recent periods in the dataset for comparison.
    Returns {"current": "2024-12", "previous": "2024-11"} or similar.
    """
    sql = f'''
        SELECT DISTINCT CAST("{time_column}" AS VARCHAR) AS period
        FROM {table_name}
        ORDER BY period DESC
        LIMIT 2
    '''
    try:
        rows = conn.execute(sql).fetchdf().to_dict(orient="records")
        if len(rows) >= 2:
            return {"current": rows[0]["period"], "previous": rows[1]["period"]}
        elif len(rows) == 1:
            return {"current": rows[0]["period"], "previous": rows[0]["period"]}
        else:
            return {"current": None, "previous": None}
    except Exception:
        return {"current": None, "previous": None}


def run_multi_dimension_analysis(
    conn,
    metric_column: str,
    time_column: str,
    dimension_columns: list,
    current_period: str,
    previous_period: str,
    table_name: str = "dataset",
) -> dict:
    """
    Run driver analysis across multiple dimensions and return the one
    with the most concentrated explanation (highest top-driver contribution).
    """
    best_result = None
    best_concentration = 0
    all_results = {}

    for dim_col in dimension_columns:
        result = compute_drivers(
            conn, metric_column, time_column, dim_col,
            current_period, previous_period, table_name
        )
        all_results[dim_col] = result

        if result.get("drivers") and abs(result.get("top_driver_contribution", 0)) > best_concentration:
            best_concentration = abs(result["top_driver_contribution"])
            best_result = dim_col

    return {
        "best_dimension": best_result,
        "results": all_results,
    }
