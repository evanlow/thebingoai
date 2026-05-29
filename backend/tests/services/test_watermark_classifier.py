"""Tests for `backend.services.watermark_classifier`.

Covers:
  - Deterministic matcher: preferred name wins, fallback to first date-typed
    column, None when no date column exists, case-insensitivity, type-token
    matching (timestamptz / datetime).
  - LLM-first batched classifier: empty config → deterministic only;
    successful LLM response wired through; per-table low-confidence falls
    back; hallucinated column falls back; LLM exception falls back;
    unparseable response falls back.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from backend.services import watermark_classifier as wc


# ── Deterministic matcher ───────────────────────────────────────────────────

def test_classify_table_prefers_updated_at_over_created_at():
    cols = [
        {"name": "id", "type": "int"},
        {"name": "created_at", "type": "timestamp"},
        {"name": "updated_at", "type": "timestamp"},
    ]
    assert wc.classify_table(cols) == "updated_at"


def test_classify_table_returns_first_date_typed_when_no_preferred_name():
    cols = [
        {"name": "id", "type": "int"},
        {"name": "ship_ts", "type": "TIMESTAMP WITHOUT TIME ZONE"},
        {"name": "label", "type": "varchar"},
    ]
    assert wc.classify_table(cols) == "ship_ts"


def test_classify_table_handles_timestamptz_and_datetime_types():
    cols = [
        {"name": "x_dt", "type": "DATETIME"},
        {"name": "event_ts", "type": "timestamptz"},
    ]
    # `event_ts` matches neither a preferred name nor sorts first — first
    # date-typed wins.
    assert wc.classify_table(cols) == "x_dt"


def test_classify_table_case_insensitive_match():
    cols = [{"name": "Created_At", "type": "TIMESTAMP"}]
    assert wc.classify_table(cols) == "Created_At"


def test_classify_table_returns_none_when_no_date_column():
    cols = [{"name": "id", "type": "bigint"}, {"name": "label", "type": "text"}]
    assert wc.classify_table(cols) is None


def test_classify_table_handles_empty_columns():
    assert wc.classify_table([]) is None


# ── Batched LLM classifier ──────────────────────────────────────────────────

_FIXTURE_TABLES = {
    "orders": [
        {"name": "id", "type": "int"},
        {"name": "created_at", "type": "datetime"},
        {"name": "updated_at", "type": "datetime"},
    ],
    "lookup": [
        {"name": "code", "type": "varchar"},
        {"name": "label", "type": "text"},
    ],
}


def _settings_patch(monkeypatch, provider="openai", model="gpt-4o-mini"):
    """Force the env-config knobs the classifier reads."""
    from backend.config import settings
    monkeypatch.setattr(settings, "watermark_classifier_provider", provider, raising=False)
    monkeypatch.setattr(settings, "watermark_classifier_model", model, raising=False)


def test_classify_connection_empty_config_returns_deterministic(monkeypatch):
    """No provider/model → no LLM call, deterministic results returned."""
    _settings_patch(monkeypatch, provider="", model="")

    called = {"hit": False}

    def _boom(*a, **kw):
        called["hit"] = True
        raise AssertionError("LLM must not be called when config empty")

    monkeypatch.setattr(wc, "_call_llm", _boom)

    out = wc.classify_connection(_FIXTURE_TABLES)
    assert out == {"orders": "updated_at", "lookup": None}
    assert called["hit"] is False


def test_classify_connection_empty_tables_short_circuits(monkeypatch):
    """Empty input → no LLM call, empty result."""
    _settings_patch(monkeypatch)
    monkeypatch.setattr(
        wc, "_call_llm",
        lambda *a, **kw: (_ for _ in ()).throw(AssertionError("must not be called")),
    )
    assert wc.classify_connection({}) == {}


def test_classify_connection_llm_high_confidence_wins(monkeypatch):
    _settings_patch(monkeypatch)
    fake_response = (
        '{"results": ['
        '{"table": "orders", "column": "created_at", "confidence": "high"},'
        '{"table": "lookup", "column": null, "confidence": "high"}'
        "]}"
    )

    async def _fake(*a, **kw):
        return fake_response

    monkeypatch.setattr(wc, "_call_llm", _fake)

    out = wc.classify_connection(_FIXTURE_TABLES)
    # LLM picked `created_at` for orders (vs deterministic `updated_at`); honor.
    assert out["orders"] == "created_at"
    assert out["lookup"] is None


def test_classify_connection_low_confidence_falls_back_per_table(monkeypatch):
    _settings_patch(monkeypatch)

    async def _fake(*a, **kw):
        return (
            '{"results": ['
            '{"table": "orders", "column": "created_at", "confidence": "low"}'
            "]}"
        )

    monkeypatch.setattr(wc, "_call_llm", _fake)

    out = wc.classify_connection(_FIXTURE_TABLES)
    # Low confidence → deterministic for that table; lookup absent in LLM
    # response → deterministic (None).
    assert out["orders"] == "updated_at"
    assert out["lookup"] is None


def test_classify_connection_hallucinated_column_falls_back(monkeypatch):
    _settings_patch(monkeypatch)

    async def _fake(*a, **kw):
        return (
            '{"results": ['
            '{"table": "orders", "column": "nonexistent_col", "confidence": "high"}'
            "]}"
        )

    monkeypatch.setattr(wc, "_call_llm", _fake)

    out = wc.classify_connection(_FIXTURE_TABLES)
    # Hallucinated column → deterministic fallback for that table.
    assert out["orders"] == "updated_at"


def test_classify_connection_llm_exception_falls_back(monkeypatch):
    _settings_patch(monkeypatch)

    async def _boom(*a, **kw):
        raise RuntimeError("upstream LLM 500")

    monkeypatch.setattr(wc, "_call_llm", _boom)

    out = wc.classify_connection(_FIXTURE_TABLES)
    assert out == {"orders": "updated_at", "lookup": None}


def test_classify_connection_unparseable_response_falls_back(monkeypatch):
    _settings_patch(monkeypatch)

    async def _fake(*a, **kw):
        return "I don't think any of these tables have a watermark, sorry!"

    monkeypatch.setattr(wc, "_call_llm", _fake)

    out = wc.classify_connection(_FIXTURE_TABLES)
    assert out == {"orders": "updated_at", "lookup": None}


def test_parse_llm_response_tolerates_markdown_fences():
    raw = (
        "```json\n"
        '{"results": [{"table": "t", "column": "c", "confidence": "high"}]}'
        "\n```"
    )
    parsed = wc._parse_llm_response(raw)
    assert parsed["t"]["column"] == "c"
    assert parsed["t"]["confidence"] == "high"
