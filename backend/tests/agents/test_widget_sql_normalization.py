"""Widget SQL is normalized to the surface it actually runs on, and persisted.

Generation-time execution and the dashboard *serve* path (`api/widget_data`) are
separate code paths — the serve path only ever sees `dataSource["sql"]`. So the
normalized SQL has to be written back, or a widget repaired at build time
re-fails on every dashboard load.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock

import asyncio
import pytest

from backend.agents import dashboard_tools as dt


class FakeResult:
    def __init__(self):
        self.columns = ["a"]
        self.rows = [(1,)]
        self.row_count = 1
        self.truncated = False


def _conn(**kw):
    defaults = dict(id=104, db_type="postgresql", org_id=None)
    defaults.update(kw)
    return SimpleNamespace(**defaults)


def _widget(sql):
    return {
        "id": "pivot_table_14",
        "widget": {"type": "pivot_table", "config": {"title": "Attrition"}},
        "dataSource": {"connectionId": 104, "sql": sql, "mapping": {"type": "table"}},
    }


# ── _widget_sql_dialect ──────────────────────────────────────────────────────

def test_plane_backed_connector_follows_the_plane_under_lockdown(monkeypatch):
    from backend.config import settings
    monkeypatch.setattr(settings, "disable_local_data_plane", True, raising=False)
    connector = SimpleNamespace(serves_from_plane=True)
    assert dt._widget_sql_dialect(_conn(db_type="dataset"), connector) == "bigquery"


def test_plane_backed_connector_is_duckdb_in_dev(monkeypatch):
    from backend.config import settings
    monkeypatch.setattr(settings, "disable_local_data_plane", False, raising=False)
    connector = SimpleNamespace(serves_from_plane=True)
    assert dt._widget_sql_dialect(_conn(db_type="dataset"), connector) == "duckdb"


def test_bigquery_ga4_follows_the_plane(monkeypatch):
    from backend.config import settings
    monkeypatch.setattr(settings, "disable_local_data_plane", True, raising=False)
    assert dt._widget_sql_dialect(_conn(db_type="bigquery_ga4"), object()) == "bigquery"


def test_source_db_uses_its_own_dialect():
    assert dt._widget_sql_dialect(_conn(db_type="postgresql"), object()) == "postgres"
    assert dt._widget_sql_dialect(_conn(db_type="mysql"), object()) == "mysql"


def test_duckdb_widget_serving_wins_for_source_connections(monkeypatch):
    monkeypatch.setattr(
        "backend.config.feature_flags.enabled",
        lambda org, flag: flag == "duckdb_widget_serving",
    )
    conn = _conn(db_type="postgresql", org_id="org-1")
    assert dt._widget_sql_dialect(conn, object()) == "duckdb"


def test_unknown_db_type_disables_normalization():
    assert dt._widget_sql_dialect(_conn(db_type="weird_thing"), object()) == ""


# ── _mark_widget_failed ──────────────────────────────────────────────────────

def test_mark_widget_failed_records_the_error():
    w = _widget("SELECT 1")
    dt._mark_widget_failed(w, "boom")
    assert w["widget"]["config"]["error"] == "Query failed: boom"


def test_mark_widget_failed_truncates():
    w = _widget("SELECT 1")
    dt._mark_widget_failed(w, "x" * 900)
    assert len(w["widget"]["config"]["error"]) == 500


# ── _execute_widget_sql ──────────────────────────────────────────────────────

def _patch_execute(monkeypatch, connection, run_side_effect):
    """Wire _execute_widget_sql's collaborators; returns the list of SQL run."""
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = connection
    monkeypatch.setattr(dt, "get_connector_for_connection",
                        lambda c: SimpleNamespace(serves_from_plane=True, close=lambda: None))
    monkeypatch.setattr("backend.services.widget_transform.transform_widget_data",
                        lambda result, mapping: {"rows": list(result.rows)})
    monkeypatch.setattr("backend.services.llm_privacy.metadata_only_for_connection",
                        lambda c: True)  # skip sampling

    seen = []

    def _run(conn, sql, factory, connector):
        seen.append(sql)
        return run_side_effect(sql)

    monkeypatch.setattr(dt, "_run_widget_query", _run)
    return db, seen


def test_normalized_sql_is_persisted_back_to_the_widget(monkeypatch):
    from backend.config import settings
    monkeypatch.setattr(settings, "disable_local_data_plane", True, raising=False)
    broken = 'SELECT c."role" AS role, c."left" AS left FROM csv_104 c'
    db, seen = _patch_execute(monkeypatch, _conn(db_type="dataset"), lambda sql: FakeResult())

    w = _widget(broken)
    err = asyncio.run(dt._execute_widget_sql(w, lambda: db))

    assert err is None
    assert "`role`" in seen[0]          # ran against BigQuery-quoted SQL
    assert w["dataSource"]["sql"] == seen[0]   # …and the fix was persisted
    assert w["widget"]["config"]["rows"] == [(1,)]


def test_clean_sql_is_not_rewritten(monkeypatch):
    from backend.config import settings
    monkeypatch.setattr(settings, "disable_local_data_plane", False, raising=False)
    clean = "SELECT department, COUNT(*) AS cnt FROM csv_104 GROUP BY department"
    db, seen = _patch_execute(monkeypatch, _conn(db_type="dataset"), lambda sql: FakeResult())

    w = _widget(clean)
    asyncio.run(dt._execute_widget_sql(w, lambda: db))

    assert seen == [clean]
    assert w["dataSource"]["sql"] == clean


def test_unrecoverable_failure_surfaces_an_error_on_the_widget(monkeypatch):
    from backend.config import settings
    monkeypatch.setattr(settings, "disable_local_data_plane", False, raising=False)
    db, seen = _patch_execute(
        monkeypatch, _conn(db_type="dataset"),
        lambda sql: (_ for _ in ()).throw(RuntimeError("no such column: left")),
    )
    monkeypatch.setattr(dt, "_attempt_sql_fix", _async_none)

    w = _widget("SELECT bad FROM csv_104")
    err = asyncio.run(dt._execute_widget_sql(w, lambda: db))

    assert err and "no such column" in err
    assert "Query failed" in w["widget"]["config"]["error"]


async def _async_none(**kwargs):
    return None
