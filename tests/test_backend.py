"""
DataPulse backend test suite.

Tests organised by module:
  - Health endpoint
  - Sample dataset listing and loading
  - Upload endpoint
  - Ask/query endpoint (with mocked LLM)
  - Semantic layer CRUD
  - Schema analyzer unit tests
  - Query pipeline unit tests (confidence, metric matching)
  - Chart recommender unit tests
  - Cache unit tests
  - Sample dataset integrity

Run: pytest tests/ -v --tb=short
"""

import sys
import time
from pathlib import Path
from unittest.mock import patch

import duckdb
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src" / "backend"))

from main import app  # noqa: E402

client = TestClient(app)

SAMPLE_CSV = b"month,region,revenue,orders\n2024-01,North,50000,120\n2024-01,South,75000,180\n2024-02,North,48000,115\n2024-02,South,80000,195\n"


# ── Health ─────────────────────────────────────────────────────

def test_health_ok():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "sessions" in body
    assert "cache" in body


# ── Samples ────────────────────────────────────────────────────

def test_samples_list_returns_list():
    resp = client.get("/api/samples")
    assert resp.status_code == 200
    assert isinstance(resp.json()["samples"], list)


def test_samples_list_contains_banking_datasets():
    samples_dir = Path(__file__).resolve().parents[1] / "assets" / "samples"
    if not samples_dir.exists():
        pytest.skip("Samples not generated")
    filenames = [s["filename"] for s in client.get("/api/samples").json()["samples"]]
    for expected in ("sme_lending.csv", "customer_support.csv", "digital_banking.csv"):
        assert expected in filenames


def test_sample_load_not_found():
    assert client.get("/api/samples/does_not_exist.csv").status_code == 404


def test_sample_load_path_traversal_rejected():
    assert client.get("/api/samples/../.env").status_code in (404, 400)


# ── Upload ─────────────────────────────────────────────────────

def test_upload_rejects_non_csv():
    resp = client.post("/api/upload", files={"file": ("report.pdf", b"%PDF", "application/pdf")})
    assert resp.status_code == 400


def test_upload_rejects_empty_file():
    resp = client.post("/api/upload", files={"file": ("empty.csv", b"", "text/csv")})
    assert resp.status_code == 400


def _upload_sample_csv(csv_bytes=SAMPLE_CSV, filename="test.csv"):
    with patch("services.semantic_engine.generate_semantic_layer") as mock_gen:
        mock_gen.return_value = {
            "metrics": [{"name": "total_revenue", "description": "Sum of revenue", "expr": "SUM(revenue)", "column": "revenue", "data_type": "numeric", "synonyms": ["revenue"]}],
            "dimensions": [{"name": "region", "description": "Geographic region", "column": "region", "data_type": "categorical", "sample_values": ["North", "South"]}],
            "time_dimensions": [{"name": "month", "description": "Month", "column": "month", "data_type": "date", "granularity": "monthly"}],
            "data_summary": "Monthly revenue by region.",
        }
        resp = client.post("/api/upload", files={"file": (filename, csv_bytes, "text/csv")})
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_upload_csv_returns_schema():
    data = _upload_sample_csv()
    assert "session_id" in data
    assert data["row_count"] == 4
    assert len(data["schema"]) == 4


def test_upload_tsv_accepted():
    tsv = b"name\tvalue\nalpha\t100\nbeta\t200\n"
    data = _upload_sample_csv(csv_bytes=tsv, filename="data.tsv")
    assert data["row_count"] == 2


def test_upload_stats_present():
    data = _upload_sample_csv()
    assert "revenue" in data["stats"]
    assert "min" in data["stats"]["revenue"]


def test_upload_semantic_layer_structure():
    data = _upload_sample_csv()
    sl = data["semantic_layer"]
    assert "metrics" in sl
    assert "dimensions" in sl
    assert "time_dimensions" in sl


# ── Ask endpoint ───────────────────────────────────────────────

def test_ask_without_session_returns_404():
    resp = client.post("/api/ask", json={"session_id": "bad-id", "question": "test?"})
    assert resp.status_code == 404


def _upload_and_ask(question, mode="auto"):
    upload_data = _upload_sample_csv()
    session_id = upload_data["session_id"]

    mock_pipeline_result = {
        "needs_clarification": False,
        "intent": "breakdown",
        "sql": 'SELECT "region", SUM("revenue") AS total_revenue FROM "dataset" GROUP BY "region"',
        "query_explanation": "Sums revenue by region",
        "data": [{"region": "North", "total_revenue": 98000}, {"region": "South", "total_revenue": 155000}],
        "columns": ["region", "total_revenue"],
        "total_rows": 2,
        "total_rows_in_dataset": 4,
        "explanation": "South leads with 155K in revenue.",
        "insight_line": "South outperforms North by 58%",
        "chart_type": "bar",
        "chart_config": {"x": "region", "y": "total_revenue"},
        "kpis": [{"label": "Total Revenue", "value": 253000, "formatted": "253K", "delta": None, "delta_label": ""}],
        "follow_ups": ["Show trend over time", "Break down by product"],
        "metrics_used": ["total_revenue"],
        "retried": False,
        "confidence": {"level": "high", "reason": "Exact metric match."},
        "coverage_pct": 100,
        "cached": False,
    }

    with patch("routes.query.run_pipeline", return_value=mock_pipeline_result):
        resp = client.post("/api/ask", json={"session_id": session_id, "question": question, "mode": mode})
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_ask_returns_required_fields():
    data = _upload_and_ask("Show revenue by region")
    for field in ("intent", "sql", "data", "columns", "total_rows", "explanation",
                  "chart_type", "confidence", "kpis", "follow_ups", "insight_line"):
        assert field in data, f"Missing: {field}"


def test_ask_confidence_structure():
    data = _upload_and_ask("Show revenue by region")
    assert data["confidence"]["level"] in ("high", "medium", "low")
    assert "reason" in data["confidence"]


def test_ask_has_kpis():
    data = _upload_and_ask("Show revenue by region")
    assert len(data["kpis"]) >= 1
    assert "label" in data["kpis"][0]


def test_ask_has_follow_ups():
    data = _upload_and_ask("Show revenue by region")
    assert len(data["follow_ups"]) >= 1


def test_ask_has_insight_line():
    data = _upload_and_ask("Show revenue by region")
    assert data["insight_line"] != ""


# ── Semantic layer ─────────────────────────────────────────────

def test_get_semantic_layer_not_found():
    assert client.get("/api/semantic-layer/no-such-session").status_code == 404


def test_put_semantic_layer_not_found():
    resp = client.put("/api/semantic-layer", json={"session_id": "no-such", "semantic_layer": {}})
    assert resp.status_code == 404


def test_get_and_update_semantic_layer():
    data = _upload_sample_csv()
    sid = data["session_id"]

    resp = client.get(f"/api/semantic-layer/{sid}")
    assert resp.status_code == 200
    assert "metrics" in resp.json()

    new_layer = {"metrics": [], "dimensions": [], "time_dimensions": [], "data_summary": "Updated."}
    resp = client.put("/api/semantic-layer", json={"session_id": sid, "semantic_layer": new_layer})
    assert resp.status_code == 200

    resp = client.get(f"/api/semantic-layer/{sid}")
    assert resp.json()["data_summary"] == "Updated."


# ── Schema analyzer ────────────────────────────────────────────

def test_schema_analyzer_numeric_stats():
    from services.schema_analyzer import analyze_schema
    conn = duckdb.connect()
    conn.execute("CREATE TABLE t AS SELECT * FROM (VALUES (1, 'a'), (2, 'b'), (3, 'c')) AS v(num, cat)")
    schema, stats, sample, row_count = analyze_schema(conn, "t")
    assert row_count == 3
    assert stats["num"]["min"] == 1
    assert stats["num"]["max"] == 3


def test_schema_analyzer_empty_table():
    from services.schema_analyzer import analyze_schema
    conn = duckdb.connect()
    conn.execute("CREATE TABLE empty_t (id INTEGER, name VARCHAR)")
    schema, stats, sample, row_count = analyze_schema(conn, "empty_t")
    assert row_count == 0
    assert sample == []


def test_schema_analyzer_single_column():
    from services.schema_analyzer import analyze_schema
    conn = duckdb.connect()
    conn.execute("CREATE TABLE single_col (val INTEGER)")
    conn.execute("INSERT INTO single_col VALUES (10), (20), (30)")
    schema, stats, sample, row_count = analyze_schema(conn, "single_col")
    assert len(schema) == 1
    assert row_count == 3


# ── Query pipeline unit tests ──────────────────────────────────

def test_pipeline_confidence_high():
    from services.query_pipeline import _compute_confidence
    level, _ = _compute_confidence(retried=False, rows_returned=25, metrics_matched=["Revenue"])
    assert level == "high"


def test_pipeline_confidence_low():
    from services.query_pipeline import _compute_confidence
    level, _ = _compute_confidence(retried=True, rows_returned=1, metrics_matched=[])
    assert level == "low"


def test_pipeline_confidence_medium():
    from services.query_pipeline import _compute_confidence
    level, _ = _compute_confidence(retried=True, rows_returned=15, metrics_matched=["Rev"])
    assert level == "medium"


def test_pipeline_find_matched_metrics():
    from services.query_pipeline import _find_matched_metrics_enriched
    semantic_layer = {
        "metrics": [
            {"name": "total_revenue", "synonyms": ["revenue", "lending volume"], "expr": "SUM(\"revenue\")"},
            {"name": "default_rate", "synonyms": ["defaults"], "expr": "AVG(\"default_rate\")"},
        ]
    }
    analyst_result = {"relevant_metrics": [], "relevant_dimensions": []}
    matched = _find_matched_metrics_enriched("Show me total revenue by region", semantic_layer, analyst_result)
    matched_names = [m["name"] for m in matched]
    assert "total_revenue" in matched_names


def test_pipeline_find_matched_metrics_by_synonym():
    from services.query_pipeline import _find_matched_metrics_enriched
    semantic_layer = {
        "metrics": [
            {"name": "total_disbursed", "synonyms": ["lending volume", "loan amount"], "expr": "SUM(\"disbursed\")"},
        ]
    }
    analyst_result = {"relevant_metrics": [], "relevant_dimensions": []}
    matched = _find_matched_metrics_enriched("What is the lending volume?", semantic_layer, analyst_result)
    matched_names = [m["name"] for m in matched]
    assert "total_disbursed" in matched_names


# ── Cache ──────────────────────────────────────────────────────

def test_cache_hit_and_miss():
    from utils.cache import get_cached, set_cached, invalidate_session
    invalidate_session("test-session")
    assert get_cached("test-session", "hello?") is None

    set_cached("test-session", "hello?", {"answer": 42})
    result = get_cached("test-session", "hello?")
    assert result is not None
    assert result["answer"] == 42

    invalidate_session("test-session")
    assert get_cached("test-session", "hello?") is None


def test_cache_normalized_question():
    from utils.cache import get_cached, set_cached, invalidate_session
    invalidate_session("test-norm")
    set_cached("test-norm", "What is revenue?", {"val": 1})
    # Same question with different casing/punctuation should hit cache
    assert get_cached("test-norm", "what is revenue") is not None
    invalidate_session("test-norm")


# ── Chart recommender ──────────────────────────────────────────

def test_chart_recommender_valid_bar():
    from services.chart_recommender import validate_and_fix_chart_config
    ct, cfg = validate_and_fix_chart_config({"chart_type": "bar", "chart_config": {"x": "region", "y": "rev"}}, ["region", "rev"], 5)
    assert ct == "bar"


def test_chart_recommender_bad_columns_fallback():
    from services.chart_recommender import validate_and_fix_chart_config
    ct, _ = validate_and_fix_chart_config({"chart_type": "bar", "chart_config": {"x": "ghost", "y": "ghost"}}, ["result"], 5)
    assert ct == "table"


def test_chart_recommender_number_single_cell():
    from services.chart_recommender import validate_and_fix_chart_config
    ct, _ = validate_and_fix_chart_config({"chart_type": "number", "chart_config": {}}, ["total"], 1)
    assert ct == "number"


# ── Sample dataset integrity ───────────────────────────────────

SAMPLES_DIR = Path(__file__).resolve().parents[1] / "assets" / "samples"


@pytest.mark.parametrize("filename,min_rows,expected_cols", [
    ("sme_lending.csv", 50, ["month", "region", "product_type", "approvals"]),
    ("customer_support.csv", 60, ["channel", "category", "tickets", "satisfaction_score"]),
    ("digital_banking.csv", 90, ["platform", "active_users", "transactions", "churn_rate"]),
])
def test_sample_dataset_integrity(filename, min_rows, expected_cols):
    import pandas as pd
    filepath = SAMPLES_DIR / filename
    if not filepath.exists():
        pytest.skip(f"{filename} not found")
    df = pd.read_csv(filepath)
    assert len(df) >= min_rows
    for col in expected_cols:
        assert col in df.columns, f"{filename}: missing '{col}'"
