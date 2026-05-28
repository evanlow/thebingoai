"""Unit tests for MySQL T-1 snapshot scheduling.

Covers:
  - SqlExtractionConfig new fields + the dlt query_adapter T-1 filter.
  - _detect_snapshot_date_column heuristic.
  - _apply_mysql_t1_schedule: cron + next_run_at + mode=full + snapshot config,
    MySQL-gated.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock

import backend.connectors.sql_dlt as sql_dlt
import backend.services.template_materializer as tm
from backend.connectors.sql_dlt import SqlExtractionConfig, sql_dlt_source


# ── SqlExtractionConfig + dlt query adapter ──────────────────────────────────

def test_extraction_config_defaults():
    cfg = SqlExtractionConfig(tables=["orders"])
    assert cfg.snapshot_date_column is None
    assert cfg.snapshot_lag_days == 1


def _conn():
    return SimpleNamespace(username="u", password="p", host="h", port=3306, database="shop")


def test_sql_dlt_source_no_filter_without_date_col(monkeypatch):
    captured = {}
    import dlt.sources.sql_database as m
    monkeypatch.setattr(m, "sql_database", lambda **kw: captured.update(kw) or "SRC")
    sql_dlt_source("mysql+pymysql", _conn(), {"tables": ["orders"]})
    assert "query_adapter_callback" not in captured  # no T-1 filter


def test_sql_dlt_source_attaches_t1_filter(monkeypatch):
    captured = {}
    import dlt.sources.sql_database as m
    monkeypatch.setattr(m, "sql_database", lambda **kw: captured.update(kw) or "SRC")

    sql_dlt_source(
        "mysql+pymysql", _conn(),
        {"tables": ["orders"], "snapshot_date_column": "created_at", "snapshot_lag_days": 1},
    )
    cb = captured.get("query_adapter_callback")
    assert callable(cb)

    # Fake SQLAlchemy column: supports `< cutoff` like a real Column does.
    class _Col:
        def __lt__(self, other):
            return ("LT", other)

    # Callback must add a WHERE on the date column when present...
    query = MagicMock()
    table = SimpleNamespace(columns={"created_at": _Col(), "id": _Col()})
    cb(query, table)
    assert query.where.called

    # ...and be a no-op when the column is absent from the reflected table.
    query2 = MagicMock()
    table2 = SimpleNamespace(columns={"id": _Col()})
    out = cb(query2, table2)
    assert not query2.where.called
    assert out is query2


# ── _detect_snapshot_date_column ─────────────────────────────────────────────

def test_detect_prefers_conventional_name():
    cols = [
        {"name": "ship_ts", "type": "timestamp"},
        {"name": "created_at", "type": "datetime"},
        {"name": "id", "type": "int"},
    ]
    assert tm._detect_snapshot_date_column(cols) == "created_at"


def test_detect_falls_back_to_first_date_typed():
    cols = [{"name": "id", "type": "int"}, {"name": "ship_ts", "type": "timestamp"}]
    assert tm._detect_snapshot_date_column(cols) == "ship_ts"


def test_detect_none_when_no_date_column():
    cols = [{"name": "id", "type": "int"}, {"name": "label", "type": "varchar"}]
    assert tm._detect_snapshot_date_column(cols) is None


# ── _apply_mysql_t1_schedule ─────────────────────────────────────────────────

def _pipe(tables):
    return SimpleNamespace(
        id="p1", extraction_config={"tables": tables}, mode="incremental",
        cron=None, next_run_at=None, timezone="UTC",
    )


def _fake_connector(columns):
    return SimpleNamespace(
        get_table_schema=lambda table, schema=None: SimpleNamespace(columns=columns),
        close=lambda: None,
    )


def test_apply_sets_cron_nextrun_mode_and_snapshot(monkeypatch):
    cols = [{"name": "created_at", "type": "datetime"}, {"name": "id", "type": "int"}]
    monkeypatch.setattr(
        "backend.connectors.factory.get_connector_for_connection",
        lambda conn: _fake_connector(cols),
    )
    p = _pipe(["orders"])
    conn = SimpleNamespace(db_type="mysql", id=23)
    tm._apply_mysql_t1_schedule([p], conn, MagicMock())

    assert p.cron == "0 2 * * *"
    assert p.mode == "full"
    assert p.next_run_at is not None
    assert p.extraction_config["snapshot_date_column"] == "created_at"
    assert p.extraction_config["snapshot_lag_days"] == 1
    assert p.extraction_config["tables"] == ["orders"]  # preserved


def test_apply_no_date_col_still_schedules_full_snapshot(monkeypatch):
    cols = [{"name": "id", "type": "int"}, {"name": "label", "type": "varchar"}]
    monkeypatch.setattr(
        "backend.connectors.factory.get_connector_for_connection",
        lambda conn: _fake_connector(cols),
    )
    p = _pipe(["lookup"])
    tm._apply_mysql_t1_schedule([p], SimpleNamespace(db_type="mysql", id=1), MagicMock())
    assert p.cron == "0 2 * * *"
    assert p.mode == "full"
    assert p.extraction_config["snapshot_date_column"] is None  # full snapshot, no filter


def test_apply_noop_for_non_mysql(monkeypatch):
    called = {"opened": False}

    def _boom(conn):
        called["opened"] = True
        return _fake_connector([])

    monkeypatch.setattr("backend.connectors.factory.get_connector_for_connection", _boom)
    p = _pipe(["orders"])
    tm._apply_mysql_t1_schedule([p], SimpleNamespace(db_type="postgres", id=1), MagicMock())
    assert p.cron is None and p.mode == "incremental"
    assert called["opened"] is False  # never even opened a connector
