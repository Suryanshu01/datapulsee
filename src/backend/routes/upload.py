"""
Upload and sample dataset routes for DataPulse.

Endpoints:
  POST /api/upload              — Accept a user-uploaded CSV/TSV file
  GET  /api/samples             — List bundled sample datasets
  GET  /api/samples/{filename}  — Load a bundled sample dataset

Both the upload and sample-load paths go through the same pipeline:
  1. Load the file into an in-memory DuckDB table
  2. Analyse the schema, compute per-column statistics, take a sample
  3. Auto-generate a semantic layer via Gemini
  4. Register the session and return all metadata to the frontend
"""

from __future__ import annotations

import tempfile
import uuid
from pathlib import Path

import duckdb
from fastapi import APIRouter, File, HTTPException, UploadFile

from services.schema_analyzer import analyze_schema
from services.semantic_engine import generate_semantic_layer
from services.pii_detector import scan_for_pii, sanitize_semantic_layer
from utils.duckdb_manager import create_session

router = APIRouter()

# Bundled sample datasets live alongside the assets directory.
# Path is resolved relative to this file so it works regardless of the
# working directory the server is started from.
_SAMPLES_DIR = Path(__file__).resolve().parents[3] / "assets" / "samples"

_ALLOWED_EXTENSIONS = (".csv", ".tsv", ".xlsx")


@router.post("/api/upload")
async def upload_dataset(file: UploadFile = File(...)) -> dict:
    """
    Accept a CSV or TSV file upload, analyse it, and return a new session.

    The file is written to a temporary path so DuckDB's read_csv_auto can
    inspect it.  All subsequent queries use the in-memory DuckDB connection;
    the temp file is not needed again after this call.
    """
    if not any(file.filename.endswith(ext) for ext in _ALLOWED_EXTENSIONS):
        raise HTTPException(
            status_code=400,
            detail=f"Only {', '.join(_ALLOWED_EXTENSIONS)} files are supported.",
        )

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    session_id = str(uuid.uuid4())
    conn = duckdb.connect()
    table_name = "dataset"

    # Write to a temp file so DuckDB can infer types and parse the CSV
    with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    if file.filename.endswith(".xlsx"):
        import pandas as pd
        df = pd.read_excel(tmp_path, engine="openpyxl")
        conn.execute(f"CREATE TABLE {table_name} AS SELECT * FROM df")
    else:
        conn.execute(f"CREATE TABLE {table_name} AS SELECT * FROM read_csv_auto('{tmp_path}')")

    schema, stats, sample, row_count = analyze_schema(conn, table_name)
    semantic_layer = await generate_semantic_layer(schema, sample, stats)

    pii_columns = scan_for_pii(conn, schema)
    if pii_columns:
        semantic_layer = sanitize_semantic_layer(semantic_layer, pii_columns)

    create_session(
        session_id=session_id,
        conn=conn,
        schema=schema,
        semantic_layer=semantic_layer,
        table_name=table_name,
        filename=file.filename,
        row_count=row_count,
    )

    return {
        "session_id": session_id,
        "schema": schema,
        "row_count": row_count,
        "sample": sample,
        "stats": stats,
        "semantic_layer": semantic_layer,
        "pii_columns": pii_columns,
    }


@router.get("/api/samples")
async def list_samples() -> dict:
    """List the bundled sample datasets available for zero-config demos."""
    if not _SAMPLES_DIR.exists():
        return {"samples": []}

    samples = [
        {"name": f.stem.replace("_", " ").title(), "filename": f.name}
        for f in sorted(_SAMPLES_DIR.glob("*.csv"))
    ]
    return {"samples": samples}


@router.get("/api/samples/{filename}")
async def load_sample(filename: str) -> dict:
    """
    Load one of the bundled sample datasets into a new session.

    Mirrors the upload pipeline exactly so that the frontend receives
    the same response shape regardless of how data was loaded.
    """
    # Sanitise filename to prevent path traversal
    safe_filename = Path(filename).name
    filepath = _SAMPLES_DIR / safe_filename

    if not filepath.exists() or filepath.suffix not in _ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=404, detail=f"Sample '{safe_filename}' not found.")

    session_id = str(uuid.uuid4())
    conn = duckdb.connect()
    table_name = "dataset"

    conn.execute(f"CREATE TABLE {table_name} AS SELECT * FROM read_csv_auto('{filepath}')")

    schema, stats, sample, row_count = analyze_schema(conn, table_name)
    semantic_layer = await generate_semantic_layer(schema, sample, stats)

    pii_columns = scan_for_pii(conn, schema)
    if pii_columns:
        semantic_layer = sanitize_semantic_layer(semantic_layer, pii_columns)

    create_session(
        session_id=session_id,
        conn=conn,
        schema=schema,
        semantic_layer=semantic_layer,
        table_name=table_name,
        filename=safe_filename,
        row_count=row_count,
    )

    return {
        "session_id": session_id,
        "schema": schema,
        "row_count": row_count,
        "sample": sample,
        "stats": stats,
        "semantic_layer": semantic_layer,
        "pii_columns": pii_columns,
    }
