"""Tests for the per-pipeline override + redetect + backfill API endpoints.

These exercise the request/response shapes and the in-process logic the
endpoints share with the runner (mode validation, extraction_config updates,
backfill ISO parsing). Heavy I/O (Celery dispatch, connector open, DB session)
is patched out. The `override`/`backfill` handlers are `async def`, so those
calls go through `asyncio.run(...)` (`_run`) — pytest-asyncio is not installed
in this image. `redetect_watermark` is sync `def` (it runs `asyncio.run`
internally via the classifier), so it's called directly.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

import backend.pipelines.api as api


def _run(coro):
    return asyncio.run(coro)


# ── Fixtures ────────────────────────────────────────────────────────────────

def _pipe(**overrides):
    base = dict(
        id="p1",
        mode="incremental",
        incremental_key="created_at",
        unique_key=["id"],
        extraction_config={"tables": ["orders"], "incremental_key": "created_at"},
        source_connection_id=42,
        owner_scope_id="u-1",
        created_by_user_id="u-1",
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _fake_db(pipeline):
    """Stub db.query(...).filter(...).first() → pipeline. db.commit/refresh no-op."""
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = pipeline
    db.commit.return_value = None
    db.refresh.return_value = None
    return db


def _user(id_="u-1"):
    return SimpleNamespace(id=id_)


# ── override_pipeline ───────────────────────────────────────────────────────

def test_override_accepts_partial_update_keeps_unspecified_fields():
    pipeline = _pipe()
    db = _fake_db(pipeline)

    body = api.PipelineOverride(incremental_key="updated_at")  # mode not provided
    result = _run(api.override_pipeline(
        pipeline_id="p1", body=body, current_user=_user(), db=db,
    ))
    assert result.mode == "incremental"  # unchanged
    assert result.incremental_key == "updated_at"
    assert result.extraction_config["incremental_key"] == "updated_at"


def test_override_full_mode_drops_incremental_hints():
    pipeline = _pipe(extraction_config={
        "tables": ["orders"],
        "incremental_key": "created_at",
        "initial_value": "2026-01-01T00:00:00+00:00",
    })
    db = _fake_db(pipeline)

    body = api.PipelineOverride(mode="full")
    result = _run(api.override_pipeline(
        pipeline_id="p1", body=body, current_user=_user(), db=db,
    ))
    assert result.mode == "full"
    assert result.incremental_key is None
    assert "incremental_key" not in result.extraction_config
    assert "initial_value" not in result.extraction_config


def test_override_rejects_invalid_mode():
    pipeline = _pipe()
    db = _fake_db(pipeline)
    body = api.PipelineOverride(mode="weekly")
    with pytest.raises(HTTPException) as exc:
        _run(api.override_pipeline("p1", body, _user(), db))
    assert exc.value.status_code == 422


def test_override_incremental_without_key_rejected():
    pipeline = _pipe(mode="full", incremental_key=None)
    db = _fake_db(pipeline)
    body = api.PipelineOverride(mode="incremental")  # no key supplied
    with pytest.raises(HTTPException) as exc:
        _run(api.override_pipeline("p1", body, _user(), db))
    assert exc.value.status_code == 422
    assert "incremental_key" in exc.value.detail


# ── redetect_watermark ──────────────────────────────────────────────────────

def test_redetect_returns_classifier_suggestion(monkeypatch):
    pipeline = _pipe()
    db = _fake_db(pipeline)
    # Connection lookup follows; second `.first()` should return the connection.
    db.query.return_value.filter.return_value.first.side_effect = [
        pipeline, SimpleNamespace(id=42),
    ]

    fake_connector = SimpleNamespace(
        get_table_schema=lambda t, schema=None: SimpleNamespace(
            columns=[
                {"name": "id", "type": "int"},
                {"name": "updated_at", "type": "timestamp"},
            ]
        ),
        close=lambda: None,
    )
    monkeypatch.setattr(
        "backend.connectors.factory.get_connector_for_connection",
        lambda c: fake_connector,
    )

    result = api.redetect_watermark("p1", _user(), db)
    assert result.suggested_incremental_key == "updated_at"
    assert result.current_incremental_key == "created_at"
    assert result.current_mode == "incremental"
    assert result.table == "orders"


def test_redetect_multi_table_pipeline_returns_none():
    pipeline = _pipe(extraction_config={"tables": ["orders", "lookup"]})
    db = _fake_db(pipeline)
    result = api.redetect_watermark("p1", _user(), db)
    assert result.table is None
    assert result.suggested_incremental_key is None


def test_redetect_503_when_schema_fetch_fails(monkeypatch):
    """Connector opens OK but schema fetch raises → 503, not a silent null
    suggestion. The "no usable cursor" UI message must not mask a transient DB
    reachability failure (e.g. MySQL container restart, network blip)."""
    pipeline = _pipe()
    db = _fake_db(pipeline)
    db.query.return_value.filter.return_value.first.side_effect = [
        pipeline, SimpleNamespace(id=42),
    ]

    def _schema_boom(table, schema=None):
        raise RuntimeError("mysql: lost connection")

    fake_connector = SimpleNamespace(
        get_table_schema=_schema_boom,
        close=lambda: None,
    )
    monkeypatch.setattr(
        "backend.connectors.factory.get_connector_for_connection",
        lambda c: fake_connector,
    )

    with pytest.raises(HTTPException) as exc:
        api.redetect_watermark("p1", _user(), db)
    assert exc.value.status_code == 503
    assert "schema" in exc.value.detail.lower()


def test_redetect_503_when_connector_unreachable(monkeypatch):
    pipeline = _pipe()
    db = _fake_db(pipeline)
    db.query.return_value.filter.return_value.first.side_effect = [
        pipeline, SimpleNamespace(id=42),
    ]

    def _boom(_):
        raise RuntimeError("connection refused")
    monkeypatch.setattr(
        "backend.connectors.factory.get_connector_for_connection", _boom,
    )

    with pytest.raises(HTTPException) as exc:
        api.redetect_watermark("p1", _user(), db)
    assert exc.value.status_code == 503


def test_redetect_survives_running_loop_with_llm_classifier(monkeypatch):
    """Regression: redetect is sync `def`, so Starlette runs it in a threadpool
    and `classify_connection`'s internal `asyncio.run()` gets a fresh loop. If
    the handler were `async def`, that `asyncio.run()` would execute inside the
    running loop and raise RuntimeError. Reproduce by invoking the handler from
    within a running loop via `asyncio.to_thread` (mirrors run_in_threadpool).
    """
    pipeline = _pipe()
    db = _fake_db(pipeline)
    db.query.return_value.filter.return_value.first.side_effect = [
        pipeline, SimpleNamespace(id=42),
    ]
    fake_connector = SimpleNamespace(
        get_table_schema=lambda t, schema=None: SimpleNamespace(
            columns=[
                {"name": "id", "type": "int"},
                {"name": "updated_at", "type": "timestamp"},
            ]
        ),
        close=lambda: None,
    )
    monkeypatch.setattr(
        "backend.connectors.factory.get_connector_for_connection",
        lambda c: fake_connector,
    )

    # Force classify_connection down the LLM path (where asyncio.run lives).
    from backend.config import settings
    monkeypatch.setattr(settings, "watermark_classifier_provider", "openai")
    monkeypatch.setattr(settings, "watermark_classifier_model", "gpt-4o-mini")

    class _FakeProvider:
        async def chat(self, messages, temperature, max_tokens):
            return (
                '{"results": [{"table": "orders", "column": "updated_at", '
                '"confidence": "high"}]}'
            )

    monkeypatch.setattr(
        "backend.llm.factory.get_provider",
        lambda provider, model=None: _FakeProvider(),
    )

    async def _call_from_running_loop():
        return await asyncio.to_thread(api.redetect_watermark, "p1", _user(), db)

    result = asyncio.run(_call_from_running_loop())
    assert result.suggested_incremental_key == "updated_at"


# ── backfill_pipeline ───────────────────────────────────────────────────────

def test_backfill_rejects_full_mode():
    pipeline = _pipe(mode="full")
    db = _fake_db(pipeline)
    body = api.BackfillRequest(backfill_since="2026-01-01T00:00:00+00:00")
    with pytest.raises(HTTPException) as exc:
        _run(api.backfill_pipeline("p1", body, _user(), db))
    assert exc.value.status_code == 409


def test_backfill_rejects_unparseable_iso():
    pipeline = _pipe()
    db = _fake_db(pipeline)
    body = api.BackfillRequest(backfill_since="not-a-date")
    with pytest.raises(HTTPException) as exc:
        _run(api.backfill_pipeline("p1", body, _user(), db))
    assert exc.value.status_code == 422


# ── PipelineResponse schema ─────────────────────────────────────────────────

def test_pipeline_response_exposes_unique_key():
    """The frontend Pipelines tab reads `unique_key` from this response to
    decide whether to surface the "no PK → backfill dedup risk" warning.
    Catches regression where the field is removed from the Pydantic model."""
    src = SimpleNamespace(
        id="p1",
        name="orders",
        source_connection_id=42,
        owner_scope_kind="user",
        owner_scope_id="u-1",
        target_table="acme__orders",
        cron="0 2 * * *",
        timezone="UTC",
        mode="incremental",
        incremental_key="created_at",
        unique_key=["id"],
        extraction_config={"tables": ["orders"]},
        pipeline_fingerprint="abc",
        last_run_at=None,
        last_run_status=None,
        next_run_at=None,
        enabled=True,
        created_by_user_id="u-1",
        created_at=None,
        updated_at=None,
    )
    resp = api.PipelineResponse.model_validate(src)
    assert resp.unique_key == ["id"]
    # Round-trip through JSON serialisation so we catch any encoder gap.
    assert resp.model_dump()["unique_key"] == ["id"]


def test_pipeline_response_unique_key_allows_none():
    src = SimpleNamespace(
        id="p1",
        name="lookup",
        source_connection_id=42,
        owner_scope_kind="user",
        owner_scope_id="u-1",
        target_table="acme__lookup",
        cron=None,
        timezone="UTC",
        mode="full",
        incremental_key=None,
        unique_key=None,
        extraction_config={"tables": ["lookup"]},
        pipeline_fingerprint="abc",
        last_run_at=None,
        last_run_status=None,
        next_run_at=None,
        enabled=True,
        created_by_user_id="u-1",
        created_at=None,
        updated_at=None,
    )
    resp = api.PipelineResponse.model_validate(src)
    assert resp.unique_key is None


def test_backfill_dispatches_task_with_since(monkeypatch):
    pipeline = _pipe()
    db = _fake_db(pipeline)

    task = SimpleNamespace(id="task-123")
    delay_calls = {}

    def _delay(pid, triggered_by, user_id, backfill_since):
        delay_calls.update(
            pid=pid, triggered_by=triggered_by,
            user_id=user_id, backfill_since=backfill_since,
        )
        return task

    monkeypatch.setattr(
        "backend.pipelines.tasks.run_pipeline_task",
        SimpleNamespace(delay=_delay),
    )

    body = api.BackfillRequest(backfill_since="2026-01-01T00:00:00+00:00")
    result = _run(api.backfill_pipeline("p1", body, _user(), db))
    assert result == {
        "run_id": "task-123",
        "status": "queued",
        "backfill_since": "2026-01-01T00:00:00+00:00",
    }
    assert delay_calls == {
        "pid": "p1",
        "triggered_by": "manual",
        "user_id": "u-1",
        "backfill_since": "2026-01-01T00:00:00+00:00",
    }


def _capture_backfill_since(monkeypatch):
    """Patch run_pipeline_task.delay to capture the `backfill_since` it receives."""
    captured = {}

    def _delay(pid, triggered_by, user_id, backfill_since):
        captured["backfill_since"] = backfill_since
        return SimpleNamespace(id="task-x")

    monkeypatch.setattr(
        "backend.pipelines.tasks.run_pipeline_task",
        SimpleNamespace(delay=_delay),
    )
    return captured


def test_backfill_normalizes_naive_to_utc(monkeypatch):
    # A timezone-naive `backfill_since` would reach the dlt cursor and be
    # compared against an aware UTC `end_value` → TypeError. The handler must
    # interpret naive input as UTC and forward an aware value.
    captured = _capture_backfill_since(monkeypatch)
    body = api.BackfillRequest(backfill_since="2026-01-01T09:30:00")
    result = _run(api.backfill_pipeline("p1", body, _user(), _fake_db(_pipe())))
    assert captured["backfill_since"] == "2026-01-01T09:30:00+00:00"
    assert result["backfill_since"] == "2026-01-01T09:30:00+00:00"


def test_backfill_converts_offset_to_utc(monkeypatch):
    # A non-UTC offset is converted to the equivalent UTC instant.
    captured = _capture_backfill_since(monkeypatch)
    body = api.BackfillRequest(backfill_since="2024-06-01T12:00:00+08:00")
    result = _run(api.backfill_pipeline("p1", body, _user(), _fake_db(_pipe())))
    assert captured["backfill_since"] == "2024-06-01T04:00:00+00:00"
    assert result["backfill_since"] == "2024-06-01T04:00:00+00:00"
