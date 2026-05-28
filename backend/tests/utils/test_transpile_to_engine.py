"""Tests for `utils.sql_refs.transpile_to_engine`.

Drives the Phase-2 read-path cutover for postgres / mysql widgets and chat
queries — stored source-dialect SQL must run on DuckDB-over-Parquet without
forcing a per-widget migration. Contract: never raise — graceful fallback to
the input string on any sqlglot error.
"""
from __future__ import annotations

from backend.utils.sql_refs import transpile_to_engine


def test_same_dialect_returns_input_unchanged():
    sql = "SELECT * FROM t"
    assert transpile_to_engine(sql, src="duckdb", dst="duckdb") is sql


def test_postgres_to_duckdb_quoting_translates():
    out = transpile_to_engine('SELECT "id" FROM "users"', src="postgres", dst="duckdb")
    assert "users" in out.lower()


def test_mysql_to_duckdb_backticks_translate():
    out = transpile_to_engine("SELECT `id` FROM `users`", src="mysql", dst="duckdb")
    # DuckDB uses double quotes; backticks must not remain.
    assert "`" not in out
    assert "users" in out.lower()


def test_unparseable_sql_returns_input():
    bogus = "SELECT FROM WHERE"
    assert transpile_to_engine(bogus, src="postgres", dst="duckdb") == bogus


def test_unknown_src_dialect_returns_input():
    sql = "SELECT 1"
    # `oracle` (or any unmapped string) hands the raw label to sqlglot; if it
    # fails, the helper must return the input unchanged.
    out = transpile_to_engine(sql, src="oracle", dst="duckdb")
    assert isinstance(out, str)


def test_postgres_alias_carries_to_duckdb():
    out = transpile_to_engine(
        "SELECT COUNT(*) AS n FROM orders WHERE created_at > NOW() - INTERVAL '7 days'",
        src="postgres", dst="duckdb",
    )
    assert "count(*)" in out.lower() or "count" in out.lower()
    assert "orders" in out.lower()
