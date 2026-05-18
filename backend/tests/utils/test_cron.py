"""Tests for backend.utils.cron.compute_next_run."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import pytest

from backend.utils.cron import compute_next_run, is_valid_timezone


def _utc(year, month, day, hour=0, minute=0):
    return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)


def test_daily_9am_singapore_returns_01_utc():
    """`0 9 * * *` in Asia/Singapore (UTC+8) → 01:00 UTC."""
    now = _utc(2026, 5, 18, 6, 0)  # 14:00 SGT — already past 09:00 SGT today
    result = compute_next_run("0 9 * * *", "Asia/Singapore", now_utc=now)
    # Next 9 AM SGT = 2026-05-19 09:00 SGT = 2026-05-19 01:00 UTC
    assert result == datetime(2026, 5, 19, 1, 0)


def test_daily_9am_utc_unchanged():
    """`0 9 * * *` in UTC → 09:00 UTC (matches legacy behavior)."""
    now = _utc(2026, 5, 18, 6, 0)
    result = compute_next_run("0 9 * * *", "UTC", now_utc=now)
    assert result == datetime(2026, 5, 18, 9, 0)


def test_none_tz_falls_back_to_utc():
    """`tz_name=None` must behave identically to ``UTC``."""
    now = _utc(2026, 5, 18, 6, 0)
    assert compute_next_run("0 9 * * *", None, now_utc=now) == datetime(2026, 5, 18, 9, 0)
    assert compute_next_run("0 9 * * *", "", now_utc=now) == datetime(2026, 5, 18, 9, 0)


def test_dst_spring_forward_new_york():
    """Across 2026-03-08 DST start in America/New_York the cron still anchors to 09:00 local.

    Before DST: NY = UTC-5; after DST: NY = UTC-4.
    """
    # 2026-03-08 06:00 UTC = 2026-03-08 01:00 EST (DST starts at 02:00 → 03:00 EDT)
    now = _utc(2026, 3, 8, 6, 0)
    result = compute_next_run("0 9 * * *", "America/New_York", now_utc=now)
    # 2026-03-08 09:00 EDT (UTC-4) = 13:00 UTC
    assert result == datetime(2026, 3, 8, 13, 0)


def test_minutely_interval_tz_invariant():
    """`*/15 * * * *` should produce the same UTC instant regardless of tz."""
    now = _utc(2026, 5, 18, 6, 7)
    utc_result = compute_next_run("*/15 * * * *", "UTC", now_utc=now)
    sgt_result = compute_next_run("*/15 * * * *", "Asia/Singapore", now_utc=now)
    assert utc_result == sgt_result == datetime(2026, 5, 18, 6, 15)


def test_invalid_timezone_raises():
    with pytest.raises(ZoneInfoNotFoundError):
        compute_next_run("0 9 * * *", "Not/A_Zone", now_utc=_utc(2026, 5, 18))


def test_naive_now_utc_treated_as_utc():
    """Caller passing naive datetime must not silently drift."""
    naive = datetime(2026, 5, 18, 6, 0)
    aware = _utc(2026, 5, 18, 6, 0)
    assert compute_next_run("0 9 * * *", "Asia/Singapore", now_utc=naive) == \
        compute_next_run("0 9 * * *", "Asia/Singapore", now_utc=aware)


def test_is_valid_timezone():
    assert is_valid_timezone("UTC")
    assert is_valid_timezone("Asia/Singapore")
    assert is_valid_timezone("America/New_York")
    assert not is_valid_timezone("Atlantis/Lemuria")
    assert not is_valid_timezone("")
