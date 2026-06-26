"""Tests for `schedule_ops.update_schedule` — partial update of a new-model
`PipelineSchedule` row (cron/timezone validation, next_run recompute, table-spec
rebuild). Uses SimpleNamespace stubs + MagicMock db (no real DB), mirroring
`tests/api/test_pipelines_api_overrides.py`.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from backend.pipelines.schedule_ops import update_schedule


def _schedule(**over):
    base = dict(timezone="UTC", cron=None, enabled=False, tables=[], next_run_at=None)
    base.update(over)
    return SimpleNamespace(**base)


def _pipeline(**over):
    base = dict(id="p1", source_connection_id=1)
    base.update(over)
    return SimpleNamespace(**base)


def test_enabled_with_cron_sets_next_run():
    s = _schedule(cron="0 2 * * *", enabled=True)
    out = update_schedule(_pipeline(), s, MagicMock())
    assert out is s
    assert s.next_run_at is not None


def test_disabled_clears_next_run_even_with_cron():
    s = _schedule(cron="0 2 * * *", enabled=False, next_run_at="stale")
    update_schedule(_pipeline(), s, MagicMock(), enabled=False)
    assert s.next_run_at is None


def test_invalid_timezone_raises():
    s = _schedule()
    with pytest.raises(ValueError, match="Unknown IANA timezone"):
        update_schedule(_pipeline(), s, MagicMock(), timezone="Mars/Phobos")


def test_invalid_cron_while_enabled_raises():
    s = _schedule(enabled=True)
    with pytest.raises(ValueError, match="Invalid cron expression"):
        update_schedule(_pipeline(), s, MagicMock(), cron="not a cron")


def test_tables_omitted_does_not_rebuild_specs():
    """No `tables` kwarg → `_rebuild_specs` not called → db never queried."""
    s = _schedule(tables=[{"source_table": "orders"}])
    db = MagicMock()
    update_schedule(_pipeline(), s, db, cron=None)
    db.query.assert_not_called()
    assert s.tables == [{"source_table": "orders"}]


def test_tables_provided_rebuilds_specs():
    s = _schedule()
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
        id=1, db_type="postgres"
    )
    rebuilt = [{"source_table": "orders", "target_table": "pg__orders"}]
    with patch("backend.connectors.factory.get_connector_registration",
               return_value=SimpleNamespace(type_id="postgres")), \
         patch("backend.services.template_materializer.build_specs_for_tables",
               return_value=rebuilt) as build:
        update_schedule(_pipeline(), s, db, tables=["orders"])
    build.assert_called_once()
    assert s.tables == rebuilt


def test_tables_rebuild_raises_when_connection_missing():
    s = _schedule()
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    with pytest.raises(ValueError, match="Source connection not found"):
        update_schedule(_pipeline(), s, db, tables=["orders"])
