"""
Application configuration and constants for DataPulse.

All environment variables, model settings, and shared constants are defined
here so that no magic strings are scattered across modules.
"""

from __future__ import annotations

import os
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────
PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]
ASSETS_DIR: Path = PROJECT_ROOT / "assets"
SAMPLES_DIR: Path = ASSETS_DIR / "samples"

# ── LLM Provider ──────────────────────────────────────────────
GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL: str = "llama-3.1-8b-instant"
LLM_TEMPERATURE: float = 0.1
LLM_MAX_RETRIES: int = 2
LLM_RETRY_DELAY_SECONDS: int = 10

# ── Query Pipeline ────────────────────────────────────────────
MAX_RESULT_ROWS: int = 200
SQL_RETRY_LIMIT: int = 2
CACHE_TTL_SECONDS: int = 600  # 10 minutes

# ── Upload ────────────────────────────────────────────────────
ALLOWED_EXTENSIONS: tuple[str, ...] = (".csv", ".tsv")
TABLE_NAME: str = "dataset"

# ── Intent Categories ─────────────────────────────────────────
VALID_INTENTS: list[str] = ["change", "compare", "breakdown", "summary", "general"]

# ── Chart Palette (NatWest-inspired) ──────────────────────────
CHART_COLORS: list[str] = [
    "#42145F",  # NatWest purple (primary)
    "#6B4C8A",  # secondary purple
    "#0F7B3F",  # positive/success green
    "#C4314B",  # negative/danger red
    "#D4760A",  # warning orange
    "#3B82F6",  # info blue
    "#8B5CF6",  # violet
    "#059669",  # emerald
    "#DC2626",  # red
    "#F59E0B",  # amber
]
