"""
Semantic layer generation and management for DataPulse.

The semantic layer mirrors Snowflake Cortex Analyst's specification:
  - metrics       : quantitative measures with SQL expressions and synonyms
  - dimensions    : categorical columns with sample values
  - time_dimensions : temporal columns with granularity detection
  - data_summary  : plain-English dataset description

This format ensures "revenue" always means the same thing across all queries,
matching NatWest's internal approach with Snowflake Cortex Analyst.
"""

from __future__ import annotations

import json
import logging
import re

from utils.llm_client import generate, strip_markdown_fences

logger = logging.getLogger(__name__)

_NUMERIC_BASE_TYPES = {
    "TINYINT", "SMALLINT", "INTEGER", "BIGINT", "HUGEINT",
    "UTINYINT", "USMALLINT", "UINTEGER", "UBIGINT",
    "FLOAT", "DOUBLE", "DECIMAL", "REAL",
}
_FRACTIONAL_BASE_TYPES = {"FLOAT", "DOUBLE", "DECIMAL", "REAL"}
_TIME_NAME_GRANULARITY = {
    "date": "daily", "day": "daily", "week": "weekly", "month": "monthly",
    "quarter": "quarterly", "year": "yearly", "period": "monthly",
}
_GEO_NAME_TOKENS = {"region", "country", "city", "state", "zone", "territory", "location", "branch"}
# Text columns with more distinct values than this (names, IDs, emails) are not useful to group by.
_MAX_DIMENSION_VALUES = 50


def _to_json_safe(obj):
    """Recursively convert pandas/numpy types to plain Python types for json.dumps."""
    if isinstance(obj, dict):
        return {k: _to_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_json_safe(v) for v in obj]
    if hasattr(obj, "item"):
        return obj.item()
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    if isinstance(obj, (int, float, bool, str, type(None))):
        return obj
    return str(obj)


async def generate_semantic_layer(
    schema: list[dict],
    sample: list[dict],
    stats: dict,
) -> dict:
    """
    Ask the LLM to auto-generate a Snowflake-format semantic layer.

    Falls back to a layer inferred from column types if generation fails,
    so uploads always succeed and still detect metrics and dimensions.
    """
    prompt = f"""You are a senior data analyst documenting a dataset for business users.
Given the schema, sample rows, and column statistics, generate a semantic layer in Snowflake Cortex Analyst format.

Schema: {json.dumps(_to_json_safe(schema))}
Sample rows (first 3): {json.dumps(_to_json_safe(sample[:3]))}
Column statistics: {json.dumps(_to_json_safe(stats))}

Return ONLY valid, compact JSON (no markdown fences, no indentation) with this structure:
{{
  "data_summary": "2-3 sentence description of the dataset, its time range, and what questions it can answer.",
  "metrics": [
    {{
      "name": "total_column_name",
      "description": "Total column_name, always aggregated with SUM",
      "expr": "SUM(\\"column_name\\")",
      "column": "column_name",
      "data_type": "numeric",
      "synonyms": ["alternative name 1", "alternative name 2"]
    }},
    {{
      "name": "avg_column_name",
      "description": "Average column_name across records",
      "expr": "AVG(\\"column_name\\")",
      "column": "column_name",
      "data_type": "numeric",
      "synonyms": ["mean column_name"]
    }},
    {{
      "name": "count_column_name",
      "description": "Count of non-null column_name records",
      "expr": "COUNT(\\"column_name\\")",
      "column": "column_name",
      "data_type": "numeric",
      "synonyms": ["number of column_name"]
    }}
  ],
  "dimensions": [
    {{
      "name": "human_readable_dimension_name",
      "description": "What this dimension represents and how it slices data",
      "column": "source_column_name",
      "data_type": "categorical",
      "sample_values": ["Value1", "Value2", "Value3"]
    }}
  ],
  "time_dimensions": [
    {{
      "name": "time_dimension_name",
      "description": "What time period this represents",
      "column": "source_column_name",
      "data_type": "date",
      "granularity": "daily|weekly|monthly|yearly",
      "sample_values": ["2024-01", "2024-02"]
    }}
  ]
}}

METRIC RULES — CRITICAL:
- For EVERY numeric column, create THREE metrics:
  1. total_<column>  with expr: SUM("<column>")   — e.g. SUM("disbursed_amount")
  2. avg_<column>    with expr: AVG("<column>")
  3. count_<column>  with expr: COUNT("<column>")
- Column names inside expr MUST be wrapped in double quotes for DuckDB compatibility
  CORRECT:   SUM("disbursed_amount")
  WRONG:     SUM(disbursed_amount)  ← missing double quotes
- The expr field is used directly in SQL, so it must be valid DuckDB syntax

OTHER RULES:
- Add 2-3 synonyms per metric (alternative names users might use)
- Mark date/month/year/week columns as time_dimensions with detected granularity
- Mark region/country/city columns as geographic dimensions (data_type: "geographic")
- Mark other categorical columns as regular dimensions (data_type: "categorical")
- Include 3-5 sample_values for each dimension (from the actual data)
- Use snake_case for names"""

    try:
        raw = generate(prompt)
        cleaned = strip_markdown_fences(raw)
        layer = json.loads(cleaned)
        # Validate expected keys
        layer.setdefault("metrics", [])
        layer.setdefault("dimensions", [])
        layer.setdefault("time_dimensions", [])
        layer.setdefault("data_summary", "")
        if not (layer["metrics"] or layer["dimensions"] or layer["time_dimensions"]):
            raise ValueError("model returned no metrics, dimensions or time dimensions")
        return layer
    except Exception as exc:
        logger.warning("Semantic layer generation failed, inferring from column types: %s", exc)
        return build_schema_semantic_layer(schema, sample, stats, reason=str(exc))


def build_schema_semantic_layer(
    schema: list[dict],
    sample: list[dict],
    stats: dict,
    reason: str,
) -> dict:
    """
    Infer a semantic layer from column types alone, without calling the LLM.

    Follows the same conventions the LLM prompt asks for (total_/avg_/count_
    metrics per numeric column, dimensions, time dimensions) so every
    downstream feature works when AI generation is unavailable.
    """
    metrics: list[dict] = []
    dimensions: list[dict] = []
    time_dimensions: list[dict] = []

    for col in schema:
        column = col["column"]
        base_type = col["type"].split("(")[0].upper()
        tokens = [t for t in re.split(r"[^a-z0-9]+", column.lower()) if t]
        snake = "_".join(tokens) or column
        label = " ".join(tokens) or column
        time_token = next((t for t in tokens if t in _TIME_NAME_GRANULARITY), None)
        sample_values = list(dict.fromkeys(
            str(row[column]) for row in sample if row.get(column) is not None
        ))[:5]

        if base_type.startswith(("DATE", "TIMESTAMP")) or (
            time_token and base_type not in _FRACTIONAL_BASE_TYPES
        ):
            time_dimensions.append({
                "name": snake,
                "description": f"When each record happened ({label})",
                "column": column,
                "data_type": "date",
                "granularity": _TIME_NAME_GRANULARITY.get(time_token, "daily"),
                "sample_values": sample_values,
            })
        elif base_type in _NUMERIC_BASE_TYPES:
            if tokens and tokens[-1] == "id":
                continue  # identifiers are numeric but meaningless to sum
            metrics.extend([
                {"name": f"total_{snake}", "description": f"Total {label}, always aggregated with SUM",
                 "expr": f'SUM("{column}")', "column": column, "data_type": "numeric", "synonyms": [label]},
                {"name": f"avg_{snake}", "description": f"Average {label} across records",
                 "expr": f'AVG("{column}")', "column": column, "data_type": "numeric", "synonyms": [f"average {label}"]},
                {"name": f"count_{snake}", "description": f"Count of non-null {label} records",
                 "expr": f'COUNT("{column}")', "column": column, "data_type": "numeric", "synonyms": [f"number of {label}"]},
            ])
        elif stats.get(column, {}).get("unique", 0) <= _MAX_DIMENSION_VALUES:
            dimensions.append({
                "name": snake,
                "description": f"Groups records by {label}",
                "column": column,
                "data_type": "geographic" if _GEO_NAME_TOKENS.intersection(tokens) else "categorical",
                "sample_values": sample_values,
            })

    return {
        "metrics": metrics,
        "dimensions": dimensions,
        "time_dimensions": time_dimensions,
        "data_summary": (
            f"Dataset with {len(schema)} columns. AI descriptions were unavailable ({reason[:200]}), "
            "so these definitions were inferred from column types. Review and edit them if needed."
        ),
    }
