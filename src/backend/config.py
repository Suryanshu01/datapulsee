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
# llama-3.1-8b-instant was retired by Groq on 2026-08-16; gpt-oss-20b is the official replacement.
GROQ_MODEL: str = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
# gpt-oss is a reasoning model — keep effort low so answers stay near-instant.
GROQ_REASONING_EFFORT: str = os.getenv("GROQ_REASONING_EFFORT", "low")
LLM_TEMPERATURE: float = 0.1
# Groq truncates replies at 2048 tokens unless told otherwise, which cuts the
# semantic-layer JSON short for datasets with more than ~6 numeric columns.
# This cap does not count against the tokens-per-minute rate limit.
LLM_MAX_COMPLETION_TOKENS: int = 8192
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
