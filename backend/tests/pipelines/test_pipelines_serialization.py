"""Tests for `api.PipelineResponse` / `ScheduleResponse` serialization of a
new-model pipeline with multiple `PipelineSchedule` rows. Pure Pydantic
(`from_attributes=True`) — no DB, no FastAPI.
"""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from backend.pipelines.api import PipelineResponse, ScheduleResponse


def _schedule(sid, cron, tz="UTC", enabled=True, tables=None):
    return SimpleNamespace(
        id=sid, name=f"sched-{sid}", cron=cron, timezone=tz, enabled=enabled,
        next_run_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        tables=tables if tables is not None else [{"source_table": "orders"}],
    )


def _pipeline(schedules):
    return SimpleNamespace(
        id="p1", name="demo", source_connection_id=1,
        owner_scope_kind="user", owner_scope_id="u1",
        target_table=None, cron=None, timezone="UTC", mode="full",
        incremental_key=None, unique_key=None, extraction_config={},
        pipeline_fingerprint="f" * 64, last_run_at=None, last_run_status=None,
        next_run_at=None, enabled=True, created_by_user_id="u1",
        created_at=None, updated_at=None, schedules=schedules,
    )


def test_multiple_schedules_serialize_in_order():
    p = _pipeline([_schedule("s1", "0 2 * * *"), _schedule("s2", "0 6 * * *")])
    out = PipelineResponse.model_validate(p)
    assert [s.id for s in out.schedules] == ["s1", "s2"]
    assert isinstance(out.schedules[0], ScheduleResponse)


def test_schedule_fields_map_through():
    p = _pipeline([_schedule("s1", "0 2 * * *", tz="America/New_York",
                             enabled=False, tables=[{"source_table": "x"}])])
    s = PipelineResponse.model_validate(p).schedules[0]
    assert s.cron == "0 2 * * *"
    assert s.timezone == "America/New_York"
    assert s.enabled is False
    assert s.next_run_at == datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert s.tables == [{"source_table": "x"}]


def test_no_schedules_yields_empty_list():
    out = PipelineResponse.model_validate(_pipeline([]))
    assert out.schedules == []
