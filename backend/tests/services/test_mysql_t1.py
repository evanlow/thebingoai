"""Unit tests for MySQL auto-scheduled incremental/full pipelines.

Covers:
  - SqlExtractionConfig new fields + the dlt incremental cursor wiring.
  - _detect_snapshot_date_column heuristic.
  - _apply_mysql_t1_schedule: incremental (with cursor) when a date col is
    detected, else full snapshot. Always sets cron + next_run_at.
"""
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import backend.connectors.sql_dlt as sql_dlt
import backend.services.template_materializer as tm
from backend.connectors.sql_dlt import SqlExtractionConfig, sql_dlt_source


# ── SqlExtractionConfig + dlt incremental wiring ─────────────────────────────

def test_extraction_config_defaults():
    cfg = SqlExtractionConfig(tables=["orders"])
    assert cfg.incremental_key is None
    assert cfg.initial_value is None


def _conn():
    return SimpleNamespace(username="u", password="p", host="h", port=3306, database="shop")


def _capture_source(monkeypatch, fake_src):
    captured = {}
    import dlt.sources.sql_database as m
    monkeypatch.setattr(m, "sql_database", lambda **kw: captured.update(kw) or fake_src)
    return captured


def test_sql_dlt_source_no_incremental_passthrough(monkeypatch):
    fake_resource = MagicMock()
    fake_src = SimpleNamespace(resources={"orders": fake_resource})
    _capture_source(monkeypatch, fake_src)
    sql_dlt_source("mysql+pymysql", _conn(), {"tables": ["orders"]})
    fake_resource.apply_hints.assert_not_called()


def test_sql_dlt_source_applies_incremental_cursor(monkeypatch):
    fake_resource = MagicMock()
    fake_src = SimpleNamespace(resources={"orders": fake_resource})
    _capture_source(monkeypatch, fake_src)

    sql_dlt_source(
        "mysql+pymysql", _conn(),
        {"tables": ["orders"], "incremental_key": "created_at",
         "initial_value": "2026-05-27T00:00:00+00:00"},
    )

    fake_resource.apply_hints.assert_called_once()
    kw = fake_resource.apply_hints.call_args.kwargs
    assert "incremental" in kw  # dlt.sources.incremental(...) instance


def test_sql_dlt_source_skips_unknown_table(monkeypatch):
    """Resource missing for the configured table → no apply_hints, no crash."""
    fake_src = SimpleNamespace(resources={})
    _capture_source(monkeypatch, fake_src)
    # Should not raise even though "orders" has no resource on the fake source.
    sql_dlt_source(
        "mysql+pymysql", _conn(),
        {"tables": ["orders"], "incremental_key": "created_at"},
    )


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

def _pipe(tables, mode_initial="full"):
    return SimpleNamespace(
        id="p1", extraction_config={"tables": tables}, mode=mode_initial,
        cron=None, next_run_at=None, timezone="UTC", incremental_key=None,
    )


def _fake_connector(columns):
    return SimpleNamespace(
        get_table_schema=lambda table, schema=None: SimpleNamespace(columns=columns),
        close=lambda: None,
    )


def test_apply_incremental_when_date_col_detected(monkeypatch):
    cols = [{"name": "created_at", "type": "datetime"}, {"name": "id", "type": "int"}]
    monkeypatch.setattr(
        "backend.connectors.factory.get_connector_for_connection",
        lambda conn: _fake_connector(cols),
    )
    p = _pipe(["orders"])
    tm._apply_mysql_t1_schedule([p], SimpleNamespace(db_type="mysql", id=23), MagicMock())

    assert p.mode == "incremental"
    assert p.incremental_key == "created_at"
    assert p.cron == "0 2 * * *"
    assert p.next_run_at is not None
    assert p.extraction_config["tables"] == ["orders"]
    assert p.extraction_config["incremental_key"] == "created_at"
    # initial_value must be a valid ISO datetime string.
    iv = p.extraction_config["initial_value"]
    assert isinstance(iv, str)
    parsed = datetime.fromisoformat(iv)
    assert parsed.tzinfo is not None and parsed.tzinfo.utcoffset(parsed) == timezone.utc.utcoffset(parsed)


def test_apply_full_snapshot_when_no_date_col(monkeypatch):
    cols = [{"name": "id", "type": "int"}, {"name": "label", "type": "varchar"}]
    monkeypatch.setattr(
        "backend.connectors.factory.get_connector_for_connection",
        lambda conn: _fake_connector(cols),
    )
    p = _pipe(["lookup"], mode_initial="incremental")  # start as incremental to verify override
    tm._apply_mysql_t1_schedule([p], SimpleNamespace(db_type="mysql", id=1), MagicMock())

    assert p.mode == "full"
    assert p.cron == "0 2 * * *"
    assert "incremental_key" not in p.extraction_config
    assert "initial_value" not in p.extraction_config


def test_apply_noop_for_non_mysql(monkeypatch):
    called = {"opened": False}

    def _boom(conn):
        called["opened"] = True
        return _fake_connector([])

    monkeypatch.setattr("backend.connectors.factory.get_connector_for_connection", _boom)
    p = _pipe(["orders"])
    tm._apply_mysql_t1_schedule([p], SimpleNamespace(db_type="postgres", id=1), MagicMock())
    assert p.cron is None
    assert p.mode == "full"  # unchanged from initial
    assert called["opened"] is False  # never even opened a connector
