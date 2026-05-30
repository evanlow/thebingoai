"""Tests for the Phase-3 PATCH overrides + new endpoints on `pipelines/api.py`.

Covers:
  - PATCH `mode` + `incremental_key` field plumbing through PipelineUpdate.
  - Validation: incremental requires cursor; invalid mode rejected.
  - empty-string `incremental_key` clears the column.
  - POST `/redetect-watermark` re-runs the classifier and persists.
  - POST `/load-history` enqueues `run_pipeline_task` with `backfill_since_iso`.
"""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from backend.pipelines.api import (
    LoadHistoryRequest,
    PipelineUpdate,
    load_history,
    redetect_watermark,
    update_pipeline,
)


def _user(uid="u1"):
    return SimpleNamespace(id=uid, org_id=None)


def _pipeline(**over):
    base = dict(
        id="p1",
        source_connection_id=1,
        target_table="pg_demo__orders",
        cron="0 2 * * *",
        timezone="UTC",
        enabled=True,
        mode="full",
        incremental_key=None,
        extraction_config={"tables": ["orders"]},
        created_by_user_id="u1",
    )
    base.update(over)
    return SimpleNamespace(**base, refresh=MagicMock())


@pytest.fixture
def _db_with(pipeline):
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = pipeline
    db.commit = MagicMock()
    db.refresh = MagicMock()
    return db


# ── PATCH override semantics ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_patch_sets_mode_and_incremental_key(monkeypatch):
    p = _pipeline()
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = p
    body = PipelineUpdate(mode="incremental", incremental_key="updated_at")
    out = await update_pipeline("p1", body, current_user=_user(), db=db)
    assert p.mode == "incremental"
    assert p.incremental_key == "updated_at"
    assert out is p


@pytest.mark.asyncio
async def test_patch_rejects_incremental_without_cursor(monkeypatch):
    p = _pipeline()
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = p
    body = PipelineUpdate(mode="incremental")
    with pytest.raises(Exception) as exc:
        await update_pipeline("p1", body, current_user=_user(), db=db)
    # FastAPI HTTPException
    assert getattr(exc.value, "status_code", None) == 422


@pytest.mark.asyncio
async def test_patch_empty_string_clears_incremental_key(monkeypatch):
    p = _pipeline(mode="incremental", incremental_key="updated_at")
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = p
    # Switch to full + clear the cursor in the same call.
    body = PipelineUpdate(mode="full", incremental_key="")
    await update_pipeline("p1", body, current_user=_user(), db=db)
    assert p.incremental_key is None
    assert p.mode == "full"


@pytest.mark.asyncio
async def test_patch_rejects_invalid_mode(monkeypatch):
    p = _pipeline()
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = p
    body = PipelineUpdate(mode="weird")
    with pytest.raises(Exception) as exc:
        await update_pipeline("p1", body, current_user=_user(), db=db)
    assert getattr(exc.value, "status_code", None) == 422


# ── POST /redetect-watermark ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_redetect_persists_new_cursor(monkeypatch):
    p = _pipeline()
    db = MagicMock()
    db.query.return_value.filter.return_value.first.side_effect = [
        p,  # _get_pipeline_for_user
        SimpleNamespace(id=1, db_type="postgres"),  # source connection
    ]

    # Patch the connector + classifier imports inside the endpoint.
    connector = MagicMock()
    connector.__enter__ = MagicMock(return_value=connector)
    connector.__exit__ = MagicMock(return_value=False)
    connector.get_table_schema = MagicMock(
        return_value=SimpleNamespace(columns=[
            {"name": "id", "type": "bigint", "primary_key": True},
            {"name": "updated_at", "type": "timestamp"},
        ]),
    )

    with patch("backend.connectors.factory.get_connector_for_connection", return_value=connector), \
         patch("backend.connectors.factory.get_connector_registration",
               return_value=SimpleNamespace(type_id="postgres")), \
         patch("backend.services.watermark_classifier.resolve_watermark",
               return_value={"orders": "updated_at"}):
        out = await redetect_watermark("p1", current_user=_user(), db=db)

    assert p.incremental_key == "updated_at"
    assert p.mode == "incremental"
    assert out is p


@pytest.mark.asyncio
async def test_redetect_falls_back_to_full_when_no_cursor(monkeypatch):
    p = _pipeline(mode="incremental", incremental_key="created_at")
    db = MagicMock()
    db.query.return_value.filter.return_value.first.side_effect = [
        p,
        SimpleNamespace(id=1, db_type="postgres"),
    ]

    connector = MagicMock()
    connector.__enter__ = MagicMock(return_value=connector)
    connector.__exit__ = MagicMock(return_value=False)
    connector.get_table_schema = MagicMock(return_value=SimpleNamespace(columns=[]))

    with patch("backend.connectors.factory.get_connector_for_connection", return_value=connector), \
         patch("backend.connectors.factory.get_connector_registration",
               return_value=SimpleNamespace(type_id="postgres")), \
         patch("backend.services.watermark_classifier.resolve_watermark",
               return_value={"orders": None}):
        await redetect_watermark("p1", current_user=_user(), db=db)

    assert p.incremental_key is None
    assert p.mode == "full"


# ── POST /load-history ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_load_history_queues_with_iso_since(monkeypatch):
    p = _pipeline(mode="incremental", incremental_key="updated_at")
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = p

    fake_task = SimpleNamespace(id="task-abc")
    delay = MagicMock(return_value=fake_task)
    with patch("backend.pipelines.tasks.run_pipeline_task", SimpleNamespace(delay=delay)):
        body = LoadHistoryRequest(since=datetime(2026, 1, 1, tzinfo=timezone.utc))
        resp = await load_history("p1", body, current_user=_user(), db=db)

    assert resp["run_id"] == "task-abc"
    assert resp["status"] == "queued"
    # delay() must include the ISO since timestamp as the 4th positional arg.
    args = delay.call_args[0]
    assert args[0] == "p1" and args[1] == "manual-backfill" and args[2] == "u1"
    assert "2026-01-01" in args[3]


@pytest.mark.asyncio
async def test_load_history_rejects_full_mode_pipeline(monkeypatch):
    p = _pipeline(mode="full", incremental_key=None)
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = p
    body = LoadHistoryRequest(since=datetime(2026, 1, 1, tzinfo=timezone.utc))
    with pytest.raises(Exception) as exc:
        await load_history("p1", body, current_user=_user(), db=db)
    assert getattr(exc.value, "status_code", None) == 422
