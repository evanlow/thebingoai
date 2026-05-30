"""Tests for the dlt incremental-cursor wiring in `connectors.sql_dlt`.

`sql_dlt_source` applies a per-table `dlt.sources.incremental` hint when
`extraction_config.incremental_key` is set, threading `initial_value` (first-run
lower bound) and an `end_value` computed from `cutoff_days` (T-N upper bound).
Also guards the no-cursor (full-snapshot) path against regressions.
"""
from __future__ import annotations

import sys
import types as _types
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest


# ── Stub dlt + sql_database before importing sql_dlt. dlt isn't installed in
#    every dev env (it ships in the backend image only).
@pytest.fixture(autouse=True)
def _stub_dlt(monkeypatch):
    dlt = _types.ModuleType("dlt")
    sources_mod = _types.ModuleType("dlt.sources")
    sql_db_mod = _types.ModuleType("dlt.sources.sql_database")

    class _FakeIncremental:
        def __init__(self, cursor_path, initial_value=None, **kwargs):
            self.cursor_path = cursor_path
            self.initial_value = initial_value
            self.kwargs = kwargs

    sources_mod.incremental = _FakeIncremental
    dlt.sources = sources_mod

    captured_hints: dict[str, dict] = {}

    class _FakeResource:
        def __init__(self, name):
            self.name = name

        def apply_hints(self, **hints):
            captured_hints[self.name] = hints

    class _FakeSource:
        def __init__(self, table_names):
            self.resources = {n: _FakeResource(n) for n in table_names}

    def _fake_sql_database(**kwargs):
        return _FakeSource(kwargs.get("table_names") or ["events"])

    sql_db_mod.sql_database = _fake_sql_database

    monkeypatch.setitem(sys.modules, "dlt", dlt)
    monkeypatch.setitem(sys.modules, "dlt.sources", sources_mod)
    monkeypatch.setitem(sys.modules, "dlt.sources.sql_database", sql_db_mod)

    # Force a fresh import of sql_dlt so it binds against our stubs.
    sys.modules.pop("backend.connectors.sql_dlt", None)
    yield captured_hints
    sys.modules.pop("backend.connectors.sql_dlt", None)


def _conn():
    return SimpleNamespace(
        username="u", password="p", host="h", port=5432, database="d",
    )


_SENTINEL = datetime(1900, 1, 1, tzinfo=timezone.utc)


def _start_of_today_utc():
    return datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)


def test_no_incremental_key_does_not_apply_hints(_stub_dlt):
    from backend.connectors.sql_dlt import sql_dlt_source
    src = sql_dlt_source("postgresql", _conn(), {"tables": ["events"]})
    assert src is not None
    assert _stub_dlt == {}  # apply_hints never called


def test_incremental_key_applies_cursor_hint(_stub_dlt):
    from backend.connectors.sql_dlt import sql_dlt_source
    sql_dlt_source(
        "postgresql", _conn(),
        {"tables": ["events"], "incremental_key": "updated_at"},
    )
    assert "events" in _stub_dlt
    inc = _stub_dlt["events"]["incremental"]
    assert inc.cursor_path == "updated_at"
    # No `initial_value` supplied → unbounded-lower sentinel.
    assert inc.initial_value == _SENTINEL


def test_initial_value_threads_into_cursor(_stub_dlt):
    from backend.connectors.sql_dlt import sql_dlt_source
    sql_dlt_source(
        "postgresql", _conn(),
        {
            "tables": ["events"],
            "incremental_key": "updated_at",
            "initial_value": "2026-05-01T00:00:00+00:00",
        },
    )
    inc = _stub_dlt["events"]["incremental"]
    assert inc.initial_value == datetime(2026, 5, 1, tzinfo=timezone.utc)


def test_cutoff_days_default_is_t1(_stub_dlt):
    """Default cutoff (1 = T-1) caps `end_value` at the start of today UTC."""
    from backend.connectors.sql_dlt import sql_dlt_source
    sql_dlt_source(
        "postgresql", _conn(),
        {"tables": ["events"], "incremental_key": "updated_at"},
    )
    inc = _stub_dlt["events"]["incremental"]
    assert inc.kwargs.get("end_value") == _start_of_today_utc()


def test_cutoff_days_two_shifts_back_one_day(_stub_dlt):
    """cutoff_days=2 (T-2) caps `end_value` one whole day earlier."""
    from backend.connectors.sql_dlt import sql_dlt_source
    sql_dlt_source(
        "postgresql", _conn(),
        {"tables": ["events"], "incremental_key": "updated_at", "cutoff_days": 2},
    )
    inc = _stub_dlt["events"]["incremental"]
    assert inc.kwargs.get("end_value") == _start_of_today_utc() - timedelta(days=1)


def test_incremental_key_applies_to_all_listed_tables(_stub_dlt):
    from backend.connectors.sql_dlt import sql_dlt_source
    sql_dlt_source(
        "postgresql", _conn(),
        {"tables": ["orders", "events"], "incremental_key": "updated_at"},
    )
    assert set(_stub_dlt) == {"orders", "events"}
    assert _stub_dlt["orders"]["incremental"].cursor_path == "updated_at"
    assert _stub_dlt["events"]["incremental"].cursor_path == "updated_at"
