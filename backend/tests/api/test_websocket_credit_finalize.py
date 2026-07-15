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
                  postprocess_raises=False, pending_done=_DONE):
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


def test_complete_turn_no_pending_done_still_charges():
    # Defensive: even with no buffered done event, the charge still lands.
    order = []
    sent = _run_complete(order, mgr=_order_mgr(order), pending_done=None)
    assert "aexit" in _tags(order)
    assert sent == []  # nothing forwarded
