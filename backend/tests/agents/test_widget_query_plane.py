"""Generation-time widget SQL must read the DataPlane, not the live source.

Once an Org has `duckdb_widget_serving` on, the dashboard agent emits DuckDB SQL
(`profile_defaults._dialect_hints_for_target`). Handing that to a Postgres/MySQL
connector fails on DuckDB-only constructs, so `_run_widget_query` routes it
through the plane instead — falling back to the source on any miss.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from backend.agents import dashboard_tools as dt


@pytest.fixture
def conn():
    return SimpleNamespace(id=7, db_type="postgres", org_id="org-1", name="pg")


@pytest.fixture
def connector():
    c = MagicMock()
    c.execute_query.return_value = "SOURCE"
    return c


def _patch(monkeypatch, *, flag=True, table_map=None, reader=None, plane=None):
    """Stub the plane lookups `_run_widget_query_on_plane` imports lazily."""
    import backend.config.feature_flags as ff
    import backend.services.data_plane_service as dps

    monkeypatch.setattr(ff, "enabled", lambda org_id, flag_name, default=False: flag)
    monkeypatch.setattr(
        dps, "plane_table_map",
        lambda c, db: {"orders": "pg__orders"} if table_map is None else table_map,
    )
    monkeypatch.setattr(
        dps, "get_plane_for_connection",
        lambda c: (plane if plane is not None else MagicMock(), SimpleNamespace(kind="user", id="u1")),
    )
    monkeypatch.setattr(dps, "get_gcs_duckdb_reader", lambda scope, db: reader)


def test_reads_plane_and_rewrites_table_refs(monkeypatch, conn, connector):
    reader = MagicMock()
    reader.query.return_value = "PLANE"
    _patch(monkeypatch, reader=reader)

    assert dt._run_widget_query(conn, "SELECT * FROM orders", MagicMock(), connector) == "PLANE"
    connector.execute_query.assert_not_called()

    # Source ref rewritten to the pipeline's plane target before the read.
    sql = reader.query.call_args[0][1]
    assert "pg__orders" in sql and "FROM orders" not in sql


def test_flag_off_uses_source(monkeypatch, conn, connector):
    _patch(monkeypatch, flag=False)
    assert dt._run_widget_query(conn, "SELECT 1 FROM orders", MagicMock(), connector) == "SOURCE"


def test_empty_table_map_uses_source(monkeypatch, conn, connector):
    # No pipelines for this connection → nothing materialized yet.
    _patch(monkeypatch, table_map={})
    assert dt._run_widget_query(conn, "SELECT 1 FROM orders", MagicMock(), connector) == "SOURCE"


def test_no_reader_uses_source(monkeypatch, conn, connector):
    # Residency-locked / customer-managed / no-HMAC plane → reader is None.
    _patch(monkeypatch, reader=None)
    assert dt._run_widget_query(conn, "SELECT 1 FROM orders", MagicMock(), connector) == "SOURCE"


def test_plane_error_falls_back_to_source(monkeypatch, conn, connector):
    reader = MagicMock()
    reader.query.side_effect = RuntimeError("no such file")
    _patch(monkeypatch, reader=reader)

    assert dt._run_widget_query(conn, "SELECT 1 FROM orders", MagicMock(), connector) == "SOURCE"
    reader.close.assert_called_once()  # reader owned here — must not leak


def test_local_plane_served_without_reader(monkeypatch, conn, connector):
    from backend.data_plane.local_filesystem import LocalFilesystemDataPlane

    plane = MagicMock(spec=LocalFilesystemDataPlane)
    plane.query.return_value = "LOCAL"
    _patch(monkeypatch, plane=plane, reader=None)

    assert dt._run_widget_query(conn, "SELECT 1 FROM orders", MagicMock(), connector) == "LOCAL"
    connector.execute_query.assert_not_called()


def test_connection_without_org_uses_source(monkeypatch, connector):
    _patch(monkeypatch)
    c = SimpleNamespace(id=7, db_type="postgres", org_id=None)
    assert dt._run_widget_query(c, "SELECT 1 FROM orders", MagicMock(), connector) == "SOURCE"
