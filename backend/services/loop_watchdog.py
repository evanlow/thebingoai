"""Event-loop stall watchdog.

A heartbeat task on the event loop stamps a timestamp every second; a daemon
thread checks it. When the loop hasn't beaten for `_STALL_AFTER_S`, the thread
logs the loop thread's current stack — naming the exact frame blocking the
loop. This is the black-box recorder for incidents like 2026-07-23, where all
backend pods went silent for 84s and were liveness-killed with no evidence of
*what* was blocking.

Zero external deps, no ptrace/py-spy needed, safe in prod: the thread sleeps
almost always and only reads `sys._current_frames()` during a stall.
"""

import asyncio
import logging
import sys
import threading
import time
import traceback

logger = logging.getLogger(__name__)

_STALL_AFTER_S = 5.0   # loop silent this long = stalled
_CHECK_EVERY_S = 5.0   # watchdog thread wake interval
_LOG_COOLDOWN_S = 15.0  # min gap between stack dumps during one long stall

_heartbeat = time.monotonic()


async def _beat() -> None:
    global _heartbeat
    while True:
        _heartbeat = time.monotonic()
        await asyncio.sleep(1.0)


def _watch(loop_thread_id: int) -> None:
    last_logged = 0.0
    while True:
        time.sleep(_CHECK_EVERY_S)
        stalled_for = time.monotonic() - _heartbeat
        if stalled_for < _STALL_AFTER_S:
            continue
        now = time.monotonic()
        if now - last_logged < _LOG_COOLDOWN_S:
            continue
        last_logged = now
        stack = sys._current_frames().get(loop_thread_id)
        if stack is not None:
            logger.warning(
                "Event loop stalled for %.1fs — loop thread stack:\n%s",
                stalled_for,
                "".join(traceback.format_stack(stack)),
            )


def start() -> None:
    """Start the watchdog. Must be called from the running event loop."""
    asyncio.get_running_loop()
    asyncio.create_task(_beat())
    threading.Thread(
        target=_watch,
        args=(threading.get_ident(),),
        daemon=True,
        name="loop-watchdog",
    ).start()
    logger.info("Event-loop stall watchdog started (threshold %.0fs)", _STALL_AFTER_S)
