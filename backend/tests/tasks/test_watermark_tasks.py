"""Tests for the background watermark refinement Celery task.

Exercises the in-process logic of `refine_watermarks_task` (skip cases, pipeline
mutation, no-change short-circuit) by patching out the DB session and the
classifier. The task itself is a `@shared_task` but is invoked synchronously
via `.run()` (eager mode) so no broker is required.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import backend.tasks.watermark_tasks as wt


def _settings_patch(monkeypatch, provider="openai", model="gpt-4o-mini"):
    from backend.config import settings
    monkeypatch.setattr(settings, "watermark_classifier_provider", provider, raising=False)
    monkeypatch.setattr(settings, "watermark_classifier_model", model, raising=False)


def _pipeline(id_="p1", table="orders", mode="full", key=None):
    return SimpleNamespace(
        id=id_,
        source_connection_id=42,
        mode=mode,
        incremental_key=key,
        extraction_config={"tables": [table]},
    )


def _fake_session(connection, pipelines):
    db = MagicMock()

    # First .query(DatabaseConnection)...first() → connection;
    # second .query(Pipeline).filter(...).all() → pipelines.
    conn_q = MagicMock()
    conn_q.filter.return_value.first.return_value = connection

    pipe_q = MagicMock()
    pipe_q.filter.return_value.all.return_value = pipelines

    def _query(model):
        # Differentiate by model name to keep things explicit.
        name = getattr(model, "__name__", "")
        if "Connection" in name:
            return conn_q
        return pipe_q

    db.query.side_effect = _query
    db.commit.return_value = None
    return db


def test_skipped_when_llm_unconfigured(monkeypatch):
    """Both env knobs empty → early return, no DB session opened."""
    _settings_patch(monkeypatch, provider="", model="")

    def _boom():
        raise AssertionError("must not open DB when LLM unconfigured")
    monkeypatch.setattr("backend.database.session.SessionLocal", _boom)

    out = wt.refine_watermarks_task.run(connection_id=1, pipeline_ids=["p1"])
    assert out == {"status": "skipped", "reason": "llm_not_configured"}


def test_skipped_when_connection_missing(monkeypatch):
    _settings_patch(monkeypatch)
    db = _fake_session(connection=None, pipelines=[])
    monkeypatch.setattr("backend.database.session.SessionLocal", lambda: db)
    out = wt.refine_watermarks_task.run(connection_id=99, pipeline_ids=["p1"])
    assert out["status"] == "skipped"
    assert out["reason"] == "connection_missing"


def test_skipped_when_no_pipelines(monkeypatch):
    _settings_patch(monkeypatch)
    db = _fake_session(SimpleNamespace(id=42), pipelines=[])
    monkeypatch.setattr("backend.database.session.SessionLocal", lambda: db)
    out = wt.refine_watermarks_task.run(connection_id=42, pipeline_ids=["px"])
    assert out["reason"] == "no_pipelines"


def test_skipped_when_connector_open_fails(monkeypatch):
    _settings_patch(monkeypatch)
    p = _pipeline()
    db = _fake_session(SimpleNamespace(id=42), pipelines=[p])
    monkeypatch.setattr("backend.database.session.SessionLocal", lambda: db)

    def _boom(_):
        raise RuntimeError("conn refused")
    monkeypatch.setattr("backend.connectors.factory.get_connector_for_connection", _boom)

    out = wt.refine_watermarks_task.run(connection_id=42, pipeline_ids=["p1"])
    assert out["reason"] == "connector_open_failed"


def test_no_change_when_llm_matches_current(monkeypatch):
    """LLM returns the same key already set → no DB write, updated=0."""
    _settings_patch(monkeypatch)
    p = _pipeline(mode="incremental", key="updated_at")
    db = _fake_session(SimpleNamespace(id=42), pipelines=[p])
    monkeypatch.setattr("backend.database.session.SessionLocal", lambda: db)

    fake_connector = SimpleNamespace(
        get_table_schema=lambda t, schema=None: SimpleNamespace(
            columns=[{"name": "updated_at", "type": "timestamp"}],
        ),
        close=lambda: None,
    )
    monkeypatch.setattr(
        "backend.connectors.factory.get_connector_for_connection",
        lambda c: fake_connector,
    )
    monkeypatch.setattr(
        "backend.services.watermark_classifier.classify_connection",
        lambda schemas, **kw: {"orders": "updated_at"},
    )

    out = wt.refine_watermarks_task.run(connection_id=42, pipeline_ids=["p1"])
    assert out == {"status": "ok", "connection_id": 42, "considered": 1, "updated": 0}
    db.commit.assert_not_called()


def test_promotes_full_to_incremental_when_llm_finds_cursor(monkeypatch):
    _settings_patch(monkeypatch)
    p = _pipeline(mode="full", key=None)
    db = _fake_session(SimpleNamespace(id=42), pipelines=[p])
    monkeypatch.setattr("backend.database.session.SessionLocal", lambda: db)

    fake_connector = SimpleNamespace(
        get_table_schema=lambda t, schema=None: SimpleNamespace(
            columns=[
                {"name": "id", "type": "int"},
                {"name": "event_timestamp", "type": "timestamp"},
            ],
        ),
        close=lambda: None,
    )
    monkeypatch.setattr(
        "backend.connectors.factory.get_connector_for_connection",
        lambda c: fake_connector,
    )
    monkeypatch.setattr(
        "backend.services.watermark_classifier.classify_connection",
        lambda schemas, **kw: {"orders": "event_timestamp"},
    )

    out = wt.refine_watermarks_task.run(connection_id=42, pipeline_ids=["p1"])
    assert out["updated"] == 1
    assert p.mode == "incremental"
    assert p.incremental_key == "event_timestamp"
    assert p.extraction_config["incremental_key"] == "event_timestamp"
    assert "initial_value" in p.extraction_config
    db.commit.assert_called_once()


def test_demotes_incremental_to_full_when_llm_returns_none(monkeypatch):
    _settings_patch(monkeypatch)
    p = _pipeline(mode="incremental", key="created_at")
    p.extraction_config = {"tables": ["lookup"], "incremental_key": "created_at",
                           "initial_value": "2026-01-01T00:00:00+00:00"}
    db = _fake_session(SimpleNamespace(id=42), pipelines=[p])
    monkeypatch.setattr("backend.database.session.SessionLocal", lambda: db)

    fake_connector = SimpleNamespace(
        get_table_schema=lambda t, schema=None: SimpleNamespace(
            columns=[{"name": "code", "type": "varchar"}],
        ),
        close=lambda: None,
    )
    monkeypatch.setattr(
        "backend.connectors.factory.get_connector_for_connection",
        lambda c: fake_connector,
    )
    monkeypatch.setattr(
        "backend.services.watermark_classifier.classify_connection",
        lambda schemas, **kw: {"lookup": None},
    )

    out = wt.refine_watermarks_task.run(connection_id=42, pipeline_ids=["p1"])
    assert out["updated"] == 1
    assert p.mode == "full"
    assert p.incremental_key is None
    assert "incremental_key" not in p.extraction_config
    assert "initial_value" not in p.extraction_config


def test_multi_table_pipelines_skipped(monkeypatch):
    """Pipelines with len(tables) != 1 are not eligible for refinement."""
    _settings_patch(monkeypatch)
    p = _pipeline()
    p.extraction_config = {"tables": ["orders", "lookup"]}
    db = _fake_session(SimpleNamespace(id=42), pipelines=[p])
    monkeypatch.setattr("backend.database.session.SessionLocal", lambda: db)

    out = wt.refine_watermarks_task.run(connection_id=42, pipeline_ids=["p1"])
    assert out["reason"] == "no_single_table_pipelines"
