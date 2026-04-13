"""
Pydantic models for DataPulse API request and response validation.

Centralising all schemas here ensures a single source of truth and makes
it easy for judges to understand the API contract without reading route logic.
"""

from typing import Any, Optional
from pydantic import BaseModel, Field


class QuestionRequest(BaseModel):
    """Payload for the /api/ask endpoint."""

    session_id: str = Field(..., description="Session ID returned by the upload endpoint")
    question: str = Field(..., description="Natural language question about the dataset")
    mode: Optional[str] = Field(
        default="auto",
        description="Intent hint: auto | change | compare | breakdown | summary",
    )
    simple_mode: bool = Field(
        default=True,
        description="When True, use plain English. When False, use precise business language.",
    )


class SemanticUpdate(BaseModel):
    """Payload for PUT /api/semantic-layer - replaces the semantic layer for a session."""

    session_id: str
    semantic_layer: dict[str, Any]


class KPI(BaseModel):
    """A single KPI card in the answer."""

    label: str = ""
    value: Any = None
    formatted: Optional[str] = ""
    delta: Optional[float] = None
    delta_label: Optional[str] = ""

    def model_post_init(self, __context: Any) -> None:
        # Normalise None to empty string for fields that the frontend expects as strings
        if self.formatted is None:
            self.formatted = ""
        if self.delta_label is None:
            self.delta_label = ""


class ConfidenceLevel(BaseModel):
    """Structured confidence indicator for every answer."""

    level: str = Field(..., description="high | medium | low")
    reason: str = Field(..., description="Human-readable explanation")


class QueryResponse(BaseModel):
    """Full response returned by the /api/ask endpoint."""

    needs_clarification: bool = False
    clarification_question: Optional[str] = None
    clarification_options: Optional[list[str]] = None
    intent: str = "general"
    sql: str = ""
    query_explanation: str = ""
    data: list[dict[str, Any]] = []
    columns: list[str] = []
    total_rows: int = 0
    total_rows_in_dataset: int = 0
    explanation: str = ""
    insight_line: str = ""
    chart_type: str = "table"
    chart_config: dict[str, Any] = {}
    kpis: list[KPI] = []
    follow_ups: list[str] = []
    metrics_used: list[Any] = []
    retried: bool = False
    confidence: Optional[ConfidenceLevel] = None
    coverage_pct: Optional[int] = None
    data_coverage: Optional[dict[str, Any]] = None
    driver_analysis: Optional[dict[str, Any]] = None
    query_validated: bool = False
    cached: bool = False
    action_insight: Optional[str] = None
    verdict: Optional[str] = None
