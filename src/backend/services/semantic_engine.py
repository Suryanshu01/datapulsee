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

from utils.llm_client import generate, strip_markdown_fences

logger = logging.getLogger(__name__)


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

    Falls back to an empty-but-valid layer if generation fails,
    so uploads always succeed.
    """
    prompt = f"""You are a senior data analyst documenting a dataset for business users.
Given the schema, sample rows, and column statistics, generate a semantic layer in Snowflake Cortex Analyst format.

Schema: {json.dumps(_to_json_safe(schema))}
Sample rows (first 3): {json.dumps(_to_json_safe(sample[:3]))}
Column statistics: {json.dumps(_to_json_safe(stats))}

Return ONLY valid JSON (no markdown fences) with this structure:
{{
  "data_summary": "2-3 sentence description of the dataset, its time range, and what questions it can answer.",
  "metrics": [
    {{
      "name": "total_column_name",
      "description": "Total column_name, always aggregated with SUM",
      "expr": "SUM(\"column_name\")",
      "column": "column_name",
      "data_type": "numeric",
      "synonyms": ["alternative name 1", "alternative name 2"]
    }},
    {{
      "name": "avg_column_name",
      "description": "Average column_name across records",
      "expr": "AVG(\"column_name\")",
      "column": "column_name",
      "data_type": "numeric",
      "synonyms": ["mean column_name"]
    }},
    {{
      "name": "count_column_name",
      "description": "Count of non-null column_name records",
      "expr": "COUNT(\"column_name\")",
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
        return layer
    except Exception as exc:
        logger.warning("Semantic layer generation failed: %s", exc)
        column_names = [c["column"] for c in schema]
        return {
            "metrics": [],
            "dimensions": [],
            "time_dimensions": [],
            "data_summary": (
                f"Auto-generation failed ({exc}). "
                f"Dataset columns: {', '.join(column_names)}. "
                "Please add metric definitions manually."
            ),
        }
