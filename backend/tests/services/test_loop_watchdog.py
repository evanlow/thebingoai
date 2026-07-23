"""Watchdog must dump the loop thread's stack when the event loop is blocked."""

import asyncio
import logging
import time

from backend.services import loop_watchdog


def test_blocked_loop_triggers_stack_dump(monkeypatch, caplog):
    monkeypatch.setattr(loop_watchdog, "_STALL_AFTER_S", 0.3)
    monkeypatch.setattr(loop_watchdog, "_CHECK_EVERY_S", 0.1)
    monkeypatch.setattr(loop_watchdog, "_LOG_COOLDOWN_S", 0.0)

    async def main():
        loop_watchdog.start()
        await asyncio.sleep(0.2)  # let the heartbeat task run once
        time.sleep(1.0)  # block the loop — this frame should appear in the dump

    with caplog.at_level(logging.WARNING, logger="backend.services.loop_watchdog"):
        asyncio.run(main())

    stall_logs = [r for r in caplog.records if "Event loop stalled" in r.getMessage()]
    assert stall_logs, "expected a stall warning while the loop was blocked"
    assert "time.sleep" in stall_logs[0].getMessage() or "main" in stall_logs[0].getMessage()


def test_quiet_loop_logs_nothing(monkeypatch, caplog):
    monkeypatch.setattr(loop_watchdog, "_STALL_AFTER_S", 0.5)
    monkeypatch.setattr(loop_watchdog, "_CHECK_EVERY_S", 0.1)

    async def main():
        loop_watchdog.start()
        await asyncio.sleep(0.4)  # responsive loop, heartbeat keeps beating

    with caplog.at_level(logging.WARNING, logger="backend.services.loop_watchdog"):
        asyncio.run(main())

    assert not [r for r in caplog.records if "Event loop stalled" in r.getMessage()]
