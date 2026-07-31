"""Dataset profiling must survive column names that are SQL keywords.

The CSV connector sanitizes headers to [a-z0-9_], which makes the characters
legal but not the word. A column named `left` made BigQuery read it as the start
of its LEFT() function — `MIN(left)` failed with `Expected "(" but got ")"`, and
because all numeric columns share one scan, a single such column wiped out the
stats for every numeric column in the table (thread 78d2eb7a).

No quote character is native to both engines: backticks are a parse error on
DuckDB, and double quotes are string literals on BigQuery (they work through the
plane only because BigQueryGCSPlane._rewrite_sql converts them to backticks — not
something this module should lean on). The profiler qualifies dataset columns with
a table alias instead, which is a path expression on both. This test runs the real
generated SQL through DuckDB — the local-plane engine.
"""
from types import SimpleNamespace

import duckdb
import pytest

from backend.services.table_profiler import profile_table


class _DuckConnector:
    """Minimal connector over an in-memory DuckDB, recording the SQL it runs."""

    def __init__(self, con):
        self._con = con
        self.queries: list[str] = []

    def execute_query(self, sql: str):
        self.queries.append(sql)
        return SimpleNamespace(rows=self._con.execute(sql).fetchall())


@pytest.fixture
def duck_connector():
    con = duckdb.connect()
    # `left` and `order` are keywords/functions; `salary` is an ordinary name.
    con.execute(
        'CREATE TABLE csv_1 AS SELECT * FROM (VALUES '
        "(1, 10, 'low'), (0, 20, 'high'), (1, 30, 'low')"
        ') AS t("left", "order", salary)'
    )
    return _DuckConnector(con)


_COLUMNS = [
    {"name": "left", "type": "integer"},
    {"name": "order", "type": "integer"},
    {"name": "salary", "type": "text"},
]


def _profile(connector):
    return profile_table(
        connector=connector,
        table_name="csv_1",
        schema_name=None,
        columns=_COLUMNS,
        row_count=3,
        db_type="postgres",
        is_dataset=True,
    )


def test_keyword_columns_are_profiled_not_errored(duck_connector):
    out = _profile(duck_connector)

    assert [c for c, d in out["columns"].items() if "error" in d] == []
    assert out["columns"]["left"]["min"] == 0
    assert out["columns"]["left"]["max"] == 1
    assert out["columns"]["order"]["avg"] == pytest.approx(20.0)


def test_an_ordinary_column_still_profiles_alongside_them(duck_connector):
    out = _profile(duck_connector)

    salary = out["columns"]["salary"]
    assert salary["type"] == "categorical"
    assert salary["distinct_count"] == 2
    assert sorted(salary["top_values"]) == ["high", "low"]


def test_dataset_sql_qualifies_columns_with_a_table_alias(duck_connector):
    """The mechanism, pinned: bare `MIN(left)` is what broke BigQuery, and neither
    quote character is portable, so column refs must carry the alias."""
    _profile(duck_connector)
    stats_sql = duck_connector.queries[0]

    assert "csv_1 AS bingo_t" in stats_sql
    assert "MIN(bingo_t.left)" in stats_sql
    assert "MIN(left)" not in stats_sql
    assert "`" not in stats_sql
    assert '"left"' not in stats_sql


def test_non_dataset_connections_keep_native_quoting(duck_connector):
    """Postgres/MySQL/BigQuery tables are quoted properly already — the alias is
    dataset-only, so this path must be untouched."""
    profile_table(
        connector=duck_connector,
        table_name="csv_1",
        schema_name=None,
        columns=_COLUMNS,
        row_count=3,
        db_type="postgres",
        is_dataset=False,
    )
    assert 'MIN("left")' in duck_connector.queries[0]
    assert "bingo_t" not in duck_connector.queries[0]
