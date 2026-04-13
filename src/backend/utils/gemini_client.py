"""
Thin wrapper around the Groq API (OpenAI-compatible).

Centralising all LLM calls here means:
  - API key validation happens in one place.
  - Retry / backoff logic is shared across every service that calls the model.
  - Tests can mock this module without touching individual services.

Model choice: llama-3.3-70b-versatile — fast, highly capable, generous free tier.
"""

from __future__ import annotations

import json
import os
import time

from fastapi import HTTPException
from groq import Groq

_GROQ_MODEL = "llama-3.1-8b-instant"
_MAX_RETRIES = 2
_RETRY_DELAY_SECONDS = 10


def _get_client() -> Groq:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="GROQ_API_KEY environment variable is not set. Add it to your .env file.",
        )
    return Groq(api_key=api_key)


def generate(prompt: str) -> str:
    """
    Send *prompt* to Groq and return the response text.

    Retries up to _MAX_RETRIES times on transient errors with a delay between
    attempts. Raises HTTP 502 if all retries are exhausted.
    """
    client = _get_client()
    last_error: Exception | None = None

    for attempt in range(_MAX_RETRIES + 1):  # 0 = initial attempt, 1..N = retries
        try:
            response = client.chat.completions.create(
                model=_GROQ_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
            )
            return response.choices[0].message.content.strip()
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt < _MAX_RETRIES:
                time.sleep(_RETRY_DELAY_SECONDS)

    raise HTTPException(
        status_code=502,
        detail=f"Groq API unavailable after {_MAX_RETRIES + 1} attempts: {last_error}",
    )


def strip_markdown_fences(text: str) -> str:
    """
    Remove ```json / ``` fences that the model sometimes wraps responses in.
    """
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0]
    return text.strip()
