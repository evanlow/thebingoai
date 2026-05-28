"""Tests for the chat data-agent plane redirect.

Covers `_maybe_serve_chat_from_plane` in `backend.agents.data_agent.tools`:
when a postgres/mysql connection's referenced tables all have Parquet on the
DataPlane, the chat tool serves from DuckDB-over-plane instead of running
live against the source DB.
"""
from __future__ import annotations

import sys
import types as _types
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


# Stub everything backend.agents.data_agent.tools imports at module-load.
@pytest.fixture(autouse=True)
def _stub_module_deps(monkeypatch):
    # langchain_core.tools.tool — make it a pass-through decorator.
    lc_tools = _types.ModuleType("langchain_core.tools")
    lc_tools.tool = lambda f: f
    lc_core = _types.ModuleType("langchain_core")
    lc_core.tools = lc_tools
    monkeypatch.setitem(sys.modules, "langchain_core", lc_core)
    monkeypatch.setitem(sys.modules, "langchain_core.tools", lc_tools)

    # Schema discovery / query result store / connectors.factory — stubs.
    for name, attrs in [
        ("backend.services.schema_discovery", {"load_schema_file": MagicMock(return_value={})}),
        (
            "backend.services.query_result_store",
            {"store_query_result": MagicMock(), "publish_query_result": MagicMock()},
        ),
        (
            "backend.connectors.factory",
            {
                "get_connector_for_connection": MagicMock(),
                "get_connector_registration": MagicMock(),
            },
        ),
        ("backend.database.session", {"SessionLocal": MagicMock()}),
        ("backend.models.database_connection", {"DatabaseConnection": MagicMock()}),
        ("backend.agents.context", {"AgentContext": MagicMock()}),
    ]:
        m = _types.ModuleType(name)
        for k, v in attrs.items():
            setattr(m, k, v)
        monkeypatch.setitem(sys.modules, name, m)

    # Force fresh import.
    sys.modules.pop("backend.agents.data_agent.tools", None)


def _conn(db_type="postgres"):
    return SimpleNamespace(id=1, db_type=db_type)


def _qr(columns, rows):
    """Stand-in for QueryResult."""
    return SimpleNamespace(columns=columns, rows=rows, row_count=len(rows),
                           execution_time_ms=1.0, truncated=False)


# ── _maybe_serve_chat_from_plane ─────────────────────────────────────────────


def test_skips_non_pg_mysql_connectors(monkeypatch):
    from backend.agents.data_agent.tools import _maybe_serve_chat_from_plane
    result = _maybe_serve_chat_from_plane(_conn(db_type="csv"), "SELECT 1", db=MagicMock())
    assert result is None


def test_serves_when_all_tables_on_plane(monkeypatch):
    """Plane has Parquet for every referenced table → returns plane.query result."""
    fake_plane = MagicMock()
    fake_plane.table_exists = MagicMock(return_value=True)
    fake_plane.query = MagicMock(return_value=_qr(["n"], [(42,)]))
    fake_scope = SimpleNamespace(kind="user", id="u1")

    sql_refs = _types.ModuleType("backend.utils.sql_refs")
    sql_refs.extract_table_refs = MagicMock(return_value=["orders"])
    sql_refs.transpile_to_engine = MagicMock(side_effect=lambda sql, **kw: sql + " /*duck*/")
    monkeypatch.setitem(sys.modules, "backend.utils.sql_refs", sql_refs)

    dps = _types.ModuleType("backend.services.data_plane_service")
    dps.get_plane_for_connection = MagicMock(return_value=(fake_plane, fake_scope))
    monkeypatch.setitem(sys.modules, "backend.services.data_plane_service", dps)

    from backend.agents.data_agent.tools import _maybe_serve_chat_from_plane
    out = _maybe_serve_chat_from_plane(_conn("postgres"), "SELECT count(*) FROM orders", db=MagicMock())
    assert out is not None
    assert out.rows == [(42,)]
    # Transpile to DuckDB happened.
    called_sql = fake_plane.query.call_args[0][1]
    assert called_sql.endswith("/*duck*/")


def test_falls_back_when_table_missing_on_plane(monkeypatch):
    fake_plane = MagicMock()
    fake_plane.table_exists = MagicMock(return_value=False)
    fake_plane.query = MagicMock()
    fake_scope = SimpleNamespace(kind="user", id="u1")

    sql_refs = _types.ModuleType("backend.utils.sql_refs")
    sql_refs.extract_table_refs = MagicMock(return_value=["orders"])
    sql_refs.transpile_to_engine = MagicMock(side_effect=lambda sql, **kw: sql)
    monkeypatch.setitem(sys.modules, "backend.utils.sql_refs", sql_refs)

    dps = _types.ModuleType("backend.services.data_plane_service")
    dps.get_plane_for_connection = MagicMock(return_value=(fake_plane, fake_scope))
    monkeypatch.setitem(sys.modules, "backend.services.data_plane_service", dps)

    from backend.agents.data_agent.tools import _maybe_serve_chat_from_plane
    out = _maybe_serve_chat_from_plane(_conn("postgres"), "SELECT * FROM orders", db=MagicMock())
    assert out is None
    fake_plane.query.assert_not_called()


def test_returns_none_when_no_table_refs(monkeypatch):
    sql_refs = _types.ModuleType("backend.utils.sql_refs")
    sql_refs.extract_table_refs = MagicMock(return_value=[])
    sql_refs.transpile_to_engine = MagicMock()
    monkeypatch.setitem(sys.modules, "backend.utils.sql_refs", sql_refs)
    from backend.agents.data_agent.tools import _maybe_serve_chat_from_plane
    assert _maybe_serve_chat_from_plane(_conn("postgres"), "SELECT 1", db=MagicMock()) is None


def test_returns_none_on_plane_lookup_failure(monkeypatch):
    sql_refs = _types.ModuleType("backend.utils.sql_refs")
    sql_refs.extract_table_refs = MagicMock(return_value=["orders"])
    sql_refs.transpile_to_engine = MagicMock(side_effect=lambda sql, **kw: sql)
    monkeypatch.setitem(sys.modules, "backend.utils.sql_refs", sql_refs)

    dps = _types.ModuleType("backend.services.data_plane_service")
    dps.get_plane_for_connection = MagicMock(side_effect=RuntimeError("plane missing"))
    monkeypatch.setitem(sys.modules, "backend.services.data_plane_service", dps)

    from backend.agents.data_agent.tools import _maybe_serve_chat_from_plane
    assert _maybe_serve_chat_from_plane(_conn("postgres"), "SELECT * FROM orders", db=MagicMock()) is None
