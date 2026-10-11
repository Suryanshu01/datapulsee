"""
Thin wrapper around the Groq API (GPT-OSS 20B).

Centralising all LLM calls here means:
  - API key validation happens in one place.
  - Retry / backoff logic is shared across every service that calls the model.
  - Tests can mock this module without touching individual services.

Model choice: openai/gpt-oss-20b — Groq's replacement for the retired
llama-3.1-8b-instant. Override with the GROQ_MODEL env var.
"""

from __future__ import annotations

import json
import os
import time

from fastapi import HTTPException
from groq import Groq

from config import (
    GROQ_MODEL as _GROQ_MODEL,
    GROQ_REASONING_EFFORT as _REASONING_EFFORT,
    LLM_MAX_COMPLETION_TOKENS as _MAX_COMPLETION_TOKENS,
    LLM_MAX_RETRIES as _MAX_RETRIES,
    LLM_RETRY_DELAY_SECONDS as _RETRY_DELAY_SECONDS,
    LLM_TEMPERATURE as _TEMPERATURE,
)


def _sanitize_text_for_utf8(text: str) -> str:
    """Replace UTF-16 surrogate code points that cannot be UTF-8 encoded."""
    return "".join(
        "?" if 0xD800 <= ord(ch) <= 0xDFFF else ch
        for ch in text
    )


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
    safe_prompt = _sanitize_text_for_utf8(prompt)
    last_error: Exception | None = None

    for attempt in range(_MAX_RETRIES + 1):  # 0 = initial attempt, 1..N = retries
        try:
            response = client.chat.completions.create(
                model=_GROQ_MODEL,
                messages=[{"role": "user", "content": safe_prompt}],
                temperature=_TEMPERATURE,
                reasoning_effort=_REASONING_EFFORT,
                max_completion_tokens=_MAX_COMPLETION_TOKENS,
            )
            return (response.choices[0].message.content or "").strip()
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
