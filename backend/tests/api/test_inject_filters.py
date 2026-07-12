"""Tests for widget filter injection across BigQuery and DuckDB dialects.

Covers the `dialect` arg added for DataPlane DuckDB serving (GAP-5): the same
AST-built conditions must render with the correct placeholder sigil and stay
parseable in each dialect.
"""
import sqlglot

from backend.api.widget_data import inject_filters
from backend.schemas.widget_data import FilterParam


def _f(column, op, value):
    return FilterParam(column=column, op=op, value=value)


# --- BigQuery (default) path unchanged -------------------------------------

def test_bigquery_emits_psycopg_placeholders():
    # The BQ path rewrites placeholders to psycopg2 `%(name)s` (bound by the
    # source-DB connector), which is intentionally not re-parseable SQL.
    sql = "SELECT region, SUM(revenue) AS r FROM `csv_1` GROUP BY region"
    out, params = inject_filters(sql, [_f("region", "eq", "EMEA")])
    assert "%(_f0)s" in out
    assert "`region` = %(_f0)s" in out
    assert params == {"_f0": "EMEA"}


def test_bigquery_in_operator_multikey():
    sql = "SELECT * FROM `csv_1`"
    out, params = inject_filters(sql, [_f("region", "in", ["EMEA", "APAC"])])
    assert "%(_f0_0)s" in out and "%(_f0_1)s" in out
    assert params == {"_f0_0": "EMEA", "_f0_1": "APAC"}


# --- MySQL / Postgres source-DB path ---------------------------------------

def test_mysql_emits_psycopg_placeholders():
    # MySQL/Postgres render exp.Placeholder as `:name`; it must be rewritten to
    # the pymysql/psycopg2 `%(name)s` form. A raw `:_f0` reaches the driver and
    # triggers a (1064) syntax error.
    sql = "SELECT status, COUNT(*) AS c FROM orders GROUP BY status"
    out, params = inject_filters(sql, [_f("status", "eq", "paid")], dialect="mysql")
    assert "%(_f0)s" in out
    assert ":_f0" not in out
    assert params == {"_f0": "paid"}


def test_postgres_emits_psycopg_placeholders():
    sql = "SELECT country, COUNT(*) AS c FROM customers GROUP BY country"
    out, params = inject_filters(sql, [_f("country", "eq", "Malaysia")], dialect="postgres")
    assert "%(_f0)s" in out
    assert ":_f0" not in out
    assert params == {"_f0": "Malaysia"}


# --- DuckDB path -----------------------------------------------------------

def test_duckdb_emits_dollar_placeholders():
    sql = "SELECT region, SUM(revenue) AS r FROM csv_1 GROUP BY region"
    out, params = inject_filters(sql, [_f("region", "eq", "EMEA")], dialect="duckdb")
    assert "$_f0" in out
    assert "%(_f0)s" not in out
    assert params == {"_f0": "EMEA"}
    sqlglot.parse_one(out, read="duckdb", error_level=sqlglot.ErrorLevel.RAISE)


def test_duckdb_in_operator_multikey():
    sql = "SELECT * FROM csv_1"
    out, params = inject_filters(sql, [_f("region", "in", ["EMEA", "APAC"])], dialect="duckdb")
    assert "$_f0_0" in out and "$_f0_1" in out
    assert params == {"_f0_0": "EMEA", "_f0_1": "APAC"}
    sqlglot.parse_one(out, read="duckdb", error_level=sqlglot.ErrorLevel.RAISE)


def test_duckdb_date_coercion_renders_cast():
    # When the column is a date-like type, the filter wraps it so a YYYY-MM-DD
    # string compares as a DATE. DuckDB renders this as CAST(... AS DATE).
    sql = "SELECT * FROM csv_1"
    ctx = {"dimensions": {"ts": {"column": "ts", "type": "TIMESTAMP"}}}
    out, params = inject_filters(
        sql, [_f("ts", "gte", "2024-01-01")], data_context=ctx, dialect="duckdb"
    )
    assert "CAST" in out.upper()
    assert "$_f0" in out
    sqlglot.parse_one(out, read="duckdb", error_level=sqlglot.ErrorLevel.RAISE)


def test_duckdb_ilike_casts_column_to_text():
    # A search control on a numeric column would make DuckDB raise a binder error
    # (~~*(BIGINT, STRING_LITERAL)). The predicate must cast the column to text so
    # ILIKE binds regardless of column type.
    sql = "SELECT * FROM gsheets_48_sheet1"
    out, params = inject_filters(sql, [_f("item_code", "ilike", "%1%")], dialect="duckdb")
    assert "CAST" in out.upper() and "ILIKE" in out.upper()
    assert params == {"_f0": "%1%"}
    sqlglot.parse_one(out, read="duckdb", error_level=sqlglot.ErrorLevel.RAISE)


def test_duckdb_qualifies_ambiguous_join_key():
    # item_code is an equi-join key present in both tables → an unqualified filter
    # reference raises "ambiguous reference". The injector must qualify it to a
    # join-side alias (s. or i.).
    sql = ("SELECT s.item_code, i.item_name FROM gsheets_48_sheet1 s "
           "JOIN gsheets_49_sheet1 i ON s.item_code = i.item_code")
    out, params = inject_filters(sql, [_f("item_code", "ilike", "%1%")], dialect="duckdb")
    assert "s.item_code" in out or "i.item_code" in out  # qualified, not bare
    assert "CAST" in out.upper()
    sqlglot.parse_one(out, read="duckdb", error_level=sqlglot.ErrorLevel.RAISE)


def test_duckdb_non_join_column_left_unqualified():
    # A filter on a column that is NOT a join key must stay unqualified — forcing
    # a wrong alias would break resolution.
    sql = "SELECT region, revenue FROM csv_1"
    out, params = inject_filters(sql, [_f("region", "eq", "EMEA")], dialect="duckdb")
    assert '"region" = $_f0' in out
    sqlglot.parse_one(out, read="duckdb", error_level=sqlglot.ErrorLevel.RAISE)


def test_no_filters_returns_sql_unchanged():
    sql = "SELECT * FROM csv_1"
    out, params = inject_filters(sql, [], dialect="duckdb")
    assert out == sql
    assert params == {}
