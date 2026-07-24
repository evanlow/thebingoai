"""Unit tests for the Redis widget result cache (per-Org `widget_result_cache`).

Redis is replaced with an in-memory fake; the cache module's contract is what
matters: key derivation (filter canonicalization, sql/gen sensitivity),
generation-counter invalidation, write-through rules (no source results, no
oversized payloads), and the widget_data hook helpers.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from backend.services import widget_result_cache as wrc
from backend.api import widget_data as wd


class FakeRedis:
    def __init__(self, store: dict, ttls: dict):
        self.store = store
        self.ttls = ttls

    def get(self, key):
        return self.store.get(key)

    def setex(self, key, ttl, value):
        self.store[key] = value
        self.ttls[key] = ttl

    def incr(self, key):
        self.store[key] = str(int(self.store.get(key) or 0) + 1)
        return int(self.store[key])

    def close(self):
        pass


@pytest.fixture()
def fake_redis(monkeypatch):
    store: dict = {}
    ttls: dict = {}
    monkeypatch.setattr(wrc, "_client", lambda: FakeRedis(store, ttls))
    return SimpleNamespace(store=store, ttls=ttls)


# ── Key derivation ───────────────────────────────────────────────────────────

def test_same_filters_different_order_same_key():
    f1 = [{"column": "a", "op": "eq", "value": 1}, {"column": "b", "op": "eq", "value": 2}]
    f2 = [{"column": "b", "op": "eq", "value": 2}, {"column": "a", "op": "eq", "value": 1}]
    k1 = wrc.build_key("org", "o1", 1, "w1", "conn1", "SELECT 1", f1, 0)
    k2 = wrc.build_key("org", "o1", 1, "w1", "conn1", "SELECT 1", f2, 0)
    assert k1 == k2


def test_sql_change_changes_key():
    k1 = wrc.build_key("org", "o1", 1, "w1", "conn1", "SELECT 1", None, 0)
    k2 = wrc.build_key("org", "o1", 1, "w1", "conn1", "SELECT 2", None, 0)
    assert k1 != k2


def test_generation_bump_changes_key():
    k1 = wrc.build_key("org", "o1", 1, "w1", "conn1", "SELECT 1", None, 0)
    k2 = wrc.build_key("org", "o1", 1, "w1", "conn1", "SELECT 1", None, 1)
    assert k1 != k2


def test_scope_isolation_in_key():
    k1 = wrc.build_key("org", "o1", 1, "w1", "conn1", "SELECT 1", None, 0)
    k2 = wrc.build_key("org", "o2", 1, "w1", "conn1", "SELECT 1", None, 0)
    assert k1 != k2


def test_connection_id_changes_key():
    # Same SQL on a different connection must not collide — source results are
    # cached and widget edits don't bump the generation.
    k1 = wrc.build_key("org", "o1", 1, "w1", "conn1", "SELECT 1", None, 0)
    k2 = wrc.build_key("org", "o1", 1, "w1", "conn2", "SELECT 1", None, 0)
    assert k1 != k2


# ── Generation counter ───────────────────────────────────────────────────────

def test_bump_generation_increments(fake_redis):
    assert wrc.get_generation(7) == 0
    wrc.bump_generation(7)
    assert wrc.get_generation(7) == 1
    wrc.bump_generation(7)
    assert wrc.get_generation(7) == 2


def test_generation_read_failure_degrades_to_zero(monkeypatch):
    def boom():
        raise ConnectionError("redis down")
    monkeypatch.setattr(wrc, "_client", boom)
    assert wrc.get_generation(7) == 0


# ── put / get ────────────────────────────────────────────────────────────────

def _payload(served_from="data_plane", rows=None):
    return {
        "columns": ["a"],
        "rows": rows if rows is not None else [[1]],
        "row_count": 1,
        "truncated": False,
        "served_from": served_from,
        "cached_at": "2026-06-11T00:00:00+00:00",
    }


def test_put_get_roundtrip(fake_redis):
    key = wrc.build_key("org", "o1", 1, "w1", "conn1", "SELECT 1", None, 0)
    wrc.put(key, _payload(), ttl=3600)
    hit = wrc.get(key)
    assert hit is not None
    assert hit["rows"] == [[1]]
    assert hit["served_from"] == "data_plane"
    assert fake_redis.ttls[key] == 3600


def test_source_results_never_cached(fake_redis):
    key = wrc.build_key("org", "o1", 1, "w1", "conn1", "SELECT 1", None, 0)
    wrc.put(key, _payload(served_from="source"), ttl=3600)
    assert wrc.get(key) is None


def test_oversized_payload_skipped(fake_redis, monkeypatch):
    from backend.config import settings
    monkeypatch.setattr(settings, "widget_cache_max_bytes", 64)
    key = wrc.build_key("org", "o1", 1, "w1", "conn1", "SELECT 1", None, 0)
    wrc.put(key, _payload(rows=[["x" * 500]]), ttl=3600)
    assert wrc.get(key) is None


def test_redis_failure_degrades_to_miss(monkeypatch):
    def boom():
        raise ConnectionError("redis down")
    monkeypatch.setattr(wrc, "_client", boom)
    key = wrc.build_key("org", "o1", 1, "w1", "conn1", "SELECT 1", None, 0)
    wrc.put(key, _payload(), ttl=60)   # must not raise
    assert wrc.get(key) is None


# ── widget_data hook helpers ─────────────────────────────────────────────────

def test_cache_key_none_when_flag_off(monkeypatch):
    monkeypatch.setattr(wd, "_widget_cache_enabled", lambda org_id: False)
    key, ttl = wd._widget_cache_key(1, "w1", "SELECT 1", None, "org-1", "u-1")
    assert key is None and ttl is None


def test_cache_key_none_without_widget_identity(monkeypatch):
    monkeypatch.setattr(wd, "_widget_cache_enabled", lambda org_id: True)
    assert wd._widget_cache_key(None, "w1", "SELECT 1", None, "org-1", "u-1") == (None, None)
    assert wd._widget_cache_key(1, None, "SELECT 1", None, "org-1", "u-1") == (None, None)


def test_cache_key_ttl_filtered_vs_unfiltered(monkeypatch, fake_redis):
    from backend.config import settings
    monkeypatch.setattr(wd, "_widget_cache_enabled", lambda org_id: True)
    _, ttl_unfiltered = wd._widget_cache_key(1, "w1", "SELECT 1", None, "org-1", "u-1")
    _, ttl_filtered = wd._widget_cache_key(
        1, "w1", "SELECT 1", [{"column": "a", "op": "eq", "value": 1}], "org-1", "u-1",
    )
    assert ttl_unfiltered == settings.widget_cache_ttl_unfiltered
    assert ttl_filtered == settings.widget_cache_ttl_filtered


def test_lookup_replays_served_from_and_transforms_with_current_mapping(fake_redis, monkeypatch):
    monkeypatch.setattr(wd, "transform_widget_data", lambda result, mapping: {"rows": result.rows, "m": mapping})
    key = wrc.build_key("org", "o1", 1, "w1", "conn1", "SELECT 1", None, 0)
    wrc.put(key, _payload(), ttl=60)

    resp = wd._widget_cache_lookup(key, {"type": "table"})

    assert resp is not None
    assert resp.served_from == "data_plane"
    assert resp.config == {"rows": [[1]], "m": {"type": "table"}}
    assert resp.refreshed_at == "2026-06-11T00:00:00+00:00"  # honest staleness


def test_store_writes_through_from_response(fake_redis):
    key = wrc.build_key("org", "o1", 1, "w1", "conn1", "SELECT 1", None, 0)
    resp = SimpleNamespace(
        source_columns=["a"], source_rows=[[2]], row_count=1, truncated=False,
        served_from="cache", refreshed_at="t",
    )
    wd._widget_cache_store(key, 60, resp)
    hit = wrc.get(key)
    assert hit is not None and hit["rows"] == [[2]] and hit["served_from"] == "cache"


def test_store_noops_without_key(fake_redis):
    wd._widget_cache_store(None, 60, SimpleNamespace())  # must not raise
    assert fake_redis.store == {}
