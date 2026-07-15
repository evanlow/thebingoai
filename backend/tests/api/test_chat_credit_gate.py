"""POST /api/chat credit gate — the REST path must bill like the websocket path.

The endpoint lost its credit wiring when the SSE stream variant was removed
(c1a1c4d), leaving an authenticated orchestrator run that bypassed the org
pool entirely. These tests pin the restored contract:

  - exhausted pool → 402 BEFORE the orchestrator runs,
  - success → persist the answer BEFORE charging (aexit(None) last),
  - orchestrator failure → aexit(exc) so the turn is never billed.
"""
import asyncio
import types
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

import backend.api.chat as chat_mod
from backend.schemas.chat import ChatRequest


class _FakeMgr:
    """Records lifecycle calls; optionally raises on enter."""

    instance = None

    def __init__(self, raise_on_enter=None, order=None, **kwargs):
        self.kwargs = kwargs
        self.calls = order if order is not None else []
        self._raise_on_enter = raise_on_enter
        _FakeMgr.instance = self

    async def __aenter__(self):
        if self._raise_on_enter is not None:
            raise self._raise_on_enter
        self.calls.append("aenter")
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self.calls.append(("aexit", exc_type))
        return False


def _ctx_stub():
    return types.SimpleNamespace(
        agent_context="", custom_agents=None, memory_context=None,
        user_skills=None, user_memories_context=None, skill_suggestions=None,
        soul_prompt=None, profile=None,
    )


@pytest.fixture
def wired(monkeypatch):
    """Stub every heavy dependency of the chat handler; return the shared
    order log that the fake manager, orchestrator, and persist append to."""
    order = []

    conversation = types.SimpleNamespace(id="c-1", thread_id="t-1")
    monkeypatch.setattr(
        chat_mod.ConversationService, "create_conversation",
        staticmethod(lambda db, uid, title: conversation),
    )

    def _add_message(db, cid, role, content):
        if role == "assistant":
            order.append("persist")

    monkeypatch.setattr(
        chat_mod.ConversationService, "add_message", staticmethod(_add_message)
    )
    monkeypatch.setattr(
        chat_mod.ConversationService, "get_conversation_history",
        staticmethod(lambda db, tid, uid: []),
    )

    import backend.services.heartbeat_context as hb

    async def _build_ctx(**kw):
        return _ctx_stub()

    monkeypatch.setattr(hb, "build_orchestrator_context", _build_ctx)

    import backend.agents.profile_llm as pl
    monkeypatch.setattr(pl, "resolve_published_llm", lambda profile: (None, None, None))

    import backend.agents as agents

    async def _run_orchestrator(**kw):
        order.append("orchestrate")
        return {"message": "answer", "metadata": {}, "success": True}

    monkeypatch.setattr(agents, "run_orchestrator", _run_orchestrator)

    import backend.plugins.loader as loader
    monkeypatch.setattr(loader, "get_loaded_plugins", lambda: {})

    monkeypatch.setattr(
        chat_mod.TokenTrackingService, "track_usage", staticmethod(lambda **kw: None)
    )

    import backend.services.token_tracking_service as tts
    monkeypatch.setattr(
        tts, "CreditContextManager",
        lambda **kw: _FakeMgr(order=order, **kw),
    )
    return order


def _call(order):
    user = types.SimpleNamespace(id="u-1")
    req = ChatRequest(message="hello")
    return asyncio.run(chat_mod.chat(req, current_user=user, db=MagicMock()))


def test_success_persists_before_charging(wired):
    resp = _call(wired)
    assert resp.message == "answer"
    # Strict order: gate on entry, run, persist the answer, THEN charge.
    assert wired == ["aenter", "orchestrate", "persist", ("aexit", None)]


def test_exhausted_pool_returns_402_before_orchestrator(wired, monkeypatch):
    import backend.services.token_tracking_service as tts
    monkeypatch.setattr(
        tts, "CreditContextManager",
        lambda **kw: _FakeMgr(
            raise_on_enter=tts.InsufficientCreditsError(reason="org_pool"),
            order=wired, **kw,
        ),
    )
    with pytest.raises(HTTPException) as ex:
        _call(wired)
    assert ex.value.status_code == 402
    assert ex.value.detail["cap"] == "org_pool"
    assert wired == []  # orchestrator never ran, nothing billed


def test_orchestrator_failure_exits_with_exception_and_reraises(wired, monkeypatch):
    import backend.agents as agents

    async def _boom(**kw):
        wired.append("orchestrate")
        raise RuntimeError("agent died")

    monkeypatch.setattr(agents, "run_orchestrator", _boom)
    with pytest.raises(RuntimeError):
        _call(wired)
    # __aexit__ received the exception → the manager skips billing.
    assert wired == ["aenter", "orchestrate", ("aexit", RuntimeError)]


def test_manager_setup_failure_degrades_to_unbilled_turn(wired, monkeypatch):
    # Credit wiring must never block chat: a non-credit setup error proceeds
    # unbilled, same as the websocket path.
    import backend.services.token_tracking_service as tts

    def _broken(**kw):
        raise RuntimeError("plugin loader down")

    monkeypatch.setattr(tts, "CreditContextManager", _broken)
    resp = _call(wired)
    assert resp.message == "answer"
    assert wired == ["orchestrate", "persist"]
