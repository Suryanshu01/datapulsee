"""
Tests for the deterministic driver analysis engine.
"""

import sys
from pathlib import Path

import duckdb
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src" / "backend"))

from services.driver_analysis import compute_drivers, auto_detect_periods, run_multi_dimension_analysis


@pytest.fixture
def sample_db():
    conn = duckdb.connect()
    conn.execute("""
        CREATE TABLE dataset AS SELECT * FROM (VALUES
            ('2024-01', 'North', 100),
            ('2024-01', 'South', 200),
            ('2024-02', 'North', 120),
            ('2024-02', 'South', 150)
        ) AS t(month, region, revenue)
    """)
    return conn


def test_compute_drivers_basic(sample_db):
    result = compute_drivers(
        sample_db, "revenue", "month", "region", "2024-02", "2024-01"
    )
    # (120+150) - (100+200) = 270 - 300 = -30
    assert result["total_change"] == -30
    assert len(result["drivers"]) == 2
    # South dropped 50, North grew 20 => South has the larger absolute change
    south = [d for d in result["drivers"] if d["dimension_value"] == "South"][0]
    assert south["change"] == -50


def test_compute_drivers_total_values(sample_db):
    result = compute_drivers(
        sample_db, "revenue", "month", "region", "2024-02", "2024-01"
    )
    assert result["total_current"] == 270  # 120 + 150
    assert result["total_previous"] == 300  # 100 + 200
    assert result["total_change_pct"] == -10.0  # -30/300 * 100


def test_compute_drivers_contribution(sample_db):
    result = compute_drivers(
        sample_db, "revenue", "month", "region", "2024-02", "2024-01"
    )
    # South: change = -50, total_change = -30 => contribution = -50/-30 * 100 ≈ 166.7%
    # North: change = +20, total_change = -30 => contribution = 20/-30 * 100 ≈ -66.7%
    south = [d for d in result["drivers"] if d["dimension_value"] == "South"][0]
    north = [d for d in result["drivers"] if d["dimension_value"] == "North"][0]
    assert south["contribution_pct"] != 0
    assert north["contribution_pct"] != 0


def test_auto_detect_periods(sample_db):
    periods = auto_detect_periods(sample_db, "month")
    assert periods["current"] == "2024-02"
    assert periods["previous"] == "2024-01"


def test_auto_detect_periods_single(sample_db):
    conn = duckdb.connect()
    conn.execute("""
        CREATE TABLE dataset AS SELECT * FROM (VALUES
            ('2024-01', 'North', 100)
        ) AS t(month, region, revenue)
    """)
    periods = auto_detect_periods(conn, "month")
    assert periods["current"] == "2024-01"
    assert periods["previous"] == "2024-01"


def test_no_division_by_zero(sample_db):
    # Add a period with only one region (previous has 0 for West)
    sample_db.execute("INSERT INTO dataset VALUES ('2024-03', 'West', 50)")
    result = compute_drivers(
        sample_db, "revenue", "month", "region", "2024-03", "2024-01"
    )
    assert result is not None
    assert "error" not in result
    # West had 0 previously, 50 now — change_pct should be 0 (no div by zero)
    west = [d for d in result["drivers"] if d["dimension_value"] == "West"][0]
    assert west["change_pct"] == 0  # previous was 0


def test_compute_drivers_returns_top_driver(sample_db):
    result = compute_drivers(
        sample_db, "revenue", "month", "region", "2024-02", "2024-01"
    )
    assert result["top_driver"] is not None
    assert result["top_driver"] in ["South", "North"]


def test_run_multi_dimension_analysis(sample_db):
    result = run_multi_dimension_analysis(
        sample_db, "revenue", "month", ["region"],
        "2024-02", "2024-01"
    )
    assert "best_dimension" in result
    assert "results" in result
    assert result["best_dimension"] == "region"


def test_compute_drivers_bad_column(sample_db):
    # Should return error dict, not raise exception
    result = compute_drivers(
        sample_db, "nonexistent_col", "month", "region", "2024-02", "2024-01"
    )
    assert "error" in result
