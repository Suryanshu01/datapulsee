"""
AI explanation generation for DataPulse query results.

After a SQL query runs, this service asks Gemini to translate the raw results
into a plain-English explanation that a non-technical business user can act on.

The explanation follows a consistent structure:
  1. Direct answer to the question
  2. Key finding (the most important number or trend)
  3. Notable pattern or anomaly if present
  4. Simple language — no SQL jargon, no column name references

Keeping this separate from the query engine makes it easy to swap in a
different explanation style (e.g. bullet-point vs narrative) or model later.
"""

from __future__ import annotations

import json
import logging

from utils.gemini_client import generate

logger = logging.getLogger(__name__)

_FALLBACK_EXPLANATION = (
    "Results retrieved successfully. See the data table and chart below for details."
)


def generate_explanation(
    question: str,
    sql: str,
    result_data: list[dict],
    intent: str,
) -> str:
    """
    Generate a plain-English explanation of query results using Gemini.

    Parameters
    ----------
    question : str
        The original user question.
    sql : str
        The SQL that produced the results (included so Gemini understands context).
    result_data : list[dict]
        The query result rows (we send the first 10 to keep the prompt short).
    intent : str
        Detected intent (change / compare / breakdown / summary / general).

    Returns
    -------
    str
        A 3-5 sentence plain-English explanation, or a safe fallback on failure.
    """
    # Limit rows in the prompt to keep token usage low
    sample_rows = result_data[:10]

    intent_guidance = _intent_guidance(intent)

    prompt = f"""You are explaining data analysis results to a non-technical business user.

Original question: "{question}"
Analysis type: {intent}
SQL query used: {sql}
Results (first 10 rows): {json.dumps(sample_rows)}

{intent_guidance}

Write a clear, concise explanation (3-5 sentences) that:
1. Directly answers the question in the first sentence
2. Highlights the single most important finding with specific numbers
3. Mentions any surprising pattern, anomaly, or notable trend if present
4. Uses plain English — no SQL terms, no column name jargon
5. Stays factual — only state what the data shows

Return ONLY the explanation text, nothing else."""

    try:
        return generate(prompt)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Explanation generation failed: %s", exc)
        return _FALLBACK_EXPLANATION


def _intent_guidance(intent: str) -> str:
    """Return intent-specific instructions to guide the explanation tone."""
    guidance = {
        "change": (
            "Focus on what changed, by how much, and what the most likely driver is. "
            "Use comparative language: 'increased by', 'dropped from X to Y'."
        ),
        "compare": (
            "Highlight the difference between the groups being compared. "
            "State which is higher/lower and by what margin."
        ),
        "breakdown": (
            "Identify the top contributors and any concentration (e.g. one category dominating). "
            "Mention the largest and smallest segments."
        ),
        "summary": (
            "Summarise the overall trend first, then call out the most notable anomaly or shift. "
            "Keep it high-level — this is an executive summary."
        ),
    }
    return guidance.get(intent, "Answer directly and highlight the key insight.")
