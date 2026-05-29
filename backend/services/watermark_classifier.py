"""Watermark column classifier — picks an incremental cursor column per table.

Two layers:

  * **Deterministic** (`classify_table`): type-first ranked matcher. Filter to
    date/time-typed columns; prefer conventionally-named ones (`updated_at`,
    `created_at`, …) over arbitrary date columns. Never raises. None when no
    date-typed column exists — caller falls back to a full snapshot.

  * **LLM-first batched** (`classify_connection`): one batched structured-output
    call per connection across all tables. Env-driven
    (``WATERMARK_CLASSIFIER_PROVIDER`` + ``WATERMARK_CLASSIFIER_MODEL``); empty
    defaults → deterministic-only (no LLM call). On any error, missing model,
    invalid JSON, or per-table low-confidence response → silently falls back to
    deterministic for that table. Never raises.

The crosscheck plan ("LLM-first batched structured-output classifier per
connection; type-first ranked deterministic matcher as fallback") is satisfied
by `classify_connection`; callers in the create-connection flow should prefer
that entry point, but `classify_table` remains the deterministic primitive used
by both this module and the materializer's sync path.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)


# ── Deterministic matcher ───────────────────────────────────────────────────

# Conventional incremental-cursor column names ranked by preference. First match
# wins among date-typed columns; if none of these names appear, the first
# date-typed column is returned.
_PREFERRED_NAMES: tuple[str, ...] = (
    "updated_at",
    "modified_at",
    "last_modified",
    "created_at",
    "inserted_at",
    "event_time",
    "event_timestamp",
    "event_date",
    "transaction_time",
    "order_date",
    "ts",
    "timestamp",
    "dt",
)

# A column qualifies as date-typed when its SQL type string contains one of
# these tokens (case-insensitive). Covers `DATE`, `DATETIME`, `TIMESTAMP`,
# `TIMESTAMPTZ`, `TIMESTAMP WITHOUT TIME ZONE`, etc.
_DATE_TYPE_TOKENS: tuple[str, ...] = ("timestamp", "datetime", "date", "time")


def _is_date_typed(col: dict) -> bool:
    ctype = (col.get("type") or "").lower()
    return any(tok in ctype for tok in _DATE_TYPE_TOKENS)


def classify_table(columns: list[dict]) -> Optional[str]:
    """Deterministic per-table classifier. None → table has no usable cursor."""
    date_cols = [c for c in columns if _is_date_typed(c)]
    if not date_cols:
        return None

    by_name = {(c.get("name") or "").lower(): c.get("name") for c in date_cols}
    for preferred in _PREFERRED_NAMES:
        if preferred in by_name:
            return by_name[preferred]
    return date_cols[0].get("name")


# ── Batched LLM-first classifier ─────────────────────────────────────────────

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


def _parse_llm_response(text: str) -> dict[str, dict]:
    """Pull the JSON object out of the LLM response, tolerating fence noise.

    Returns ``{table_name: {"column": str|None, "confidence": str}}``. Empty
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
    for entry in obj.get("results") or []:
        name = entry.get("table")
        if not name:
            continue
        out[name] = {
            "column": entry.get("column"),
            "confidence": (entry.get("confidence") or "").lower(),
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
        if not entry or entry.get("confidence") == "low":
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
