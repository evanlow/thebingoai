"""Deterministic layout normalizer for agent-generated dashboard widgets.

The dashboard agent decides widget positions on a 12-column grid, but LLM
output often leaves rows underfilled (e.g. a lone w=8 chart with 4 empty
columns). This module post-processes the widget list so every row packs the
full grid width, overlaps are resolved, and vertical gaps are compacted.

Pure functions — no DB, no LLM, no side effects beyond mutating the
`position` dicts in the list passed in. Idempotent: a well-formed layout
passes through unchanged. Must never raise — a failure here would block
dashboard creation, and any layout is better than no dashboard.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

GRID_COLUMNS = 12

# Width bounds per widget type, aligned with frontend WIDGET_DEFAULTS
# (frontend/types/dashboard.ts). default_w/default_h used when sanitizing
# garbage values.
_TYPE_CONSTRAINTS: dict[str, dict[str, int]] = {
    "kpi": {"min_w": 2, "max_w": 6, "default_w": 3, "default_h": 2},
    "chart": {"min_w": 3, "max_w": 12, "default_w": 6, "default_h": 5},
    "table": {"min_w": 4, "max_w": 12, "default_w": 12, "default_h": 5},
    "pivot_table": {"min_w": 4, "max_w": 12, "default_w": 8, "default_h": 5},
    "text": {"min_w": 2, "max_w": 12, "default_w": 12, "default_h": 1},
    "filter": {"min_w": 4, "max_w": 12, "default_w": 12, "default_h": 2},
}
_FALLBACK_CONSTRAINTS = {"min_w": 2, "max_w": 12, "default_w": 6, "default_h": 4}

# Pie/doughnut charts are unreadable at full width — frontend guidance caps
# them at half the grid.
_ROUND_CHART_MAX_W = 6


def _constraints_for(widget: dict) -> dict[str, int]:
    wtype = (widget.get("widget") or {}).get("type")
    constraints = dict(_TYPE_CONSTRAINTS.get(wtype, _FALLBACK_CONSTRAINTS))
    if wtype == "chart":
        chart_type = ((widget.get("widget") or {}).get("config") or {}).get("type")
        if chart_type in ("pie", "doughnut"):
            constraints["max_w"] = _ROUND_CHART_MAX_W
    return constraints


def _coerce_int(value, default: int) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return default
    return n if n >= 0 else default


def _sanitize(widgets: list[dict]) -> None:
    """Coerce x/y/w/h to sane ints in place; clamp to grid and type bounds."""
    for w in widgets:
        pos = w.get("position")
        if not isinstance(pos, dict):
            pos = {}
            w["position"] = pos
        c = _constraints_for(w)
        width = _coerce_int(pos.get("w"), c["default_w"])
        width = max(c["min_w"], min(width if width > 0 else c["default_w"], c["max_w"], GRID_COLUMNS))
        height = _coerce_int(pos.get("h"), c["default_h"])
        height = max(1, height if height > 0 else c["default_h"])
        x = _coerce_int(pos.get("x"), 0)
        x = max(0, min(x, GRID_COLUMNS - width))
        y = _coerce_int(pos.get("y"), 0)
        pos["x"], pos["y"], pos["w"], pos["h"] = x, y, width, height


def _intersects(a: dict, b: dict) -> bool:
    return (
        a["x"] < b["x"] + b["w"]
        and b["x"] < a["x"] + a["w"]
        and a["y"] < b["y"] + b["h"]
        and b["y"] < a["y"] + a["h"]
    )


def _resolve_overlaps(widgets: list[dict]) -> None:
    """Push overlapping widgets down, GridStack float:false style.

    Iterates in reading order (y, x, original index — stable) and moves each
    widget below any already-placed widget it collides with.
    """
    order = sorted(range(len(widgets)), key=lambda i: (widgets[i]["position"]["y"], widgets[i]["position"]["x"], i))
    placed: list[dict] = []
    for i in order:
        pos = widgets[i]["position"]
        moved = True
        while moved:
            moved = False
            for other in placed:
                if _intersects(pos, other):
                    pos["y"] = other["y"] + other["h"]
                    moved = True
        placed.append(pos)


def _detect_bands(widgets: list[dict]) -> list[list[dict]]:
    """Group widgets into horizontal bands of transitively overlapping y-intervals."""
    items = sorted(widgets, key=lambda w: (w["position"]["y"], w["position"]["x"]))
    bands: list[list[dict]] = []
    band: list[dict] = []
    band_bottom = -1
    for w in items:
        pos = w["position"]
        if band and pos["y"] >= band_bottom:
            bands.append(band)
            band = []
            band_bottom = -1
        band.append(w)
        band_bottom = max(band_bottom, pos["y"] + pos["h"])
    if band:
        bands.append(band)
    return bands


def _normalize_band_widths(band: list[dict]) -> None:
    """Widen a uniform band (same y and h) so widths sum to GRID_COLUMNS.

    Deficit is distributed proportionally to current widths (largest-remainder
    rounding), respecting each widget's max width. Mixed-height bands are left
    alone — they may be intentional mosaics.
    """
    first = band[0]["position"]
    if any(w["position"]["y"] != first["y"] or w["position"]["h"] != first["h"] for w in band):
        return

    band.sort(key=lambda w: w["position"]["x"])
    total = sum(w["position"]["w"] for w in band)
    if total < GRID_COLUMNS:
        deficit = GRID_COLUMNS - total
        maxes = [min(_constraints_for(w)["max_w"], GRID_COLUMNS) for w in band]
        # Proportional shares with largest-remainder rounding.
        shares = [deficit * w["position"]["w"] / total for w in band]
        extras = [int(s) for s in shares]
        remainder = deficit - sum(extras)
        by_frac = sorted(range(len(band)), key=lambda i: shares[i] - extras[i], reverse=True)
        for i in by_frac[:remainder]:
            extras[i] += 1
        # Apply, clamping at max_w; pool any clamped leftover.
        leftover = 0
        for i, w in enumerate(band):
            new_w = w["position"]["w"] + extras[i]
            if new_w > maxes[i]:
                leftover += new_w - maxes[i]
                new_w = maxes[i]
            w["position"]["w"] = new_w
        # Redistribute leftover to widgets still under their max.
        while leftover > 0:
            grew = False
            for i, w in enumerate(band):
                if leftover <= 0:
                    break
                if w["position"]["w"] < maxes[i]:
                    w["position"]["w"] += 1
                    leftover -= 1
                    grew = True
            if not grew:
                break  # every widget capped (e.g. lone pie) — leave the gap

    # Re-pack x contiguously from 0 in left-to-right order.
    cursor = 0
    for w in band:
        w["position"]["x"] = cursor
        cursor += w["position"]["w"]


def _compact_vertical(bands: list[list[dict]]) -> None:
    """Shift each band up as a unit so bands stack with no empty rows."""
    cursor = 0
    for band in bands:
        top = min(w["position"]["y"] for w in band)
        bottom = max(w["position"]["y"] + w["position"]["h"] for w in band)
        dy = top - cursor
        if dy:
            for w in band:
                w["position"]["y"] -= dy
        cursor += bottom - top


def normalize_dashboard_layout(widgets: list[dict]) -> list[dict]:
    """Normalize agent-generated widget positions in place and return the list.

    Passes: sanitize → resolve overlaps → fill row widths to 12 → compact
    vertical gaps. Array order and all non-position fields are untouched.
    """
    if not widgets:
        return widgets
    try:
        _sanitize(widgets)
        _resolve_overlaps(widgets)
        bands = _detect_bands(widgets)
        for band in bands:
            _normalize_band_widths(band)
        _compact_vertical(bands)
    except Exception:
        # Layout normalization is best-effort — never block dashboard creation.
        logger.warning("normalize_dashboard_layout failed; keeping agent layout", exc_info=True)
    return widgets
