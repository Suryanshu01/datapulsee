"""
Tests for the SQL sanitizer — ensures LLM-generated SQL is safe before execution.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src" / "backend"))

from utils.sql_sanitizer import sanitize_sql


def test_allows_select():
    result = sanitize_sql('SELECT "region", SUM("revenue") FROM dataset GROUP BY "region"')
    assert result["safe"] is True


def test_allows_with_cte():
    result = sanitize_sql('WITH cte AS (SELECT * FROM dataset) SELECT * FROM cte')
    assert result["safe"] is True


def test_blocks_drop():
    result = sanitize_sql('DROP TABLE dataset')
    assert result["safe"] is False
    assert "DROP" in result["reason"]


def test_blocks_delete():
    result = sanitize_sql('DELETE FROM dataset WHERE 1=1')
    assert result["safe"] is False


def test_blocks_update():
    result = sanitize_sql('UPDATE dataset SET revenue = 0')
    assert result["safe"] is False


def test_blocks_truncate():
    result = sanitize_sql('TRUNCATE TABLE dataset')
    assert result["safe"] is False


def test_blocks_create():
    result = sanitize_sql('CREATE TABLE evil AS SELECT * FROM dataset')
    assert result["safe"] is False


def test_blocks_insert():
    result = sanitize_sql('INSERT INTO dataset VALUES (1, 2, 3)')
    assert result["safe"] is False


def test_blocks_semicolon_injection():
    result = sanitize_sql('SELECT * FROM dataset; DROP TABLE dataset')
    assert result["safe"] is False


def test_blocks_comment_injection():
    result = sanitize_sql('SELECT * FROM dataset -- comment')
    assert result["safe"] is False


def test_blocks_block_comment():
    result = sanitize_sql('SELECT /* evil */ * FROM dataset')
    assert result["safe"] is False


def test_strips_markdown_fences():
    result = sanitize_sql('```sql\nSELECT * FROM dataset\n```')
    assert result["safe"] is True
    assert "```" not in result["sql"]


def test_strips_trailing_semicolon():
    result = sanitize_sql('SELECT * FROM dataset;')
    assert result["safe"] is True
    assert not result["sql"].endswith(";")


def test_empty_query():
    result = sanitize_sql('')
    assert result["safe"] is False


def test_whitespace_only():
    result = sanitize_sql('   ')
    assert result["safe"] is False


def test_returns_cleaned_sql():
    result = sanitize_sql('  SELECT * FROM dataset  ')
    assert result["safe"] is True
    assert result["sql"] == "SELECT * FROM dataset"


def test_exec_blocked():
    result = sanitize_sql('EXEC sp_something')
    assert result["safe"] is False


def test_grant_blocked():
    result = sanitize_sql('GRANT ALL ON dataset TO public')
    assert result["safe"] is False
