"""
Question-answering route for DataPulse.

POST /api/ask — Accept a natural language question, run it through the
three-agent pipeline (Analyst -> SQL Writer -> Explainer), and return
a structured answer with KPIs, charts, explanation, and follow-ups.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from models.schemas import QueryResponse, QuestionRequest
from services.query_pipeline import run_pipeline
from utils.cache import get_cached, set_cached
from utils.duckdb_manager import get_session

router = APIRouter()


@router.post("/api/ask", response_model=QueryResponse)
async def ask_question(req: QuestionRequest) -> QueryResponse:
    """
    Answer a natural language question about the user's dataset.

    Uses a three-agent pipeline:
      1. Analyst — intent detection + schema selection
      2. SQL Writer — generates DuckDB query with only relevant columns
      3. Explainer — produces explanation, KPIs, chart config, follow-ups

    Includes query caching with 10-minute expiry.
    """
    session = get_session(req.session_id)
    if session is None:
        raise HTTPException(
            status_code=404,
            detail="Session not found. Please upload a dataset or select a sample first.",
        )

    # Check cache first
    cached = get_cached(req.session_id, req.question)
    if cached:
        cached["cached"] = True
        return QueryResponse(**cached)

    # Run the three-agent pipeline
    result = run_pipeline(
        question=req.question,
        schema=session["schema"],
        semantic_layer=session["semantic_layer"],
        table_name=session["table_name"],
        mode=req.mode or "auto",
        conn=session["conn"],
        total_rows_in_dataset=session["row_count"],
        simple_mode=req.simple_mode,
    )

    # Cache the result (unless it's a clarification request)
    if not result.get("needs_clarification"):
        set_cached(req.session_id, req.question, result)

    return QueryResponse(**result)
