"""Timezone-aware cron utilities.

`compute_next_run` evaluates a cron expression in a given IANA timezone and
returns a naive-UTC datetime suitable for persisting in `next_run_at` columns.

Schedule-bearing tables (heartbeat_jobs, dashboards, pipelines) store
`timezone` as an IANA name (e.g. ``Asia/Singapore``). Storage stays UTC;
only the user's intent for *when* the cron fires changes.
"""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from croniter import croniter

__all__ = ["compute_next_run", "is_valid_timezone"]


def compute_next_run(
    cron_expression: str,
    tz_name: str | None,
    *,
    now_utc: datetime | None = None,
) -> datetime:
    """Compute the next firing time of ``cron_expression`` in ``tz_name``.

    Args:
        cron_expression: Standard 5-field cron string.
        tz_name: IANA timezone name (e.g. ``Asia/Singapore``). ``None`` or
            empty falls back to ``UTC`` so legacy rows behave as before.
        now_utc: Override "current time" for tests. Must be tz-aware UTC if
            provided.

    Returns:
        Naive UTC datetime — matches existing `next_run_at` column shape.
    """
    tz = ZoneInfo(tz_name) if tz_name else ZoneInfo("UTC")

    if now_utc is None:
        now_utc = datetime.now(timezone.utc)
    elif now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)

    now_local = now_utc.astimezone(tz)
    next_local = croniter(cron_expression, now_local).get_next(datetime)
    return next_local.astimezone(timezone.utc).replace(tzinfo=None)


def is_valid_timezone(tz_name: str) -> bool:
    """Return True if ``tz_name`` resolves to a known IANA zone."""
    if not tz_name:
        return False
    try:
        ZoneInfo(tz_name)
        return True
    except (ZoneInfoNotFoundError, ValueError):
        return False
