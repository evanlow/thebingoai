"""Tests for the per-connection semantic-layer API endpoints:

    GET  /api/connections/{id}/semantics
    PUT  /api/connections/{id}/semantics
    POST /api/connections/{id}/semantics/generate-descriptions
    GET  /api/connections/{id}/semantics/generation-status

Self-contained: mounts only the connections router on a throwaway FastAPI app
with dependency overrides, so it never touches a real DB / Redis / Celery. The
service + task modules the handlers import lazily are patched at call time.
"""
from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock, patch

CONN = SimpleNamespace(id=1, uuid="conn-uuid", org_id=None, user_id="u1")


def _build_client(connection):
    """A TestClient whose connection lookup returns *connection* (or None)."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from backend.api.connections import router
    from backend.database.session import get_db
    from backend.auth.dependencies import get_current_user

    class _Query:
        def filter(self, *_a, **_kw): return self
        def outerjoin(self, *_a, **_kw): return self
        def first(self): return connection

    db = MagicMock()
    db.query.return_value = _Query()

    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id="u1", org_id=None)
    return TestClient(app)


def _no_governance():
    """Replace backend.governance.contract with a permissive stub for mutate routes."""
    mod = ModuleType("backend.governance.contract")
    mod.require = MagicMock()
    return patch.dict(sys.modules, {"backend.governance.contract": mod})


def _fake_semantic_tasks(status="idle"):
    mod = ModuleType("backend.tasks.semantic_tasks")
    mod.generate_glossary_drafts = MagicMock()
    mod.get_generation_status = MagicMock(return_value={"status": status})
    mod.set_generation_status = MagicMock()
    return mod


# --- GET /semantics ----------------------------------------------------------

def test_get_semantics_returns_saved_layer():
    layer = {
        "glossary": {"orders.id": {"description": "PK", "source": "human", "status": "confirmed"}},
        "relationships": [{"from": "orders.user_id", "to": "users.id"}],
        "definitions": [],
    }
    client = _build_client(CONN)
    with patch("backend.services.semantic_layer.load_semantic_layer", return_value=layer):
        resp = client.get("/api/connections/conn-uuid/semantics")
    assert resp.status_code == 200
    assert resp.json() == layer


def test_get_semantics_empty_default_when_none_saved():
    client = _build_client(CONN)
    with patch("backend.services.semantic_layer.load_semantic_layer", return_value=None):
        resp = client.get("/api/connections/conn-uuid/semantics")
    assert resp.status_code == 200
    assert resp.json() == {"glossary": {}, "relationships": [], "definitions": []}


def test_get_semantics_404_when_connection_missing():
    client = _build_client(None)
    resp = client.get("/api/connections/ghost/semantics")
    assert resp.status_code == 404


# --- PUT /semantics ----------------------------------------------------------

def test_put_semantics_persists_sections():
    saved = {
        "glossary": {"orders.id": {"description": "PK", "source": "human", "status": "confirmed"}},
        "relationships": [{"from": "orders.user_id", "to": "users.id", "status": "confirmed"}],
        "definitions": [],
    }
    client = _build_client(CONN)
    body = {"glossary": saved["glossary"], "relationships": saved["relationships"]}
    with _no_governance(), patch(
        "backend.services.semantic_layer.upsert_semantic_layer", return_value=saved
    ) as upsert:
        resp = client.put("/api/connections/conn-uuid/semantics", json=body)
    assert resp.status_code == 200
    assert resp.json() == saved
    # sections forwarded to the service; unset definitions stays None (section-replace)
    _, kwargs = upsert.call_args
    assert kwargs["glossary"] == saved["glossary"]
    assert kwargs["relationships"] == saved["relationships"]
    assert kwargs["definitions"] is None


def test_put_semantics_404_when_connection_missing():
    client = _build_client(None)
    with _no_governance():
        resp = client.put("/api/connections/ghost/semantics", json={"glossary": {}})
    assert resp.status_code == 404


# --- POST /semantics/generate-descriptions -----------------------------------

def test_generate_409_when_not_profiled():
    client = _build_client(CONN)
    with _no_governance(), patch(
        "backend.services.connection_context.load_connection_context", return_value=None
    ):
        resp = client.post(
            "/api/connections/conn-uuid/semantics/generate-descriptions",
            json={"tables": ["orders"]},
        )
    assert resp.status_code == 409


def test_generate_400_on_unknown_table():
    client = _build_client(CONN)
    ctx = {"tables": {"orders": {}}}
    with _no_governance(), patch(
        "backend.services.connection_context.load_connection_context", return_value=ctx
    ), patch.dict(sys.modules, {"backend.tasks.semantic_tasks": _fake_semantic_tasks()}):
        resp = client.post(
            "/api/connections/conn-uuid/semantics/generate-descriptions",
            json={"tables": ["ghost"]},
        )
    assert resp.status_code == 400


def test_generate_202_queues_task():
    client = _build_client(CONN)
    ctx = {"tables": {"orders": {}}}
    fake = _fake_semantic_tasks(status="idle")
    with _no_governance(), patch(
        "backend.services.connection_context.load_connection_context", return_value=ctx
    ), patch.dict(sys.modules, {"backend.tasks.semantic_tasks": fake}):
        resp = client.post(
            "/api/connections/conn-uuid/semantics/generate-descriptions",
            json={"tables": ["orders"]},
        )
    assert resp.status_code == 202
    assert resp.json() == {"status": "queued", "tables": 1}
    fake.generate_glossary_drafts.delay.assert_called_once_with(1, ["orders"])


def test_generate_400_when_already_running():
    client = _build_client(CONN)
    ctx = {"tables": {"orders": {}}}
    fake = _fake_semantic_tasks(status="running")
    with _no_governance(), patch(
        "backend.services.connection_context.load_connection_context", return_value=ctx
    ), patch.dict(sys.modules, {"backend.tasks.semantic_tasks": fake}):
        resp = client.post(
            "/api/connections/conn-uuid/semantics/generate-descriptions",
            json={"tables": ["orders"]},
        )
    assert resp.status_code == 400
    fake.generate_glossary_drafts.delay.assert_not_called()


# --- GET /semantics/generation-status ----------------------------------------

def test_generation_status_returns_payload():
    client = _build_client(CONN)
    payload = {"status": "done", "progress": "3/3"}
    fake = _fake_semantic_tasks()
    fake.get_generation_status = MagicMock(return_value=payload)
    with patch.dict(sys.modules, {"backend.tasks.semantic_tasks": fake}):
        resp = client.get("/api/connections/conn-uuid/semantics/generation-status")
    assert resp.status_code == 200
    assert resp.json() == payload
