"""Tests for the dlt incremental-cursor wiring in `connectors.sql_dlt`.

Targets the Phase-1 fix: `sql_dlt_source` must apply a per-table
`dlt.sources.incremental` hint when `extraction_config.incremental_keys` is
set, threading `backfill_since` through as the cursor's `initial_value`. Also
guards the no-cursor (full-snapshot) path against regressions.
"""
from __future__ import annotations

import sys
import types as _types
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

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


def test_no_incremental_keys_does_not_apply_hints(_stub_dlt):
    from backend.connectors.sql_dlt import sql_dlt_source
    src = sql_dlt_source("postgresql", _conn(), {"tables": ["events"]})
    assert src is not None
    assert _stub_dlt == {}  # apply_hints never called


def test_incremental_key_applies_cursor_hint(_stub_dlt):
    from backend.connectors.sql_dlt import sql_dlt_source
    sql_dlt_source(
        "postgresql", _conn(),
        {"tables": ["events"], "incremental_keys": {"events": "updated_at"}},
    )
    assert "events" in _stub_dlt
    inc = _stub_dlt["events"]["incremental"]
    assert inc.cursor_path == "updated_at"
    assert inc.initial_value is None


def test_backfill_since_threads_into_initial_value(_stub_dlt):
    from backend.connectors.sql_dlt import sql_dlt_source
    since = datetime(2026, 5, 1, tzinfo=timezone.utc)
    sql_dlt_source(
        "postgresql", _conn(),
        {
            "tables": ["events"],
            "incremental_keys": {"events": "updated_at"},
            "backfill_since": since,
        },
    )
    inc = _stub_dlt["events"]["incremental"]
    assert inc.initial_value == since


def test_unknown_table_in_incremental_keys_is_skipped(_stub_dlt):
    """Cursor for a table dlt did not produce as a resource is silently dropped."""
    from backend.connectors.sql_dlt import sql_dlt_source
    sql_dlt_source(
        "postgresql", _conn(),
        {"tables": ["events"], "incremental_keys": {"ghost_table": "updated_at"}},
    )
    assert _stub_dlt == {}


def test_end_value_threaded_to_incremental(_stub_dlt):
    """`end_value` from extraction_config flows to dlt.sources.incremental."""
    from backend.connectors.sql_dlt import sql_dlt_source
    cutoff = datetime(2026, 5, 28, 14, 32, tzinfo=timezone.utc)
    sql_dlt_source(
        "postgresql", _conn(),
        {
            "tables": ["events"],
            "incremental_keys": {"events": "updated_at"},
            "end_value": cutoff,
        },
    )
    inc = _stub_dlt["events"]["incremental"]
    assert inc.kwargs.get("end_value") == cutoff


def test_end_value_optional_defaults_to_none(_stub_dlt):
    """Omitting `end_value` passes None to dlt (no upper bound)."""
    from backend.connectors.sql_dlt import sql_dlt_source
    sql_dlt_source(
        "postgresql", _conn(),
        {"tables": ["events"], "incremental_keys": {"events": "updated_at"}},
    )
    inc = _stub_dlt["events"]["incremental"]
    assert inc.kwargs.get("end_value") is None
