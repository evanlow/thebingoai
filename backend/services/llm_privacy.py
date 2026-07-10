"""LLM privacy controls — keep real data values out of LLM-provider prompts.

Gated per-Organization by the ``metadata_only_llm`` feature flag (strict mode,
user-confirmed): when on, the LLM sees schema, column meanings, relationships,
row counts and *derived* stats (avg, null counts, distinct counts) — but never
actual cell values (sample rows, top values, query previews) or the raw extreme
values min/max (the lowest salary in a table is a real person's salary).

User-facing output is unaffected: query results reach the frontend via the
existing side-channel (``store_query_result`` / ``publish_query_result``), which
never passes through the LLM, so stripping the LLM's preview copy costs nothing
the user sees.

NOT gated in v1 (documented intentional exposure): dashboard briefings /
``analyze_dashboard`` widget aggregates, conversation summaries
(``summary_service`` / ``title_service``), and the summarize skill — these carry
user-visible derived output by design. Routing those to a local LLM is the
future path for orgs that need them covered too.

Per-column sensitivity (``glossary[key].sensitive``) is enforced by
``redact_sensitive_columns`` even when the org flag is off — see the semantic
layer.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Sequence

FLAG = "metadata_only_llm"

# Per-column stat keys that are real data values and must not reach the LLM in
# strict mode. avg / null_count / distinct_count / type are derived or
# structural and are kept.
_VALUE_KEYS = ("min", "max", "top_values")

_REDACTED = "[REDACTED]"


# ---------------------------------------------------------------------------
# Flag resolution
# ---------------------------------------------------------------------------

def metadata_only_for_connection(connection: Any) -> bool:
    """True when the connection's Org has ``metadata_only_llm`` enabled.

    A connection with no ``org_id`` (legacy rows) resolves to False — matches the
    existing flag pattern (`data_agent/tools.py`).
    """
    org_id = getattr(connection, "org_id", None)
    if not org_id:
        return False
    from backend.config.feature_flags import enabled
    return enabled(str(org_id), FLAG)


def metadata_only_for_user(db, user_id: Optional[str]) -> bool:
    """True when the user's Org has ``metadata_only_llm`` enabled.

    Used on paths that have a user but no connection (uploaded chat files).
    Missing user or org → False.
    """
    if not user_id:
        return False
    from backend.models.user import User
    org_id = (
        db.query(User.org_id).filter(User.id == user_id).scalar()
    )
    if not org_id:
        return False
    from backend.config.feature_flags import enabled
    return enabled(str(org_id), FLAG)


# ---------------------------------------------------------------------------
# Redaction (pure)
# ---------------------------------------------------------------------------

def strip_profile_values(profile: Dict[str, Any]) -> Dict[str, Any]:
    """Return a copy of a ``profile_table`` result with real values removed.

    Drops per-column ``min``/``max``/``top_values``; keeps ``type``, ``avg``,
    ``null_count``, ``distinct_count``. Non-destructive (input untouched).
    """
    out = dict(profile)
    cols_in = profile.get("columns") or {}
    cols_out: Dict[str, Any] = {}
    for name, stats in cols_in.items():
        if isinstance(stats, dict):
            cols_out[name] = {k: v for k, v in stats.items() if k not in _VALUE_KEYS}
        else:
            cols_out[name] = stats
    out["columns"] = cols_out
    return out


def strip_preview(result: Dict[str, Any]) -> Dict[str, Any]:
    """Return a copy of a query-result dict with the row values withheld.

    Keeps shape (columns, row_count, timings, result_ref); empties ``rows`` and
    adds an explanatory note so the agent describes shape instead of fabricating
    values.
    """
    out = dict(result)
    out["rows"] = []
    out["values_withheld"] = True
    out["note"] = (
        "Row values withheld by org privacy policy; the full result is delivered "
        "to the user via the result reference. Describe the shape and columns; "
        "do not fabricate values."
    )
    return out


def redact_sensitive_columns(
    rows: Sequence[Sequence[Any]],
    columns: Sequence[str],
    sensitive_names: Iterable[str],
) -> List[List[Any]]:
    """Replace values in sensitive columns with ``[REDACTED]``.

    Column matching is case-insensitive against ``sensitive_names`` (bare column
    names). Aliased/derived result columns won't match — a documented limitation;
    the org-wide flag is the complete control, this is best-effort defense.
    """
    sensitive = {s.lower() for s in sensitive_names}
    mask = [c.lower() in sensitive for c in columns]
    if not any(mask):
        return [list(r) for r in rows]
    out: List[List[Any]] = []
    for r in rows:
        out.append([_REDACTED if mask[i] else v for i, v in enumerate(r)])
    return out
