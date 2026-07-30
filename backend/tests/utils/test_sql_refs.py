import pytest

import sqlglot

from backend.utils.sql_refs import (
    extract_table_refs,
    qualifier_allowlist,
    rewrite_table_refs,
    can_parse,
    transpile_bq_to_duckdb,
    transpile_to_engine,
    UntranspilableSQLError,
)


def _assert_valid_duckdb(sql: str) -> None:
    """Raise if *sql* is not parseable as DuckDB."""
    sqlglot.parse_one(sql, read="duckdb", error_level=sqlglot.ErrorLevel.RAISE)


def test_extract_single_table():
    result = extract_table_refs("SELECT * FROM foo")
    assert result == ["foo"]


def test_extract_multiple_tables():
    result = extract_table_refs("SELECT * FROM foo JOIN bar ON foo.id = bar.id")
    assert result == ["bar", "foo"]


def test_extract_unparseable():
    result = extract_table_refs("garbage that can't parse")
    assert result == []


def test_extract_excludes_cte_names():
    """A CTE has no storage — returning its name made the DuckDB reader mount
    `gs://.../bands/dt=*/*.parquet`, fail, and drop the widget to the source DB.
    This is the real dashboard-39 chart_8 shape.
    """
    sql = (
        'WITH bands AS ('
        '  SELECT CASE WHEN c."exp_in_company" < 2 THEN \'<2 years\' ELSE \'>2 years\' END'
        '         AS tenure_band'
        '  FROM csv_104 c'
        ') '
        'SELECT tenure_band, COUNT(*) FROM bands GROUP BY 1'
    )
    assert extract_table_refs(sql) == ["csv_104"]


def test_extract_excludes_multiple_and_nested_ctes():
    sql = (
        "WITH a AS (WITH b AS (SELECT * FROM real_t) SELECT * FROM b), "
        "c AS (SELECT * FROM other_t) "
        "SELECT * FROM a JOIN c ON a.id = c.id"
    )
    assert extract_table_refs(sql) == ["other_t", "real_t"]


def test_extract_excludes_cte_shadowing_a_real_table():
    """`orders` resolves to the CTE inside this query, so mounting the physical
    `orders` table would serve different data than the SQL asks for."""
    sql = "WITH orders AS (SELECT * FROM raw_orders) SELECT * FROM orders"
    assert extract_table_refs(sql) == ["raw_orders"]


def test_cte_does_not_hide_the_physical_table_it_reads():
    """A non-recursive CTE cannot reference itself, so the inner `orders` is the
    real table. Matching bare names statement-wide swallowed it and returned [] —
    and the org-governance plugin enforces per-table ACLs by iterating this list,
    so an empty list means no authorization check runs at all.
    """
    sql = "WITH orders AS (SELECT * FROM orders) SELECT * FROM orders"
    assert extract_table_refs(sql) == ["orders"]


def test_a_qualified_ref_survives_a_same_named_cte():
    """`node.name` drops the qualifier, so `public.orders` used to collide with a
    CTE called `orders` and disappear."""
    sql = "WITH orders AS (SELECT * FROM public.orders) SELECT * FROM orders"
    assert extract_table_refs(sql) == ["orders"]


def test_a_name_that_is_a_cte_in_one_scope_and_a_table_in_another():
    """CTE bindings are per-scope: `t` is a CTE inside the derived table only, and
    the outer `t` is a real table. Physical must win."""
    sql = "SELECT * FROM (WITH t AS (SELECT 1 AS x) SELECT * FROM t) a JOIN t ON 1 = 1"
    assert extract_table_refs(sql) == ["t"]


def test_recursive_cte_self_reference_is_still_excluded():
    sql = "WITH RECURSIVE r AS (SELECT 1 AS n UNION ALL SELECT n FROM r) SELECT * FROM r"
    assert extract_table_refs(sql) == []


def test_insert_target_is_reported():
    """The scope walk doesn't reach an INSERT target, so the backfill has to."""
    assert extract_table_refs("INSERT INTO t SELECT * FROM src") == ["src", "t"]


def test_rewrite_single_table():
    result_sql, success = rewrite_table_refs("SELECT * FROM legacy", {"legacy": "new_table"})
    assert success is True
    assert "new_table" in result_sql


def test_rewrite_with_cte():
    sql = "WITH cte AS (SELECT * FROM legacy) SELECT * FROM cte"
    result_sql, success = rewrite_table_refs(sql, {"legacy": "new_table"})
    assert success is True
    assert "new_table" in result_sql


def test_rewrite_case_insensitive():
    result_sql, success = rewrite_table_refs("SELECT * FROM legacy", {"LEGACY": "new"})
    assert success is True
    assert "new" in result_sql


def test_rewrite_unparseable():
    bad_sql = "SELECT @@@;###"
    result_sql, success = rewrite_table_refs(bad_sql, {"a": "b"})
    assert success is False
    assert result_sql == bad_sql


class _Conn:
    def __init__(self, db_type, database=""):
        self.db_type = db_type
        self.database = database


@pytest.mark.parametrize("db_type,expected", [
    ("postgres", {"public"}),
    ("postgresql", {"public"}),
    ("sqlite", {"main"}),
    ("mssql", {"dbo"}),
    ("sqlserver", {"dbo"}),
    ("bigquery", None),
    ("", None),
])
def test_qualifier_allowlist_by_db_type(db_type, expected):
    assert qualifier_allowlist(_Conn(db_type)) == expected


def test_qualifier_allowlist_db_type_case_insensitive():
    assert qualifier_allowlist(_Conn("Postgres")) == {"public"}


def test_qualifier_allowlist_mysql_uses_database_name():
    assert qualifier_allowlist(_Conn("mysql", database="Shop")) == {"shop"}


def test_qualifier_allowlist_mysql_without_database_is_none():
    assert qualifier_allowlist(_Conn("mysql")) is None


def test_rewrite_drops_qualifier_in_allowlist():
    result_sql, success = rewrite_table_refs(
        "SELECT * FROM public.orders", {"orders": "acme__orders"}, {"public"}
    )
    assert success is True
    assert "acme__orders" in result_sql
    assert "public" not in result_sql


def test_rewrite_skips_qualifier_outside_allowlist():
    sql = "SELECT * FROM archive.orders"
    result_sql, success = rewrite_table_refs(sql, {"orders": "acme__orders"}, {"public"})
    assert success is True
    assert "archive.orders" in result_sql
    assert "acme__orders" not in result_sql


def test_rewrite_mixed_schemas_only_allowlisted_rewritten():
    sql = "SELECT * FROM public.orders o JOIN archive.orders a ON o.id = a.id"
    result_sql, success = rewrite_table_refs(sql, {"orders": "acme__orders"}, {"public"})
    assert success is True
    assert "acme__orders" in result_sql
    assert "archive.orders" in result_sql


def test_rewrite_unqualified_ref_rewritten_regardless_of_allowlist():
    result_sql, success = rewrite_table_refs(
        "SELECT * FROM orders", {"orders": "acme__orders"}, {"public"}
    )
    assert success is True
    assert "acme__orders" in result_sql


def test_rewrite_allowlist_none_drops_any_qualifier():
    result_sql, success = rewrite_table_refs(
        "SELECT * FROM proj.ds.orders", {"orders": "acme__orders"}, None
    )
    assert success is True
    assert "acme__orders" in result_sql
    assert "proj" not in result_sql
    assert "ds" not in result_sql


def test_rewrite_allowlist_schema_compare_case_insensitive():
    result_sql, success = rewrite_table_refs(
        "SELECT * FROM PUBLIC.orders", {"orders": "acme__orders"}, {"public"}
    )
    assert success is True
    assert "acme__orders" in result_sql


def test_can_parse_valid():
    assert can_parse("SELECT 1") is True


def test_can_parse_invalid():
    assert can_parse("NOT SQL AT ALL !!!") is False


# ---------------------------------------------------------------------------
# BQ → DuckDB transpile corpus (GAP-6)
# ---------------------------------------------------------------------------

def test_transpile_backticks_become_double_quotes():
    out = transpile_bq_to_duckdb("SELECT `col` FROM `tbl`")
    assert "`" not in out
    _assert_valid_duckdb(out)


def test_transpile_date_trunc_reorders_args():
    out = transpile_bq_to_duckdb("SELECT DATE_TRUNC(d, DAY) FROM t")
    # BigQuery DATE_TRUNC(col, unit) → DuckDB DATE_TRUNC('unit', col)
    assert "DATE_TRUNC('DAY', d)" in out
    _assert_valid_duckdb(out)


def test_transpile_safe_cast_becomes_try_cast():
    out = transpile_bq_to_duckdb("SELECT SAFE_CAST(x AS INT64) FROM t")
    assert "TRY_CAST" in out.upper()
    _assert_valid_duckdb(out)


def test_transpile_safe_divide_becomes_case():
    out = transpile_bq_to_duckdb("SELECT SAFE_DIVIDE(a, b) FROM t")
    assert "safe_divide" not in out.lower()  # must be rewritten, not passed through
    assert "CASE" in out.upper()
    _assert_valid_duckdb(out)


def test_transpile_date_sub_interval():
    out = transpile_bq_to_duckdb("SELECT DATE_SUB(d, INTERVAL 1 DAY) FROM t")
    assert "INTERVAL" in out.upper()
    _assert_valid_duckdb(out)


def test_transpile_extract_and_format_and_parse_date():
    for sql in (
        "SELECT EXTRACT(YEAR FROM d) FROM t",
        "SELECT FORMAT_DATE('%Y-%m', d) FROM t",
        "SELECT PARSE_DATE('%Y-%m-%d', s) FROM t",
        "SELECT APPROX_QUANTILES(x, 100) FROM t",
    ):
        out = transpile_bq_to_duckdb(sql)
        _assert_valid_duckdb(out)


def test_transpile_full_widget_query():
    sql = """
    SELECT DATE_TRUNC(`order_date`, DAY) AS d,
           SAFE_DIVIDE(SUM(`revenue`), COUNT(*)) AS avg_rev
    FROM `csv_42`
    WHERE `order_date` >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
    GROUP BY 1
    """
    out = transpile_bq_to_duckdb(sql)
    assert "`" not in out
    _assert_valid_duckdb(out)


def test_transpile_raises_on_parse_failure():
    with pytest.raises(UntranspilableSQLError):
        transpile_bq_to_duckdb("SELECT @@@ ;;; not valid sql")


def test_transpile_raises_on_unsupported_function():
    # ST_GEOGPOINT has no DuckDB-core equivalent — must fail loudly, not emit
    # SQL that errors at runtime.
    with pytest.raises(UntranspilableSQLError) as ei:
        transpile_bq_to_duckdb("SELECT ST_GEOGPOINT(lng, lat) FROM t")
    assert "st_geogpoint" in str(ei.value).lower()


# ---------------------------------------------------------------------------
# transpile_to_engine — generic dialect → dialect helper
# ---------------------------------------------------------------------------

def test_transpile_to_engine_postgres_to_duckdb_double_colon_cast():
    """Postgres `::` cast must render as a DuckDB-parseable CAST expression.

    sqlglot canonicalises `NUMERIC` to `DECIMAL` (DuckDB's native name), so we
    only assert the output parses and contains a cast keyword.
    """
    out = transpile_to_engine("SELECT amount::numeric FROM orders", source="postgres")
    _assert_valid_duckdb(out)
    lowered = out.lower()
    assert "cast" in lowered or "::" in lowered


def test_transpile_to_engine_mysql_to_duckdb_backticks():
    out = transpile_to_engine("SELECT `col` FROM `orders`", source="mysql")
    _assert_valid_duckdb(out)
    assert "`" not in out  # backticks must be rewritten to double-quotes


def test_transpile_to_engine_mysql_to_duckdb_year_function():
    out = transpile_to_engine("SELECT YEAR(created_at) FROM orders", source="mysql")
    _assert_valid_duckdb(out)


def test_transpile_to_engine_postgres_to_mysql_repairs_ansi_quotes():
    """The widget read path's ("postgres", …) attempt exists to repair ANSI
    double-quoted identifiers the agent sometimes emits — they parse fine on
    Postgres but break on MySQL. source="postgres", target="mysql" must rewrite
    `"col"` → backticks so the query runs on MySQL."""
    out = transpile_to_engine('SELECT "col" FROM "orders"', source="postgres", target="mysql")
    assert '"' not in out          # ANSI double-quotes must be gone
    assert "`col`" in out          # rewritten to MySQL backticks


def test_transpile_to_engine_postgres_to_postgres_short_circuits():
    """For a Postgres target the ("postgres", …) attempt is a same-dialect no-op:
    it must return the SQL verbatim (parse-validated), never corrupt native
    quoting — the widget loop relies on this being harmless."""
    sql = 'SELECT "col" FROM "tbl"'
    assert transpile_to_engine(sql, source="postgres", target="postgres") == sql


def test_transpile_to_engine_default_target_is_duckdb():
    """Omitting target should default to DuckDB."""
    out = transpile_to_engine("SELECT `c` FROM t", source="mysql")
    _assert_valid_duckdb(out)


def test_transpile_to_engine_same_dialect_short_circuits():
    """source == target → return input verbatim after parse-validation."""
    sql = 'SELECT "col" FROM "tbl"'
    assert transpile_to_engine(sql, source="duckdb", target="duckdb") == sql


def test_transpile_to_engine_rejects_unknown_dialect():
    with pytest.raises(UntranspilableSQLError) as ei:
        transpile_to_engine("SELECT 1", source="oracle")
    assert "unknown source dialect" in str(ei.value).lower()


def test_transpile_to_engine_rejects_unknown_target():
    with pytest.raises(UntranspilableSQLError) as ei:
        transpile_to_engine("SELECT 1", source="mysql", target="snowflake")
    assert "unknown target dialect" in str(ei.value).lower()


def test_transpile_to_engine_parse_failure_raises():
    """Truly broken input must raise; sqlglot's permissive parser means most
    'looks-bad' SQL still parses, so we test the function-catalog reject path
    above and rely on the generic raise here."""
    with pytest.raises(UntranspilableSQLError):
        # Re-parse step rejects this since the output is syntactically broken.
        transpile_to_engine("SELECT FROM WHERE FROM", source="postgres")


def test_transpile_to_engine_validates_duckdb_function_catalog():
    """Function-catalog check only fires when target is DuckDB."""
    with pytest.raises(UntranspilableSQLError):
        transpile_to_engine(
            "SELECT ST_GEOGPOINT(lng, lat) FROM t",
            source="bigquery",
        )


def test_transpile_bq_shim_still_works():
    """`transpile_bq_to_duckdb` is now a thin shim — must still pass."""
    out = transpile_bq_to_duckdb("SELECT `col` FROM `tbl`")
    _assert_valid_duckdb(out)
