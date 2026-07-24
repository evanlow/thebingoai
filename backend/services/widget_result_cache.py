"""Redis cache for widget refresh results (per-Org flag `widget_result_cache`).

Unfiltered widget data only changes when the dashboard materializes, so keys
embed a per-dashboard generation counter bumped at the end of each successful
`materialize_dashboard` run — cache-until-materialize, exact for unfiltered
reads. Filtered reads get a short TTL instead (they scan live source Parquet,
which moves on pipeline runs). Old-generation entries expire via TTL; no SCAN
cleanup needed.

`data_plane` / `cache` outcomes are stored until the generation bumps.
`source` (live source-DB fallback) results are also stored, but with a short
`widget_cache_ttl_source` window (clamped in `put`) — enough that reopening a
cold, non-migrated dashboard within the window is instant, without pinning stale
source data for long.

Every helper swallows Redis failures and degrades to a miss: the cache must
never break serving.
"""
import hashlib
import json
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_KEY_PREFIX = "widget_cache"
_GEN_PREFIX = "widget_cache_gen"

# served_from values eligible for write-through. `source` is cached too but its
# TTL is clamped short in `put` (see widget_cache_ttl_source).
CACHEABLE_SERVED_FROM = ("data_plane", "cache", "source")


def _client():
    import redis as syncredis
    from backend.config import settings

    return syncredis.from_url(settings.redis_url, decode_responses=True)


def _canonical_filters(filters: Optional[list]) -> str:
    """Order-independent canonical form: equivalent filter sets hash equal."""
    items = sorted(
        json.dumps(f, sort_keys=True, default=str) for f in (filters or [])
    )
    return json.dumps(items)


def build_key(
    scope_kind: str,
    scope_id: Any,
    dashboard_id: int,
    widget_id: str,
    sql: str,
    filters: Optional[list],
    generation: int,
) -> str:
    sql_hash = hashlib.sha256((sql or "").encode()).hexdigest()[:16]
    filters_hash = hashlib.sha256(_canonical_filters(filters).encode()).hexdigest()[:16]
    return (
        f"{_KEY_PREFIX}:{scope_kind}:{scope_id}:{dashboard_id}:{widget_id}"
        f":g{generation}:{sql_hash}:{filters_hash}"
    )


def get_generation(dashboard_id: int) -> int:
    try:
        client = _client()
        try:
            val = client.get(f"{_GEN_PREFIX}:{dashboard_id}")
            return int(val) if val else 0
        finally:
            client.close()
    except Exception:
        logger.debug("widget_result_cache generation read failed", exc_info=True)
        return 0


def bump_generation(dashboard_id: int) -> None:
    """Invalidate all cached entries for a dashboard (called post-materialize)."""
    try:
        client = _client()
        try:
            client.incr(f"{_GEN_PREFIX}:{dashboard_id}")
        finally:
            client.close()
    except Exception:
        logger.warning("widget_result_cache generation bump failed for dashboard %s", dashboard_id, exc_info=True)


def get(key: str) -> Optional[Dict[str, Any]]:
    try:
        client = _client()
        try:
            raw = client.get(key)
            if raw is None:
                return None
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else None
        finally:
            client.close()
    except Exception:
        logger.debug("widget_result_cache read failed", exc_info=True)
        return None


def put(key: str, payload: Dict[str, Any], ttl: int) -> None:
    """Write-through. Oversized payloads are skipped, not truncated."""
    from backend.config import settings

    served_from = payload.get("served_from")
    if served_from not in CACHEABLE_SERVED_FROM:
        return
    # Live source-DB results get a short staleness window regardless of the
    # caller's (filtered/unfiltered) TTL — they aren't generation-exact.
    if served_from == "source":
        ttl = min(ttl, settings.widget_cache_ttl_source)
    try:
        raw = json.dumps(payload, default=str)
        if len(raw) > settings.widget_cache_max_bytes:
            logger.debug("widget_result_cache skip oversized payload (%d bytes) for %s", len(raw), key)
            return
        client = _client()
        try:
            client.setex(key, ttl, raw)
        finally:
            client.close()
    except Exception:
        logger.debug("widget_result_cache write failed", exc_info=True)
