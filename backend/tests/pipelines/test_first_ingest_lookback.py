"""Tests for `first_ingest_task`'s backfill lookback logic — the
`first_ingest_lookback_days` → `backfill_since` conversion and how it is
threaded into `run_pipeline`. Uses SimpleNamespace stubs + MagicMock db (no
real DB), mirroring `tests/pipelines/test_schedule_ops.py`.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from backend.pipelines.tasks import first_ingest_task


def _pipeline(**over):
    base = dict(id="p1", first_ingest_done=False, schedules=[])
    base.update(over)
    return SimpleNamespace(**base)


def _run(pipelines, lookback_days):
    """Invoke the task with a stubbed db + settings; return the run_pipeline mock."""
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = pipelines
    with patch("backend.database.session.SessionLocal", return_value=db), \
         patch("backend.config.settings.first_ingest_lookback_days", lookback_days, create=True), \
         patch("backend.pipelines.runner.run_pipeline") as run_pipeline:
        first_ingest_task(connection_id=1, triggered_by_user_id="u1")
    return run_pipeline


def _since_of(run_pipeline):
    return run_pipeline.call_args.kwargs["backfill_since"]


def test_positive_lookback_sets_since_n_days_back():
    run_pipeline = _run([_pipeline()], 7)
    since = datetime.fromisoformat(_since_of(run_pipeline))
    expected = datetime.now(timezone.utc) - timedelta(days=7)
    assert abs((since - expected).total_seconds()) < 60


@pytest.mark.parametrize("lookback", [0, -1])
def test_non_positive_lookback_means_no_lower_bound(lookback):
    """N <= 0 → `None`, i.e. dlt's sentinel for "load all history"."""
    assert _since_of(_run([_pipeline()], lookback)) is None


def test_since_is_passed_to_every_schedule():
    """New model: one run_pipeline per schedule, all sharing one backfill_since."""
    p = _pipeline(schedules=[SimpleNamespace(id="s1"), SimpleNamespace(id="s2")])
    run_pipeline = _run([p], 3)
    assert run_pipeline.call_count == 2
    sinces = {c.kwargs["backfill_since"] for c in run_pipeline.call_args_list}
    assert len(sinces) == 1 and sinces.pop() is not None
    assert [c.kwargs["schedule_id"] for c in run_pipeline.call_args_list] == ["s1", "s2"]


def test_already_ingested_pipelines_are_skipped():
    run_pipeline = _run([_pipeline(first_ingest_done=True)], 7)
    run_pipeline.assert_not_called()
