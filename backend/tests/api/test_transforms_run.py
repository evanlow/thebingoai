"""Tests for POST /api/transforms/{model_id}/run — manual re-run trigger.

Self-contained: mounts only the transforms router on a throwaway FastAPI app with
dependency overrides, so it neither imports backend.main nor touches a real DB /
Celery. The dbt task module is injected via sys.modules because the handler imports
`backend.transforms.tasks` lazily at call time.
"""
from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


def _build_client(model):
    """A TestClient whose transforms DB lookup returns *model* (or None)."""
    from backend.transforms.api import router
    from backend.database.session import get_db
    from backend.auth.dependencies import get_current_user

    class _Query:
        def filter(self, *_a, **_kw): return self
        def first(self): return model

    db = MagicMock()
    db.query.return_value = _Query()

    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id="u1")
    return TestClient(app)


def _fake_tasks_module(task_id="task-123"):
    mod = ModuleType("backend.transforms.tasks")
    run_dbt_task = MagicMock()
    run_dbt_task.delay.return_value = SimpleNamespace(id=task_id)
    mod.run_dbt_task = run_dbt_task
    return mod, run_dbt_task


def test_run_queues_task_and_returns_run_id():
    model = SimpleNamespace(
        id="m1", created_by_user_id="u1",
        owner_scope_kind="user", owner_scope_id="u1",
    )
    client = _build_client(model)
    fake_mod, run_dbt_task = _fake_tasks_module("task-123")

    with patch.dict(sys.modules, {"backend.transforms.tasks": fake_mod}):
        resp = client.post("/api/transforms/m1/run")

    assert resp.status_code == 202
    assert resp.json() == {"run_id": "task-123", "status": "queued"}
    run_dbt_task.delay.assert_called_once_with("user", "u1", ["m1"], "manual")


def test_run_404_when_model_missing():
    client = _build_client(None)
    fake_mod, run_dbt_task = _fake_tasks_module()

    with patch.dict(sys.modules, {"backend.transforms.tasks": fake_mod}):
        resp = client.post("/api/transforms/nope/run")

    assert resp.status_code == 404
    run_dbt_task.delay.assert_not_called()


def test_run_404_when_owned_by_another_user():
    model = SimpleNamespace(
        id="m1", created_by_user_id="someone-else",
        owner_scope_kind="user", owner_scope_id="someone-else",
    )
    client = _build_client(model)
    fake_mod, run_dbt_task = _fake_tasks_module()

    with patch.dict(sys.modules, {"backend.transforms.tasks": fake_mod}):
        resp = client.post("/api/transforms/m1/run")

    assert resp.status_code == 404
    run_dbt_task.delay.assert_not_called()
