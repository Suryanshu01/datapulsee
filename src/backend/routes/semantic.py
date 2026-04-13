"""
Semantic layer CRUD routes for DataPulse.

GET /api/semantic-layer/{session_id} — Retrieve the current semantic layer
PUT /api/semantic-layer              — Replace the semantic layer (user edits)

The semantic layer is included in every Gemini prompt, so edits made here
immediately affect the accuracy and consistency of subsequent answers.
This is a key differentiator: users can define "revenue means gross revenue
before returns" once and all future queries will respect that definition.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from models.schemas import SemanticUpdate
from utils.duckdb_manager import get_session, update_semantic_layer

router = APIRouter()


@router.get("/api/semantic-layer/{session_id}")
async def get_semantic_layer(session_id: str) -> dict:
    """Return the semantic layer for the given session."""
    session = get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    return session["semantic_layer"]


@router.put("/api/semantic-layer")
async def put_semantic_layer(req: SemanticUpdate) -> dict:
    """
    Replace the semantic layer for the given session with user-edited definitions.

    The updated layer is stored in the session and used for all subsequent
    /api/ask calls in this session.
    """
    success = update_semantic_layer(req.session_id, req.semantic_layer)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found.")
    return {"status": "updated"}
