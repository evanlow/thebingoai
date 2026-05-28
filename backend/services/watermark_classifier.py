"""Resolve the best incremental-cursor column for each table on a connection.

Used by `services.template_materializer._build_sql_pipeline_templates` (and
the override / re-detect endpoints in Phase 3) to decide which column drives
dlt's `sources.incremental` for postgres / mysql tables.

Two layers:

1. **Deterministic ranked matcher** — always runs. Scores every candidate
   column by (a) type tier (timestamptz > timestamp > date > integer) and
   (b) name-token rank (`updated_*` > `modified_*` > `created_*` >
   `inserted_*` > `*_at` > `*_ts`). Falls back to None when no candidate
   clears the minimum bar.

2. **LLM batched classifier** — opt-in via `settings.watermark_classifier_model`.
   One structured-output call per connection with `{table: [columns]}` →
   `{table: {column, confidence}}`. On HTTP error / low confidence we return
   the deterministic pick for that table.

Public API:

    resolve_watermark(reg, connector, tables, columns_by_table)
        -> dict[str, str | None]

`reg` is the connector's `ConnectorRegistration` (used for type-specific
helpers — postgres `detect_partition_key`, mysql ditto); `connector` is an
open connector instance; `tables` is the list of source tables;
`columns_by_table` is `{table: [{name, type, primary_key?}, ...]}`.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


# Type / name tiers. Earlier in the tuple = higher rank.
_TYPE_TIERS: tuple[tuple[str, ...], ...] = (
    ("timestamptz", "timestamp with time zone"),
    ("timestamp",),
    ("datetime",),
    ("date",),
    # Integers rank below all temporal types — only useful when the source
    # has a monotonically-increasing surrogate id and no date column.
    ("bigint", "integer", "int", "serial"),
)

_NAME_TIERS: tuple[tuple[str, ...], ...] = (
    ("updated_at", "updated_on", "modified_at", "modified_on", "last_modified"),
    ("created_at", "created_on", "inserted_at", "ingested_at", "event_time"),
    ("event_date", "event_ts", "occurred_at", "happened_at"),
    # Suffix matches handled separately below.
)

_NAME_SUFFIX_TIERS: tuple[str, ...] = ("_at", "_ts", "_date", "_time")


def _type_tier(ctype: str) -> int:
    ct = (ctype or "").lower()
    for i, tier in enumerate(_TYPE_TIERS):
        if any(tok in ct for tok in tier):
            return i
    return len(_TYPE_TIERS)  # worst


def _name_tier(name: str) -> int:
    n = (name or "").lower()
    for i, tier in enumerate(_NAME_TIERS):
        if n in tier:
            return i
    for i, suffix in enumerate(_NAME_SUFFIX_TIERS):
        if n.endswith(suffix):
            return len(_NAME_TIERS) + i
    return len(_NAME_TIERS) + len(_NAME_SUFFIX_TIERS)  # worst


def _deterministic_pick(columns: list[dict]) -> Optional[str]:
    """Pick the best column or return None.

    A candidate must score within the temporal type tiers (index <
    len(_TYPE_TIERS) - 1, i.e. NOT the integer-only fallback) OR match a
    high-priority name tier. This filters out unrelated string / numeric
    columns that happen to be named `*_id`, etc.
    """
    best: Optional[tuple[int, int, int, str]] = None  # (type_tier, name_tier, source_order, name)
    for idx, col in enumerate(columns or []):
        name = col.get("name") or ""
        if not name:
            continue
        ctype = col.get("type") or ""
        t_tier = _type_tier(ctype)
        n_tier = _name_tier(name)
        # Reject columns that are neither temporal nor named like a watermark.
        if t_tier >= len(_TYPE_TIERS) - 1 and n_tier >= len(_NAME_TIERS) + len(_NAME_SUFFIX_TIERS):
            continue
        key = (t_tier, n_tier, idx, name)
        if best is None or key < best:
            best = key
    return best[3] if best else None


def _connector_partition_key(reg, connector, table: str) -> Optional[str]:
    """Source-side partition-key helper (postgres / mysql native partitions)."""
    type_id = (getattr(reg, "type_id", "") or "").lower()
    try:
        if type_id == "postgres":
            from backend.connectors.postgres import detect_partition_key as _pg
            return _pg(connector, "public", table)
        if type_id == "mysql":
            from backend.connectors.mysql import detect_partition_key as _my
            return _my(connector, "", table)
    except Exception:
        logger.debug("partition-key helper failed for %s/%s", type_id, table, exc_info=True)
    return None


def _llm_classify(
    tables: list[str],
    columns_by_table: dict[str, list[dict]],
    model: str,
    provider: str,
) -> dict[str, Optional[str]]:
    """Batched single-call LLM watermark classifier. Returns {} on any error."""
    try:
        from backend.llm.factory import get_provider
    except Exception:
        logger.debug("LLM factory unavailable; skipping watermark classifier", exc_info=True)
        return {}

    # Compact JSON payload — column names + types only.
    schema = {
        t: [{"name": c.get("name"), "type": c.get("type")} for c in (columns_by_table.get(t) or [])]
        for t in tables
    }

    system = (
        "You pick the best column for incremental data ingestion. The cursor "
        "column must (a) monotonically increase as new rows arrive and "
        "(b) be a timestamp, date, or auto-increment id. Prefer 'updated_at' "
        "> 'modified_at' > 'created_at' > integer surrogate ids. Output "
        "STRICT JSON: {\"picks\": [{\"table\": \"name\", \"column\": \"col\", "
        "\"confidence\": 0.0-1.0}, ...]}. Use null for `column` when no "
        "suitable cursor exists. Set confidence < 0.6 when uncertain."
    )
    import json as _json
    user = "Tables:\n" + _json.dumps(schema, indent=2, default=str)

    try:
        provider_obj = get_provider(provider or None)
        resp = provider_obj.chat(  # type: ignore[attr-defined]
            messages=[{"role": "user", "content": user}],
            system=system,
            model=model or None,
            response_format={"type": "json_object"},
        )
    except Exception:
        logger.warning("Watermark LLM call failed; falling back to deterministic", exc_info=True)
        return {}

    try:
        parsed = _json.loads(resp if isinstance(resp, str) else (resp.get("content") or "{}"))
        picks = parsed.get("picks") or []
    except Exception:
        logger.warning("Watermark LLM returned unparseable JSON; falling back", exc_info=True)
        return {}

    result: dict[str, Optional[str]] = {}
    for entry in picks:
        if not isinstance(entry, dict):
            continue
        tbl = entry.get("table")
        col = entry.get("column")
        conf = entry.get("confidence") or 0.0
        if tbl in tables and isinstance(conf, (int, float)) and conf >= 0.6:
            result[tbl] = col if isinstance(col, str) else None
    return result


def resolve_watermark(
    reg: Any,
    connector: Any,
    tables: list[str],
    columns_by_table: dict[str, list[dict]],
) -> dict[str, Optional[str]]:
    """Return `{table: cursor_col | None}` for each table.

    Priority per table:
      1. Source-side native partition key (postgres / mysql).
      2. LLM pick if `settings.watermark_classifier_model` is set AND the LLM
         returns a high-confidence column.
      3. Deterministic ranked matcher.
    """
    from backend.config import settings

    out: dict[str, Optional[str]] = {}

    # Step 1: native partition keys (cheap and authoritative — keep these).
    for t in tables:
        out[t] = _connector_partition_key(reg, connector, t)

    # Step 2: LLM batched pick for everything still unresolved.
    unresolved = [t for t, v in out.items() if v is None]
    if unresolved and settings.watermark_classifier_model:
        llm = _llm_classify(
            unresolved,
            {t: columns_by_table.get(t) or [] for t in unresolved},
            settings.watermark_classifier_model,
            settings.watermark_classifier_provider,
        )
        for t, col in llm.items():
            if col:
                out[t] = col

    # Step 3: deterministic fallback for anything the LLM skipped.
    for t in tables:
        if out.get(t) is None:
            out[t] = _deterministic_pick(columns_by_table.get(t) or [])

    return out
