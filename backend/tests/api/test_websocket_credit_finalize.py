"""_finalize_credit_turn — the on-`done` credit close-out.

Covers the ordering/void/idempotency/error-swallow semantics of the money path
that runs before `done` is forwarded to the client. The "runs before send"
placement itself is structural (the call sits in the `done` branch ahead of the
send); here we pin the finalize behaviour it delegates to.
"""
import asyncio

from backend.api.websocket import _finalize_credit_turn


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
