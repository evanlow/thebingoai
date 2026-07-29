"""Tests for `normalize_sql_for` — widget SQL dialect + reserved-word repair.

The bug this guards: the dashboard agent writes ANSI double-quoted identifiers
whatever the execution surface is, so `c."role"` reaches BigQuery as a *string
literal* and a column literally named `left` is a syntax error everywhere. Both
shipped a permanently-dead widget (dashboard 39, `pivot_table_14`).
"""
from backend.services.schema_utils import normalize_sql_for

# The exact SQL persisted for dashboard 39 / pivot_table_14.
BROKEN = (
    'SELECT c."role" AS role, c."salary" AS salary, c."left" AS left '
    'FROM csv_104 c WHERE c."role" IS NOT NULL AND c."salary" IS NOT NULL'
)


def test_bigquery_gets_backticked_identifiers():
    out = normalize_sql_for(BROKEN, "bigquery")
    assert "`role`" in out
    assert "`salary`" in out
    assert '"role"' not in out  # would be a string literal on BigQuery


def test_reserved_word_alias_is_quoted_for_every_dialect():
    assert "AS `left`" in normalize_sql_for(BROKEN, "bigquery")
    assert 'AS "left"' in normalize_sql_for(BROKEN, "duckdb")


def test_duckdb_keeps_ansi_quoting():
    out = normalize_sql_for(BROKEN, "duckdb")
    assert '"role"' in out and "`" not in out


def test_clean_sql_is_returned_byte_identical():
    sql = (
        "SELECT department, COUNT(*) AS cnt FROM csv_104 "
        "GROUP BY department ORDER BY cnt DESC LIMIT 10"
    )
    # Same quoting flavour and nothing to quote → no re-emit at all, so a
    # transpile bug can never touch a widget that already works.
    assert normalize_sql_for(sql, "duckdb") == sql
    assert normalize_sql_for(sql, "postgres") == sql


def test_string_literal_is_not_turned_into_an_identifier():
    sql = "SELECT COUNT(*) FROM t WHERE role = 'left'"
    for dialect in ("duckdb", "bigquery", "postgres"):
        assert "'left'" in normalize_sql_for(sql, dialect)


def test_bigquery_flavoured_input_keeps_double_quoted_strings():
    # Backticks mark the SQL as BigQuery-flavoured, where "..." is a string.
    # Reading it as ANSI would silently convert it to an identifier.
    sql = 'SELECT c.`role`, "Bob" AS who FROM t c'
    assert '"Bob"' in normalize_sql_for(sql, "bigquery")


def test_unparseable_sql_is_returned_unchanged():
    junk = "this is not sql at all (("
    assert normalize_sql_for(junk, "duckdb") == junk


def test_missing_sql_or_dialect_is_a_noop():
    assert normalize_sql_for("", "duckdb") == ""
    assert normalize_sql_for("SELECT 1", "") == "SELECT 1"
    assert normalize_sql_for("SELECT 1", "not-a-dialect") == "SELECT 1"


def test_mixed_case_identifier_is_left_alone():
    # Quoting "Left" under Postgres' unquoted case folding would change which
    # column it resolves to. Skipping is no worse than today.
    sql = 'SELECT "x" AS Left FROM t'
    assert '"Left"' not in normalize_sql_for(sql, "postgres")
