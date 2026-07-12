"""Tests for DB-catalog comment extraction (semantic-layer glossary bootstrap).

Covers the two overridable hooks (`_get_column_comments`, `_get_table_comment`)
on the Postgres/MySQL connectors, the base no-op default, and the base
`get_table_schema` wiring that attaches comments onto the returned schema.
"""
from typing import ClassVar
from unittest.mock import MagicMock

from backend.connectors.base import BaseConnector, TableSchema
from backend.connectors.postgres import PostgresConnector
from backend.connectors.mysql import MySQLConnector


class FakeCursor:
    """Cursor stub whose fetchall/fetchone return queued result sets in order."""

    def __init__(self, result_sets):
        self._queue = list(result_sets)
        self._current = []
        self.executed = []  # (sql, params) tuples, for assertions

    def execute(self, sql, params=None):
        self.executed.append((sql, params))
        self._current = self._queue.pop(0) if self._queue else []

    def fetchall(self):
        return self._current

    def fetchone(self):
        return self._current[0] if self._current else None

    def close(self):
        pass


def _pg():
    return PostgresConnector(host="h", port=5432, database="d", username="u", password="p")


def _mysql():
    return MySQLConnector(host="h", port=3306, database="d", username="u", password="p")


# --- Postgres overrides ------------------------------------------------------

def test_pg_column_comments_skips_empty_and_none():
    cur = FakeCursor([[
        {"column_name": "id", "comment": "primary key"},
        {"column_name": "cust_nm", "comment": "Customer Name"},
        {"column_name": "tmp", "comment": None},
    ]])
    out = _pg()._get_column_comments(cur, "public", "orders")
    assert out == {"id": "primary key", "cust_nm": "Customer Name"}
    sql = cur.executed[0][0]
    assert "pg_description" in sql and "pg_attribute" in sql


def test_pg_table_comment():
    cur = FakeCursor([[{"comment": "All customer orders"}]])
    assert _pg()._get_table_comment(cur, "public", "orders") == "All customer orders"


def test_pg_table_comment_none_when_absent():
    cur = FakeCursor([[{"comment": None}]])
    assert _pg()._get_table_comment(cur, "public", "orders") is None


# --- MySQL overrides ---------------------------------------------------------

def test_mysql_column_comments_treats_blank_as_absent():
    # MySQL returns '' (never NULL) for undocumented columns.
    cur = FakeCursor([[
        {"column_name": "amt_lcy", "column_comment": "Amount in local currency"},
        {"column_name": "flg", "column_comment": ""},
    ]])
    out = _mysql()._get_column_comments(cur, "shop", "sales")
    assert out == {"amt_lcy": "Amount in local currency"}
    assert "column_comment" in cur.executed[0][0]


def test_mysql_table_comment_blank_is_none():
    cur = FakeCursor([[{"table_comment": ""}]])
    assert _mysql()._get_table_comment(cur, "shop", "sales") is None


# --- Base default is a no-op -------------------------------------------------

class _StubConnector(BaseConnector):
    """Minimal concrete connector for exercising base template logic."""

    _db_type_name: ClassVar[str] = "Stub"
    _quote_char: ClassVar[str] = '"'

    def _create_connection(self, **kwargs):
        return MagicMock()

    def _is_connection_alive(self, conn):
        return True

    def _get_cursor(self, conn, dict_mode=False):
        return conn  # the test injects a FakeCursor as the "connection"

    def _get_connect_kwargs(self):
        return {}


def test_base_default_comment_hooks_are_empty():
    c = _StubConnector(host="h", port=1, database="d", username="u", password="p")
    assert c._get_column_comments(None, "s", "t") == {}
    assert c._get_table_comment(None, "s", "t") is None


def test_get_table_schema_attaches_comments():
    """Base get_table_schema must merge column + table comments from the hooks."""
    cur = FakeCursor([
        # columns query
        [{"column_name": "id", "data_type": "integer", "is_nullable": "NO", "column_default": None},
         {"column_name": "cust_nm", "data_type": "text", "is_nullable": "YES", "column_default": None}],
        # primary key query
        [{"column_name": "id"}],
        # _get_row_count (base COUNT(*))
        [{"count": 42}],
    ])

    c = _StubConnector(host="h", port=1, database="d", username="u", password="p")
    c._connection = cur  # _get_connection returns this; _get_cursor returns it too
    c._get_column_comments = lambda cursor, schema, table: {"cust_nm": "Customer Name"}
    c._get_table_comment = lambda cursor, schema, table: "Customer records"

    schema = c.get_table_schema("customers", "public")
    assert isinstance(schema, TableSchema)
    assert schema.comment == "Customer records"
    by_name = {col["name"]: col for col in schema.columns}
    assert by_name["cust_nm"]["comment"] == "Customer Name"
    assert "comment" not in by_name["id"]  # no comment → key absent


def test_get_table_schema_survives_hook_failure():
    """A failing comment hook must not break schema discovery."""
    cur = FakeCursor([
        [{"column_name": "id", "data_type": "integer", "is_nullable": "NO", "column_default": None}],
        [{"column_name": "id"}],
        [{"count": 1}],
    ])
    c = _StubConnector(host="h", port=1, database="d", username="u", password="p")
    c._connection = cur

    def _boom(*a, **k):
        raise RuntimeError("catalog unavailable")

    c._get_column_comments = _boom
    c._get_table_comment = _boom

    schema = c.get_table_schema("t", "public")
    assert schema.comment is None
    assert "comment" not in schema.columns[0]
