"""Watermark column classifier — picks an incremental cursor column per table.

Three public entry points, sharing one deterministic ranker and one batched
LLM call. Use the one that matches the context you have:

  * **`classify_table(columns)`** — deterministic ranked matcher. No I/O, no
    LLM, never raises. Scores candidates by (a) type tier (timestamptz >
    timestamp > datetime > date > integer) and (b) name-token rank
    (`updated_*` > `created_*` > event/business dates > `*_at`/`*_ts` …),
    rejecting columns that are neither temporal nor named like a watermark.
    Returns None when no candidate qualifies → caller falls back to a full
    snapshot. Used by the materializer's sync (connect-time) path.

  * **`classify_connection(tables, *, provider, model)`** — LLM-first batched.
    One structured-output call per connection across all tables, env-driven
    (``WATERMARK_CLASSIFIER_PROVIDER`` + ``WATERMARK_CLASSIFIER_MODEL``); empty
    defaults → deterministic-only (no LLM call). Per-table fallback to
    `classify_table` on error / unparseable response / low confidence. Never
    raises. Used by the async refinement task (`tasks/watermark_tasks.py`).

  * **`resolve_watermark(reg, connector, tables, columns_by_table)`** —
    connector-aware. Per table: (1) source-side native partition key
    (postgres / mysql), (2) the batched LLM-or-deterministic pick from
    `classify_connection`. Used by the materializer's main path and the
    `/redetect-watermark` endpoint, which have an open connector.

`reg` is the connector's `ConnectorRegistration` (used for the type-specific
partition-key helper); `connector` is an open connector instance;
`columns_by_table` is `{table: [{name, type, primary_key?}, ...]}`.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ── Deterministic ranked matcher ─────────────────────────────────────────────

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
    ("created_at", "created_on", "inserted_at", "ingested_at", "event_time", "event_timestamp"),
    ("event_date", "event_ts", "occurred_at", "happened_at", "transaction_time", "order_date"),
    # Bare conventional names (low priority — generic).
    ("ts", "timestamp", "dt", "datetime"),
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
    name tier. This filters out unrelated string / numeric columns that
    happen to be named `*_id`, etc.
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


def classify_table(columns: list[dict]) -> Optional[str]:
    """Deterministic per-table classifier. None → table has no usable cursor."""
    return _deterministic_pick(columns)


# ── Source-side partition key ────────────────────────────────────────────────

def _connector_partition_key(reg: Any, connector: Any, table: str) -> Optional[str]:
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


# ── Batched LLM classifier ───────────────────────────────────────────────────

_SYSTEM_PROMPT = (
    "You are a data-engineering assistant. For each table you must pick the "
    "single best column to use as an incremental ingestion watermark (the "
    "column that monotonically advances as rows are inserted or updated, so a "
    "pipeline can pull only new/changed rows on each run). Prefer "
    "last-modified timestamps over creation timestamps; prefer creation "
    "timestamps over event/business dates; only pick a numeric ID column if "
    "no date/time column exists and the ID is clearly monotonic. Return null "
    "for a table when no column is a safe watermark."
)

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def _build_user_prompt(tables: dict[str, list[dict]]) -> str:
    """Render the per-connection table schema as a compact JSON payload."""
    payload = {
        "tables": [
            {
                "name": table,
                "columns": [
                    {"name": c.get("name"), "type": c.get("type")}
                    for c in cols
                ],
            }
            for table, cols in tables.items()
        ]
    }
    return (
        "Pick one watermark column per table. Respond with **only** a JSON "
        "object of the form "
        '{"results": [{"table": "<name>", "column": "<col_or_null>", '
        '"confidence": "high|medium|low"}, ...]}. '
        "No prose, no markdown fences.\n\n"
        f"Schema:\n{json.dumps(payload, indent=2)}"
    )


def _is_low_confidence(conf: Any) -> bool:
    """Confidence may be a string ('high|medium|low') or a float (0.0-1.0)."""
    if isinstance(conf, str):
        return conf.lower() == "low"
    if isinstance(conf, (int, float)):
        return conf < 0.6
    return False  # unknown → trust the column


def _parse_llm_response(text: str) -> dict[str, dict]:
    """Pull the JSON object out of the LLM response, tolerating fence noise.

    Accepts both the ``{"results": [...]}`` and ``{"picks": [...]}`` envelopes.
    Returns ``{table_name: {"column": str|None, "confidence": Any}}``. Empty
    dict on parse failure — caller falls back to deterministic per-table.
    """
    if not text:
        return {}
    match = _JSON_RE.search(text)
    if not match:
        return {}
    try:
        obj = json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}
    out: dict[str, dict] = {}
    for entry in (obj.get("results") or obj.get("picks") or []):
        if not isinstance(entry, dict):
            continue
        name = entry.get("table")
        if not name:
            continue
        out[name] = {
            "column": entry.get("column"),
            "confidence": entry.get("confidence"),
        }
    return out


async def _call_llm(prompt: str, provider_name: str, model: str) -> str:
    """Run a single chat call. Caller wraps any exception."""
    from backend.llm.factory import get_provider

    provider = get_provider(provider_name, model=model)
    return await provider.chat(
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.0,
        max_tokens=2000,
    )


def classify_connection(
    tables: dict[str, list[dict]],
    *,
    provider: Optional[str] = None,
    model: Optional[str] = None,
) -> dict[str, Optional[str]]:
    """Classify watermarks for every table on a connection in one batched call.

    Args:
      tables: mapping ``{table_name: [{"name": str, "type": str, ...}, ...]}``.
      provider: optional override; falls back to ``WATERMARK_CLASSIFIER_PROVIDER``
        env. Empty/None disables LLM and returns deterministic results.
      model: optional override; falls back to ``WATERMARK_CLASSIFIER_MODEL``.

    Returns: ``{table_name: column_name | None}``. Per-table fallback to the
    deterministic matcher when the LLM call fails, response is unparseable, or
    confidence for that table is "low".
    """
    deterministic = {t: classify_table(cols) for t, cols in tables.items()}

    if not tables:
        return deterministic

    from backend.config import settings

    provider = provider or getattr(settings, "watermark_classifier_provider", "") or ""
    model = model or getattr(settings, "watermark_classifier_model", "") or ""
    if not provider or not model:
        return deterministic

    try:
        raw = asyncio.run(_call_llm(_build_user_prompt(tables), provider, model))
    except Exception as exc:
        logger.warning(
            "watermark_classifier: LLM call failed (%s) — using deterministic fallback",
            exc,
        )
        return deterministic

    parsed = _parse_llm_response(raw)
    if not parsed:
        logger.warning(
            "watermark_classifier: unparseable LLM response — using deterministic fallback"
        )
        return deterministic

    final: dict[str, Optional[str]] = {}
    for table, cols in tables.items():
        entry = parsed.get(table)
        if not entry or _is_low_confidence(entry.get("confidence")):
            final[table] = deterministic[table]
            continue
        col = entry.get("column")
        valid_names = {c.get("name") for c in cols}
        if col in valid_names:
            final[table] = col
        else:
            # Hallucinated column → fall back to deterministic for this table.
            final[table] = deterministic[table]
    return final


def resolve_watermark(
    reg: Any,
    connector: Any,
    tables: list[str],
    columns_by_table: dict[str, list[dict]],
) -> dict[str, Optional[str]]:
    """Return `{table: cursor_col | None}` for each table (connector-aware).

    Priority per table:
      1. Source-side native partition key (postgres / mysql) — cheap and
         authoritative.
      2. The batched LLM-or-deterministic pick from `classify_connection`
         (LLM when configured, deterministic matcher otherwise / on fallback).
    """
    out: dict[str, Optional[str]] = {}

    # Step 1: native partition keys.
    for t in tables:
        out[t] = _connector_partition_key(reg, connector, t)

    # Step 2: classify everything still unresolved (LLM-first, deterministic
    # fallback already baked into classify_connection).
    unresolved = [t for t, v in out.items() if v is None]
    if unresolved:
        picks = classify_connection({t: columns_by_table.get(t) or [] for t in unresolved})
        for t, col in picks.items():
            out[t] = col

    return out
