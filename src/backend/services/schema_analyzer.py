"""
Schema analysis service for DataPulse.

After a CSV is loaded into DuckDB, this module inspects the table to produce:
  - A typed column list (schema)
  - Per-column statistics (min/max/avg for numerics, unique-count for categoricals)
  - A sample of the first few rows for display and for the Gemini semantic-layer prompt

Keeping this logic separate from the upload route makes it testable in isolation
and reusable for both user-uploaded files and bundled sample datasets.
"""

from __future__ import annotations

import duckdb

# DuckDB type names that indicate a numeric column.
_NUMERIC_TYPES = {"BIGINT", "INTEGER", "DOUBLE", "FLOAT", "DECIMAL", "HUGEINT", "UBIGINT"}


def analyze_schema(
    conn: duckdb.DuckDBPyConnection,
    table_name: str,
) -> tuple[list[dict], dict, list[dict], int]:
    """
    Inspect *table_name* inside *conn* and return analysis results.

    Returns
    -------
    schema : list[dict]
        One entry per column: {"column": str, "type": str}
    stats : dict
        Keyed by column name.  Numeric columns get min/max/avg/unique;
        non-numeric columns get unique count only.
    sample : list[dict]
        First 5 rows as a list of row dicts (for the Gemini prompt and UI preview).
    row_count : int
        Total number of rows in the table.
    """
    schema_info = conn.execute(f"DESCRIBE {table_name}").fetchall()
    schema: list[dict] = [{"column": row[0], "type": row[1]} for row in schema_info]

    # Convert to string-safe dicts: Pandas may produce Timestamp / numpy types
    # that are not JSON-serialisable. Casting via str() on non-primitive values
    # ensures the sample can be passed safely to json.dumps() in the AI prompt.
    raw_sample = conn.execute(f'SELECT * FROM "{table_name}" LIMIT 5').fetchdf()
    sample: list[dict] = [
        {k: (v if isinstance(v, (int, float, bool, str, type(None))) else str(v))
         for k, v in row.items()}
        for row in raw_sample.to_dict(orient="records")
    ]

    row_count: int = conn.execute(f'SELECT COUNT(*) FROM "{table_name}"').fetchone()[0]

    stats: dict = {}
    for col in schema:
        col_name = col["column"]
        # Normalise to base type name (e.g. "DECIMAL(18,3)" → "DECIMAL")
        base_type = col["type"].split("(")[0].upper()

        if base_type in _NUMERIC_TYPES:
            stats[col_name] = _numeric_stats(conn, table_name, col_name)
        else:
            stats[col_name] = _categorical_stats(conn, table_name, col_name)

    return schema, stats, sample, row_count


def _numeric_stats(
    conn: duckdb.DuckDBPyConnection,
    table_name: str,
    col_name: str,
) -> dict:
    """Compute min, max, average, and distinct-value count for a numeric column."""
    try:
        result = conn.execute(
            f"""
            SELECT
                MIN("{col_name}"),
                MAX("{col_name}"),
                AVG("{col_name}")::DOUBLE,
                COUNT(DISTINCT "{col_name}")
            FROM "{table_name}"
            """
        ).fetchone()
        return {
            "min": result[0],
            "max": result[1],
            "avg": round(result[2], 2) if result[2] is not None else None,
            "unique": result[3],
        }
    except Exception:  # noqa: BLE001
        return {}


def _categorical_stats(
    conn: duckdb.DuckDBPyConnection,
    table_name: str,
    col_name: str,
) -> dict:
    """Compute distinct-value count for a categorical or temporal column."""
    try:
        result = conn.execute(
            f'SELECT COUNT(DISTINCT "{col_name}") FROM "{table_name}"'
        ).fetchone()
        return {"unique": result[0]}
    except Exception:  # noqa: BLE001
        return {}
