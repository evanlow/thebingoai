"""Tests for the widget plane-redirect path and bootstrap fallback.

Covers:
  - _duckdb_serving_enabled (flag gate)
  - _serve_widget_via_dataplane (local-plane cold/missing → None fallback,
    GCS reader None→None fallback, unregistered connection→None)
  - refresh_widget fallback chain (plane → cache → source DB)
  - Bootstrap policy: pg/mysql widget fallback to live source when plane
    data is cold/missing.

Heavy I/O (connector open, plane query, DB session) is patched out.  The
endpoint handler is async def, so each call goes through `asyncio.run(...)`.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from backend.api import widget_data as wd


def _run(coro):
    return asyncio.run(coro)


@dataclass
class FakeQueryResult:
    columns: list[str]
    rows: list[tuple]
    row_count: int
    execution_time_ms: float = 1.0
    truncated: bool = False


# ── Helpers ──────────────────────────────────────────────────────────────────

class FakeConnection(SimpleNamespace):
    def __init__(self, **kwargs):
        defaults = dict(id=42, user_id="u-1", db_type="postgresql",
                         org_id="org-1")
        defaults.update(kwargs)
        super().__init__(**defaults)

class FakeDashboard(SimpleNamespace):
    def __init__(self):
        super().__init__(id=1, user_id="u-1", data_context={})


def _user(id_="u-1", org_id=None):
    return SimpleNamespace(id=id_, org_id=org_id)


def _db_with_first(*side):
    """Return a MagicMock db where .query().filter().first() returns `side[0]`,
    then `side[1]`, etc. Callers that need both dashboard + connection lookups
    pass two values."""
    db = MagicMock()
    first = db.query.return_value.filter.return_value.first
    if side:
        first.side_effect = list(side)
    return db


def _setup_plane_patch(monkeypatch, plane):
    """Patch get_plane_for_connection to return (plane, scope)."""
    monkeypatch.setattr(
        "backend.services.data_plane_service.get_plane_for_connection",
        lambda conn: (plane, SimpleNamespace()),
    )


def _setup_duckdb_ready(monkeypatch, ready: bool = True):
    monkeypatch.setattr(
        "backend.migration.dialect_migration.is_duckdb_ready",
        lambda dashboard_id, db: ready,
    )


def _setup_rewrite_noop(monkeypatch):
    """rewrite_table_refs / extract_table_refs live in sql_refs and are imported
    inside _serve_widget_via_dataplane — patch the source module."""
    monkeypatch.setattr(
        "backend.utils.sql_refs.rewrite_table_refs",
        lambda sql, table_map: (sql, set()),
    )
    monkeypatch.setattr(
        "backend.utils.sql_refs.extract_table_refs",
        lambda sql: {"orders"},
    )


def _noop_table_map(monkeypatch):
    monkeypatch.setattr(
        "backend.services.data_plane_service.plane_table_map",
        lambda conn, db: {},
    )


# ── _duckdb_serving_enabled ─────────────────────────────────────────────────

def test_duckdb_serving_enabled_false_when_no_org():
    assert wd._duckdb_serving_enabled(None) is False


def test_duckdb_serving_enabled_calls_feature_flags(monkeypatch):
    calls = {}

    def _enabled(org_id: str, flag: str) -> bool:
        calls["org_id"] = org_id
        calls["flag"] = flag
        return True

    monkeypatch.setattr("backend.config.feature_flags.enabled", _enabled)
    assert wd._duckdb_serving_enabled("org-1") is True
    assert calls == {"org_id": "org-1", "flag": "duckdb_widget_serving"}


# ── _build_widget_response ──────────────────────────────────────────────────

def test_build_widget_response_includes_source_rows(monkeypatch):
    def _transform(result, mapping):
        return {"value": mapping["valueColumn"], "label": "test"}
    monkeypatch.setattr(wd, "transform_widget_data", _transform)

    result = FakeQueryResult(
        columns=["total"], rows=[(15,)], row_count=1,
    )
    mapping = {"type": "kpi", "valueColumn": "total"}
    resp = wd._build_widget_response(result, mapping)

    assert resp.config == {"value": "total", "label": "test"}
    assert resp.row_count == 1
    assert resp.source_columns == ["total"]
    assert resp.source_rows == [[15]]


# ── _serve_via_dataplane — connection not found ─────────────────────────────

def test_serve_via_dataplane_none_when_connection_not_found():
    db = _db_with_first(None)
    req = wd.WidgetRefreshRequest(connection_id=42, sql="SELECT 1", mapping={})
    assert wd._serve_widget_via_dataplane(req, None, _user(), db) is None


def test_serve_via_dataplane_none_when_not_duckdb_ready(monkeypatch):
    _setup_duckdb_ready(monkeypatch, ready=False)
    db = _db_with_first(FakeConnection())
    req = wd.WidgetRefreshRequest(
        connection_id=42, sql="SELECT 1", mapping={}, dashboard_id=1,
    )
    assert wd._serve_widget_via_dataplane(req, None, _user(), db) is None


# ── Local plane — bootstrap policy (cold/missing → fallback) ───────────────

def test_serve_via_dataplane_local_plane_cold_table_returns_none(monkeypatch):
    """Bootstrap policy: when the local plane doesn't have the source table yet
    (cold/missing Parquet), return None → fall back to source DB."""
    _setup_duckdb_ready(monkeypatch)
    _setup_rewrite_noop(monkeypatch)
    _noop_table_map(monkeypatch)

    class ColdLocalPlane:
        def table_exists(self, scope, table):
            return False

    _setup_plane_patch(monkeypatch, ColdLocalPlane())
    db = _db_with_first(FakeConnection())

    req = wd.WidgetRefreshRequest(
        connection_id=42, sql="SELECT * FROM orders", mapping={}, dashboard_id=1,
    )
    assert wd._serve_widget_via_dataplane(req, None, _user(), db) is None


def test_serve_via_dataplane_local_plane_warm_table_returns_response(monkeypatch):
    """When the local plane has the table, serve via GCS reader (same data path
    as local plane in _build_widget_response — the function signature + response
    shape is identical for both plane types)."""
    monkeypatch.setattr(
        "backend.migration.dialect_migration.is_duckdb_ready",
        lambda dashboard_id, db: True,
    )
    monkeypatch.setattr(
        "backend.utils.sql_refs.rewrite_table_refs",
        lambda sql, table_map: (sql, set()),
    )
    monkeypatch.setattr(
        "backend.services.data_plane_service.plane_table_map",
        lambda conn, db: {},
    )

    result = FakeQueryResult(columns=["cnt"], rows=[(15,)], row_count=1)

    class FakeReader:
        def query(self, scope, sql):
            return result
        def close(self):
            pass

    # GCS plane (not LocalFilesystemDataPlane) → triggers reader path
    monkeypatch.setattr(
        "backend.services.data_plane_service.get_plane_for_connection",
        lambda conn: (SimpleNamespace(), SimpleNamespace()),
    )
    monkeypatch.setattr(
        "backend.services.data_plane_service.get_gcs_duckdb_reader",
        lambda scope, db: FakeReader(),
    )

    def _transform(result, mapping):
        return {"value": 15}
    monkeypatch.setattr(wd, "transform_widget_data", _transform)

    db = _db_with_first(FakeConnection())

    req = wd.WidgetRefreshRequest(
        connection_id=42, sql="SELECT COUNT(*) FROM orders", mapping={}, dashboard_id=1,
    )
    resp = wd._serve_widget_via_dataplane(req, None, _user(), db)
    assert resp is not None
    assert resp.config["value"] == 15
    assert resp.row_count == 1
    assert resp.source_columns == ["cnt"]
    assert resp.source_rows == [[15]]


def test_serve_via_dataplane_local_plane_raises_returns_none(monkeypatch):
    """Bootstrap policy: plane.query exception → None → fall back to source DB."""
    _setup_duckdb_ready(monkeypatch)
    _setup_rewrite_noop(monkeypatch)
    _noop_table_map(monkeypatch)

    class FaultyPlane:
        def table_exists(self, scope, table):
            return True
        def query(self, scope, sql, params=None):
            raise RuntimeError("disk-full")

    _setup_plane_patch(monkeypatch, FaultyPlane())
    db = _db_with_first(FakeConnection())

    req = wd.WidgetRefreshRequest(
        connection_id=42, sql="SELECT 1", mapping={}, dashboard_id=1,
    )
    assert wd._serve_widget_via_dataplane(req, None, _user(), db) is None


# ── GCS plane — reader None / reader success / reader exception ─────────────

def test_serve_via_dataplane_gcs_reader_none_returns_none(monkeypatch):
    """GCS path: reader is None (residency-locked / customer / no-HMAC)
    → None → fall back to source DB."""
    _setup_duckdb_ready(monkeypatch)
    _setup_rewrite_noop(monkeypatch)
    _noop_table_map(monkeypatch)

    class FakeGCSPlane:
        pass

    _setup_plane_patch(monkeypatch, FakeGCSPlane())
    monkeypatch.setattr(
        "backend.services.data_plane_service.get_gcs_duckdb_reader",
        lambda scope, db: None,
    )
    db = _db_with_first(FakeConnection())

    req = wd.WidgetRefreshRequest(
        connection_id=42, sql="SELECT 1", mapping={}, dashboard_id=1,
    )
    assert wd._serve_widget_via_dataplane(req, None, _user(), db) is None


def test_serve_via_dataplane_gcs_reader_success(monkeypatch):
    """GCS path with a valid reader: serve via DuckDB-over-GCS."""
    _setup_duckdb_ready(monkeypatch)
    _setup_rewrite_noop(monkeypatch)
    _noop_table_map(monkeypatch)

    result = FakeQueryResult(columns=["cnt"], rows=[(15,)], row_count=1)

    class FakeReader:
        def query(self, scope, sql):
            return result
        def close(self):
            pass

    class FakeGCSPlane:
        pass

    _setup_plane_patch(monkeypatch, FakeGCSPlane())
    monkeypatch.setattr(
        "backend.services.data_plane_service.get_gcs_duckdb_reader",
        lambda scope, db: FakeReader(),
    )

    def _transform(result, mapping):
        return {"value": 15}
    monkeypatch.setattr(wd, "transform_widget_data", _transform)

    db = _db_with_first(FakeConnection())

    req = wd.WidgetRefreshRequest(
        connection_id=42, sql="SELECT COUNT(*) FROM orders", mapping={}, dashboard_id=1,
    )
    resp = wd._serve_widget_via_dataplane(req, None, _user(), db)
    assert resp is not None
    assert resp.config["value"] == 15


def test_serve_via_dataplane_gcs_exception_returns_none(monkeypatch):
    """GCS path: query raises → None → fall back to source DB."""
    _setup_duckdb_ready(monkeypatch)
    _setup_rewrite_noop(monkeypatch)
    _noop_table_map(monkeypatch)

    class FaultyReader:
        def query(self, scope, sql):
            raise RuntimeError("GCS timeout")
        def close(self):
            pass

    class FakeGCSPlane:
        pass

    _setup_plane_patch(monkeypatch, FakeGCSPlane())
    monkeypatch.setattr(
        "backend.services.data_plane_service.get_gcs_duckdb_reader",
        lambda scope, db: FaultyReader(),
    )
    db = _db_with_first(FakeConnection())

    req = wd.WidgetRefreshRequest(
        connection_id=42, sql="SELECT 1", mapping={}, dashboard_id=1,
    )
    assert wd._serve_widget_via_dataplane(req, None, _user(), db) is None


# ── refresh_widget — fallback chain (plane → cache → source DB) ────────────

def test_refresh_widget_no_dashboard_falls_straight_to_source(monkeypatch):
    """When no dashboard_id is supplied, skip both the plane and cache paths
    and go directly to the source DB connector."""
    monkeypatch.setattr(wd, "_duckdb_serving_enabled", lambda org_id: False)

    result = FakeQueryResult(columns=["cnt"], rows=[(15,)], row_count=1)
    fake_connector = MagicMock()
    fake_connector.__enter__ = lambda self: self
    fake_connector.__exit__ = lambda *a: None
    fake_connector.execute_query.return_value = result

    monkeypatch.setattr(
        "backend.connectors.factory.get_connector_for_connection",
        lambda conn: fake_connector,
    )

    def _transform(result, mapping):
        return {"value": 15}
    monkeypatch.setattr(wd, "transform_widget_data", _transform)

    db = _db_with_first(FakeConnection())

    req = wd.WidgetRefreshRequest(
        connection_id=42, sql="SELECT COUNT(*) FROM orders", mapping={},
    )
    resp = _run(wd.refresh_widget(req, _user(), db))
    assert resp is not None
    assert resp.row_count == 1
    assert resp.source_rows == [[15]]
    fake_connector.execute_query.assert_called_once()


def test_refresh_widget_source_db_fallback_when_plane_returns_none(monkeypatch):
    """Bootstrap policy: when the plane redirect returns None (cold data),
    the endpoint falls back to live source DB query — widget still renders."""
    monkeypatch.setattr(wd, "_duckdb_serving_enabled", lambda org_id: True)
    monkeypatch.setattr(wd, "_serve_widget_via_dataplane",
                         lambda req, dash, user, db: None)
    monkeypatch.setattr(wd, "_read_widget_from_cache",
                         lambda dash_id, wid, org_id, user_id: None)

    result = FakeQueryResult(columns=["cnt"], rows=[(15,)], row_count=1)
    fake_connector = MagicMock()
    fake_connector.__enter__ = lambda self: self
    fake_connector.__exit__ = lambda *a: None
    fake_connector.execute_query.return_value = result

    monkeypatch.setattr(
        "backend.connectors.factory.get_connector_for_connection",
        lambda conn: fake_connector,
    )

    def _transform(result, mapping):
        return {"value": 15}
    monkeypatch.setattr(wd, "transform_widget_data", _transform)

    # dashboard first(), connection second ()
    db = _db_with_first(FakeDashboard(), FakeConnection())

    req = wd.WidgetRefreshRequest(
        connection_id=42, sql="SELECT COUNT(*) FROM orders", mapping={},
        dashboard_id=1, widget_id="kpi_1",
    )
    resp = _run(wd.refresh_widget(req, _user(org_id="org-1"), db))
    assert resp is not None
    assert resp.row_count == 1
    fake_connector.execute_query.assert_called_once()
    call_args = fake_connector.execute_query.call_args
    assert call_args[0][0] == "SELECT COUNT(*) FROM orders"


# ── refresh_dashboard_widgets — shared reader / connector reuse ─────────────

def _bulk_widget(wid, connection_id=42):
    return {
        "id": wid,
        "dataSource": {
            "connectionId": connection_id,
            "sql": "SELECT COUNT(*) FROM orders",
            "mapping": {"type": "kpi", "valueColumn": "total"},
        },
        "widget": {"config": {"type": "kpi"}},
    }


def test_bulk_refresh_uses_one_shared_reader_for_all_widgets(monkeypatch):
    """Core perf claim: a multi-widget dashboard builds the GCS reader ONCE
    (not once per widget), serves every widget through it, and closes it once."""
    monkeypatch.setattr(wd, "_duckdb_serving_enabled", lambda org_id: True)
    _setup_duckdb_ready(monkeypatch)
    _setup_rewrite_noop(monkeypatch)
    _noop_table_map(monkeypatch)
    monkeypatch.setattr(
        "backend.services.data_plane_service.get_plane_for_connection",
        lambda conn: (SimpleNamespace(), SimpleNamespace()),  # non-local → prod reader branch
    )

    class _CountingReader:
        def __init__(self):
            self.query_calls = 0
            self.closed = False

        def query(self, scope, sql, params=None):
            self.query_calls += 1
            return FakeQueryResult(columns=["cnt"], rows=[(1,)], row_count=1)

        def close(self):
            self.closed = True

    reader = _CountingReader()
    factory_calls = {"n": 0}

    def _factory(scope, db):
        factory_calls["n"] += 1
        return reader

    monkeypatch.setattr(
        "backend.services.data_plane_service.get_gcs_duckdb_reader", _factory,
    )
    monkeypatch.setattr(wd, "transform_widget_data", lambda result, mapping: {"value": 1})

    dashboard = SimpleNamespace(
        id=1, user_id="u-1", data_context={},
        widgets=[_bulk_widget("w1"), _bulk_widget("w2"), _bulk_widget("w3")],
    )
    # endpoint dashboard lookup, then one connection lookup per widget inside _serve
    db = _db_with_first(dashboard, FakeConnection(), FakeConnection(), FakeConnection())

    resp = _run(wd.refresh_dashboard_widgets(1, _user(org_id="org-1"), db))

    assert factory_calls["n"] == 1          # ONE reader for the whole dashboard
    assert reader.query_calls == 3          # all three widgets served by it
    assert reader.closed is True            # closed once after the loop
    assert set(resp.widgets.keys()) == {"w1", "w2", "w3"}
    assert all("config" in resp.widgets[w] for w in ("w1", "w2", "w3"))


def test_bulk_refresh_source_fallback_reuses_one_connector(monkeypatch):
    """N+1 fix: widgets sharing a connection build one connector (not one each)
    on the source-DB fallback, and it is closed once."""
    monkeypatch.setattr(wd, "_duckdb_serving_enabled", lambda org_id: False)
    monkeypatch.setattr(
        wd, "_read_widget_from_cache",
        lambda dash_id, wid, org_id=None, user_id=None: None,  # cache miss → source
    )

    result = FakeQueryResult(columns=["cnt"], rows=[(7,)], row_count=1)
    fake_connector = MagicMock()
    fake_connector.execute_query.return_value = result

    factory_calls = {"n": 0}

    def _get_conn(conn):
        factory_calls["n"] += 1
        return fake_connector

    monkeypatch.setattr(
        "backend.connectors.factory.get_connector_for_connection", _get_conn,
    )
    monkeypatch.setattr(wd, "transform_widget_data", lambda result, mapping: {"value": 7})

    dashboard = SimpleNamespace(
        id=1, user_id="u-1", data_context={},
        widgets=[_bulk_widget("w1"), _bulk_widget("w2")],  # same connection_id=42
    )
    # endpoint dashboard lookup, then ONE connection lookup (second widget reuses cache)
    db = _db_with_first(dashboard, FakeConnection())

    resp = _run(wd.refresh_dashboard_widgets(1, _user(org_id="org-1"), db))

    assert factory_calls["n"] == 1                       # one connector for both widgets
    assert fake_connector.execute_query.call_count == 2  # but each widget queried
    assert fake_connector.close.call_count == 1          # closed once, after the loop
    assert set(resp.widgets.keys()) == {"w1", "w2"}


# ── Bootstrap policy: pg/mysql connectors both fallback correctly ──────────

def test_source_db_fallback_works_for_mysql_connection(monkeypatch):
    """MySQL widget, plane cold → source DB fallback via the connector."""
    monkeypatch.setattr(wd, "_duckdb_serving_enabled", lambda org_id: True)
    monkeypatch.setattr(wd, "_serve_widget_via_dataplane",
                         lambda req, dash, user, db: None)
    monkeypatch.setattr(wd, "_read_widget_from_cache",
                         lambda dash_id, wid, org_id, user_id: None)

    result = FakeQueryResult(columns=["cnt"], rows=[(42,)], row_count=1)
    fake_connector = MagicMock()
    fake_connector.__enter__ = lambda self: self
    fake_connector.__exit__ = lambda *a: None
    fake_connector.execute_query.return_value = result

    monkeypatch.setattr(
        "backend.connectors.factory.get_connector_for_connection",
        lambda conn: fake_connector,
    )

    def _transform(result, mapping):
        return {"value": 42}
    monkeypatch.setattr(wd, "transform_widget_data", _transform)

    # dashboard first(), connection second ()
    mysql_conn = FakeConnection(db_type="mysql")
    db = _db_with_first(FakeDashboard(), mysql_conn)

    req = wd.WidgetRefreshRequest(
        connection_id=42, sql="SELECT COUNT(*) FROM orders", mapping={},
        dashboard_id=1, widget_id="kpi_1",
    )
    resp = _run(wd.refresh_widget(req, _user(org_id="org-1"), db))
    assert resp is not None
    assert resp.config["value"] == 42
