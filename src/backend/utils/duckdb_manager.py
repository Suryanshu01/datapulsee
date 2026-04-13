"""
DuckDB session manager for DataPulse.

Each uploaded dataset lives in its own in-memory DuckDB connection so that
multiple browser sessions can coexist without interference.  Sessions are
keyed by a UUID that the frontend stores and sends with every request.

Why in-memory DuckDB?  Zero infrastructure — no Postgres, no SQLite file —
and DuckDB's analytical query engine handles GROUP BY / window functions on
CSV data faster than SQLite would.
"""

from __future__ import annotations

from typing import Any

import duckdb

# Module-level registry: session_id → session dict.
# Structure per session:
#   conn            : duckdb.DuckDBPyConnection
#   schema          : list[dict]  — [{"column": str, "type": str}, ...]
#   semantic_layer  : dict        — metrics + dimensions + data_summary
#   table_name      : str         — always "dataset" for now
#   filename        : str         — original file name, shown in the UI
#   row_count       : int         — total rows, used for coverage calculation
_SESSIONS: dict[str, dict[str, Any]] = {}


def create_session(
    session_id: str,
    conn: duckdb.DuckDBPyConnection,
    schema: list[dict],
    semantic_layer: dict,
    table_name: str,
    filename: str,
    row_count: int,
) -> None:
    """Register a new session after a successful dataset upload."""
    _SESSIONS[session_id] = {
        "conn": conn,
        "schema": schema,
        "semantic_layer": semantic_layer,
        "table_name": table_name,
        "filename": filename,
        "row_count": row_count,
    }


def get_session(session_id: str) -> dict[str, Any] | None:
    """Return the session dict for *session_id*, or None if it does not exist."""
    return _SESSIONS.get(session_id)


def update_semantic_layer(session_id: str, semantic_layer: dict) -> bool:
    """
    Replace the semantic layer for an existing session.

    Returns True on success, False if the session was not found.
    Storing the updated layer back into the session dict means that every
    subsequent /api/ask call will use the user's edited definitions.
    """
    session = _SESSIONS.get(session_id)
    if session is None:
        return False
    session["semantic_layer"] = semantic_layer
    return True


def session_count() -> int:
    """Return the number of active sessions (used by the health endpoint)."""
    return len(_SESSIONS)
