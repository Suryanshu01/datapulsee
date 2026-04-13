"""
Simple in-memory query result cache for DataPulse.

Caches NL question -> response mappings per session to avoid redundant
LLM calls and SQL execution. Cache entries expire after CACHE_TTL_SECONDS.

Design: dict-based, no external dependencies. Fast and good enough for
a single-process demo. Production would use Redis.
"""

from __future__ import annotations

import hashlib
import time
from typing import Any

from config import CACHE_TTL_SECONDS

# session_id -> { question_hash -> { "response": dict, "timestamp": float } }
_cache: dict[str, dict[str, dict[str, Any]]] = {}


def _normalize_question(question: str) -> str:
    """Lowercase, strip whitespace, remove trailing punctuation for consistent hashing."""
    return question.lower().strip().rstrip("?!.")


def _hash_question(question: str) -> str:
    """Create a short hash of the normalized question."""
    normalized = _normalize_question(question)
    return hashlib.md5(normalized.encode()).hexdigest()


def get_cached(session_id: str, question: str) -> dict[str, Any] | None:
    """Return cached response if it exists and hasn't expired, else None."""
    session_cache = _cache.get(session_id)
    if not session_cache:
        return None

    key = _hash_question(question)
    entry = session_cache.get(key)
    if not entry:
        return None

    if time.time() - entry["timestamp"] > CACHE_TTL_SECONDS:
        del session_cache[key]
        return None

    return entry["response"]


def set_cached(session_id: str, question: str, response: dict[str, Any]) -> None:
    """Store a response in the cache."""
    if session_id not in _cache:
        _cache[session_id] = {}

    key = _hash_question(question)
    _cache[session_id][key] = {
        "response": response,
        "timestamp": time.time(),
    }


def invalidate_session(session_id: str) -> None:
    """Clear all cached entries for a session (called on new upload)."""
    _cache.pop(session_id, None)


def cache_stats() -> dict[str, int]:
    """Return cache statistics for the health endpoint."""
    total_entries = sum(len(v) for v in _cache.values())
    return {"sessions": len(_cache), "entries": total_entries}
