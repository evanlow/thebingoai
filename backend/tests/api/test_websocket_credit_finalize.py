"""_finalize_credit_turn + _complete_turn — the post-`done` credit close-out.

Covers the ordering/void/error-swallow semantics of the money path. The helper
tests pin _finalize_credit_turn's behaviour; the _complete_turn tests pin the
turn-completion ORDER — persist BEFORE charge BEFORE forwarding `done` — so a
persist failure can never bill the user (the regression the reviewer flagged).
"""
import asyncio
import types

import pytest

import backend.api.websocket as ws
from backend.api.websocket import _finalize_credit_turn, _complete_turn


class _FakeMgr:
    def __init__(self, raise_on_exit: bool = False):
        self.calls: list = []
        self._raise = raise_on_exit

    def void(self, reason: str) -> None:
        self.calls.append(("void", reason))

    async def __aenter__(self):
        # Deliberately not logged: the helper tests assert on the exact call
        # list and only the close-out half is under test there.
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self.calls.append(("aexit", (exc_type, exc, tb)))
        if self._raise:
            raise RuntimeError("db down")
        return False


def test_normal_turn_records_without_void():
    mgr = _FakeMgr()
    asyncio.run(_finalize_credit_turn(mgr, None))
    assert mgr.calls == [("aexit", (None, None, None))]


def test_retry_succeeded_true_records_without_void():
    mgr = _FakeMgr()
    asyncio.run(_finalize_credit_turn(mgr, True))
    assert mgr.calls == [("aexit", (None, None, None))]


def test_retry_failed_voids_before_recording():
    mgr = _FakeMgr()
    asyncio.run(_finalize_credit_turn(mgr, False))
    # Void must fire BEFORE __aexit__ so the recorded turn is skipped.
    assert mgr.calls == [
        ("void", "layer4_retry_failed"),
        ("aexit", (None, None, None)),
    ]


def test_orchestrator_error_voids_the_turn():
    # stream_orchestrator reports its own failures as an `error` EVENT and never
    # raises, so "no exception" is not evidence the turn worked. Must void, the
    # same as chat.py's success=False branch.
    mgr = _FakeMgr()
    asyncio.run(_finalize_credit_turn(mgr, None, orchestrator_errored=True))
    assert mgr.calls == [
        ("void", "orchestrator reported failure"),
        ("aexit", (None, None, None)),
    ]


def test_orchestrator_error_outranks_retry_reason():
    # Same precedence as chat.py:190 — an outright failure beats a stalled retry.
    mgr = _FakeMgr()
    asyncio.run(_finalize_credit_turn(mgr, False, orchestrator_errored=True))
    assert ("void", "orchestrator reported failure") in mgr.calls
    assert ("void", "layer4_retry_failed") not in mgr.calls


def test_none_manager_is_noop():
    # No manager (setup failed / credits disabled) — must not raise.
    asyncio.run(_finalize_credit_turn(None, False))


def test_exit_error_is_swallowed():
    mgr = _FakeMgr(raise_on_exit=True)
    # A DB failure while recording must not bubble up and kill the turn.
    asyncio.run(_finalize_credit_turn(mgr, None))
    assert mgr.calls == [("aexit", (None, None, None))]


# --- _complete_turn lifecycle: persist → charge → forward `done` -------------

_DONE = {"type": "chat.done", "content": None}


def _tags(order: list) -> list:
    """Step tags in order. void/aexit/send are logged as tuples; persist and
    postprocess as bare strings — normalise to the leading tag for ordering."""
    return [c[0] if isinstance(c, tuple) else c for c in order]


def _order_mgr(order: list) -> _FakeMgr:
    """A _FakeMgr whose void/aexit append to a shared order log."""
    mgr = _FakeMgr()
    mgr.calls = order  # share the single ordering log
    return mgr


def _run_complete(order, *, mgr, retry_succeeded=None, persist_raises=False,
                  postprocess_raises=False, pending_done=_DONE,
                  orchestrator_errored=False):
    """Drive _complete_turn with the persist/postprocess seams stubbed to record
    into `order`. Returns the list of payloads passed to `send`."""
    sent = []

    async def _fake_persist(db, conversation, final_message, collected_steps):
        order.append("persist")
        if persist_raises:
            raise RuntimeError("db down mid-persist")

    async def _fake_postprocess(*a, **k):
        order.append("postprocess")
        if postprocess_raises:
            raise RuntimeError("title service down")

    async def _send(payload):
        order.append(("send", payload.get("type")))
        sent.append(payload)

    conv = types.SimpleNamespace(id=1, thread_id="t-1")
    user = types.SimpleNamespace(id="u-1")

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(ws, "_persist_turn", _fake_persist)
        mp.setattr(ws, "_postprocess_turn", _fake_postprocess)
        asyncio.run(_complete_turn(
            db=None, conversation=conv, is_new=False, user_message="q",
            final_message="a", collected_steps=[], retry_succeeded=retry_succeeded,
            judge_metadata=None, credit_mgr=mgr, pending_done_event=pending_done,
            send=_send, request_id="r-1", user=user, active_thread_id="t-1",
            orchestrator_errored=orchestrator_errored,
        ))
    return sent


def test_complete_turn_persists_before_charging_before_done():
    order = []
    _run_complete(order, mgr=_order_mgr(order))
    tags = _tags(order)
    # Persist precedes the charge (aexit), which precedes forwarding `done`.
    assert tags[0] == "persist"
    assert tags.index("persist") < tags.index("aexit") < tags.index("send")
    # Post-processing runs last, after `done` is already forwarded.
    assert tags[-1] == "postprocess"


def test_complete_turn_persist_failure_skips_charge_and_done():
    # THE regression: if persistence fails, the pool must NOT be debited and
    # `done` must NOT be forwarded — the exception propagates to the handler,
    # which finalizes with the exception (skipping the charge).
    order = []
    with pytest.raises(RuntimeError):
        _run_complete(order, mgr=_order_mgr(order), persist_raises=True)
    assert "aexit" not in _tags(order)   # never charged
    assert "send" not in _tags(order)    # `done` never forwarded
    assert order == ["persist"]


def test_complete_turn_postprocess_failure_keeps_charge_and_done():
    # A post-processing hiccup after the answer is saved must not undo the
    # charge or error the turn: charge + `done` already happened, exception
    # swallowed (no raise out of _complete_turn).
    order = []
    sent = _run_complete(order, mgr=_order_mgr(order), postprocess_raises=True)
    assert "aexit" in _tags(order)                              # charged
    assert any(p.get("type") == "chat.done" for p in sent)     # done forwarded


def test_complete_turn_retry_failed_voids_before_charge():
    order = []
    _run_complete(order, mgr=_order_mgr(order), retry_succeeded=False)
    tags = _tags(order)
    # Void fires before the charge so the failed turn isn't billed.
    assert tags.index("void") < tags.index("aexit")


def test_complete_turn_orchestrator_error_voids_before_charge():
    order = []
    _run_complete(order, mgr=_order_mgr(order), orchestrator_errored=True)
    tags = _tags(order)
    assert tags.index("void") < tags.index("aexit")
    assert ("void", "orchestrator reported failure") in order


def test_complete_turn_no_pending_done_still_charges():
    # Defensive: a missing `done` event with no reported error still charges —
    # only an explicit orchestrator_errored flag voids (see the test above).
    order = []
    sent = _run_complete(order, mgr=_order_mgr(order), pending_done=None)
    assert "aexit" in _tags(order)
    assert ("void", "orchestrator reported failure") not in order
    assert sent == []  # nothing forwarded


# --- the wiring: does the stream loop actually set the flag? ------------------


def test_handle_chat_send_voids_on_an_orchestrator_error_event(monkeypatch):
    """The regression this pins: stream_orchestrator catches its own exception,
    yields `{"type": "error"}` and stops WITHOUT a `done` (graph.py). Nothing
    raises, so `_handle_chat_send` used to run to a clean __aexit__ and bill the
    user for an error message — while POST /api/chat voided the same failure.

    The helper tests above cover the void decision; only this one proves the
    flag is set where the error event actually arrives.
    """
    from unittest.mock import MagicMock

    conversation = types.SimpleNamespace(id="c-1", thread_id="t-1")
    mgr = _FakeMgr()

    async def _resolve_conv(db, user, thread_id, connection_ids, send, request_id):
        return conversation, False

    async def _build_ctx(**kw):
        return types.SimpleNamespace(
            agent_context="", custom_agents=None, memory_context=None,
            user_skills=None, user_memories_context=None,
            skill_suggestions=None, soul_prompt=None, profile=None,
        )

    async def _stream(*a, **k):
        # Exactly what graph.py yields when the orchestrator blows up.
        yield {"type": "error", "content": "Something went wrong. Please try again."}

    async def _noop(*a, **k):
        return None

    async def _wait_files(*a, **k):
        return True

    async def _resolve_att(*a, **k):
        return None, None

    import backend.agents as agents
    import backend.agents.profile_llm as pl
    import backend.plugins.loader as loader
    import backend.services.heartbeat_context as hb
    import backend.services.token_tracking_service as tts
    import redis as _redis

    monkeypatch.setattr(ws, "_resolve_conversation", _resolve_conv)
    monkeypatch.setattr(hb, "build_orchestrator_context", _build_ctx)
    monkeypatch.setattr(agents, "stream_orchestrator", _stream)
    monkeypatch.setattr(ws, "_wait_for_file_processing", _wait_files)
    monkeypatch.setattr(ws, "_resolve_attachments", _resolve_att)
    monkeypatch.setattr(ws, "_inject_conversation_datasets", _noop)
    monkeypatch.setattr(ws, "_persist_turn", _noop)
    monkeypatch.setattr(ws, "_postprocess_turn", _noop)
    monkeypatch.setattr(ws, "DetachedReadSessionLocal", lambda: MagicMock())
    monkeypatch.setattr(pl, "resolve_published_llm", lambda p: (None, None, None))
    monkeypatch.setattr(loader, "get_loaded_plugins", lambda: {})
    monkeypatch.setattr(_redis, "from_url", lambda *a, **k: MagicMock())
    monkeypatch.setattr(
        ws.ConversationService, "get_conversation_history",
        staticmethod(lambda db, tid, uid: []),
    )
    monkeypatch.setattr(
        ws.ConversationService, "add_message", staticmethod(lambda *a, **k: None)
    )
    monkeypatch.setattr(tts, "CreditContextManager", lambda **kw: mgr)

    class _WS:
        async def send_text(self, _):
            pass

    asyncio.run(ws._handle_chat_send(
        _WS(), types.SimpleNamespace(id="u-1"), "r-1", "t-1", "hello", [],
    ))

    assert ("void", "orchestrator reported failure") in mgr.calls, (
        "websocket billed a turn the orchestrator reported as failed"
    )
