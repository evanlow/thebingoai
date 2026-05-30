"""Tests for `services.watermark_classifier`.

Covers:
  - Deterministic ranked matcher (type tier > name tier > source order).
  - Native partition-key helper short-circuits everything else.
  - LLM batched path: high-confidence pick overrides deterministic.
  - LLM low-confidence / error / unparseable response → deterministic fallback.
  - Fence-tolerant LLM response parsing.
"""
from __future__ import annotations

import sys
import types as _types
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── Stub `backend.config` so the module import doesn't pull pydantic-settings.
# Real Settings is fine if available, but this keeps the test hermetic.
if "backend.config" not in sys.modules or not hasattr(sys.modules["backend.config"], "settings"):
    _cfg = _types.ModuleType("backend.config")
    _cfg.settings = SimpleNamespace(
        watermark_classifier_model="",
        watermark_classifier_provider="",
    )
    sys.modules["backend.config"] = _cfg


from backend.services.watermark_classifier import (  # noqa: E402
    _deterministic_pick,
    _name_tier,
    _parse_llm_response,
    _type_tier,
    resolve_watermark,
)


# ── _deterministic_pick — pure-function checks ──────────────────────────────


def test_deterministic_picks_updated_at_over_created_at():
    cols = [
        {"name": "id", "type": "bigint", "primary_key": True},
        {"name": "created_at", "type": "timestamp"},
        {"name": "updated_at", "type": "timestamp"},
    ]
    assert _deterministic_pick(cols) == "updated_at"


def test_deterministic_prefers_timestamptz_over_date():
    cols = [
        {"name": "event_date", "type": "date"},
        {"name": "modified_at", "type": "timestamp with time zone"},
    ]
    assert _deterministic_pick(cols) == "modified_at"


def test_deterministic_suffix_match_when_no_canonical_name():
    cols = [
        {"name": "id", "type": "bigint", "primary_key": True},
        {"name": "ingest_ts", "type": "timestamp"},
    ]
    assert _deterministic_pick(cols) == "ingest_ts"


def test_deterministic_returns_none_when_no_temporal_or_named_candidate():
    cols = [
        {"name": "id", "type": "bigint", "primary_key": True},
        {"name": "label", "type": "varchar"},
        {"name": "amount", "type": "numeric"},
    ]
    assert _deterministic_pick(cols) is None


def test_deterministic_ignores_unrelated_int_suffixed_columns():
    # `account_id` matches no canonical name and has no temporal type → reject.
    cols = [{"name": "account_id", "type": "bigint"}]
    assert _deterministic_pick(cols) is None


def test_type_and_name_tiers_are_monotone():
    assert _type_tier("timestamptz") < _type_tier("timestamp") < _type_tier("date")
    assert _name_tier("updated_at") < _name_tier("created_at") < _name_tier("event_date")


# ── resolve_watermark — wiring + fallback semantics ─────────────────────────


def _reg(type_id: str = "postgres"):
    return SimpleNamespace(type_id=type_id)


def test_resolve_uses_partition_key_helper_first():
    """Postgres native partition-key short-circuits LLM + deterministic."""
    fake_pg = _types.ModuleType("backend.connectors.postgres")
    fake_pg.detect_partition_key = MagicMock(return_value="partition_dt")
    with patch.dict(sys.modules, {"backend.connectors.postgres": fake_pg}):
        out = resolve_watermark(
            _reg("postgres"),
            connector=MagicMock(),
            tables=["events"],
            columns_by_table={"events": [{"name": "updated_at", "type": "timestamp"}]},
        )
    assert out == {"events": "partition_dt"}
    fake_pg.detect_partition_key.assert_called_once()


def test_resolve_falls_through_to_deterministic_when_no_partition_key():
    fake_pg = _types.ModuleType("backend.connectors.postgres")
    fake_pg.detect_partition_key = MagicMock(return_value=None)
    with patch.dict(sys.modules, {"backend.connectors.postgres": fake_pg}):
        out = resolve_watermark(
            _reg("postgres"),
            connector=MagicMock(),
            tables=["orders"],
            columns_by_table={"orders": [
                {"name": "id", "type": "bigint", "primary_key": True},
                {"name": "updated_at", "type": "timestamp"},
            ]},
        )
    assert out == {"orders": "updated_at"}


def test_resolve_returns_none_when_no_candidate():
    fake_pg = _types.ModuleType("backend.connectors.postgres")
    fake_pg.detect_partition_key = MagicMock(return_value=None)
    with patch.dict(sys.modules, {"backend.connectors.postgres": fake_pg}):
        out = resolve_watermark(
            _reg("postgres"), connector=MagicMock(),
            tables=["lookup"], columns_by_table={"lookup": [{"name": "label", "type": "varchar"}]},
        )
    assert out == {"lookup": None}


def test_resolve_handles_unknown_connector_type_gracefully():
    """Non-pg/mysql type_id skips the partition helper and falls to deterministic."""
    out = resolve_watermark(
        _reg("sqlite"), connector=MagicMock(),
        tables=["t"], columns_by_table={"t": [{"name": "updated_at", "type": "timestamp"}]},
    )
    assert out == {"t": "updated_at"}


# ── LLM-first path ───────────────────────────────────────────────────────────


@pytest.fixture
def _llm_settings(monkeypatch):
    from backend.config import settings
    monkeypatch.setattr(settings, "watermark_classifier_model", "claude-sonnet-test", raising=False)
    monkeypatch.setattr(settings, "watermark_classifier_provider", "anthropic", raising=False)


def _patch_provider_chat(monkeypatch, json_str):
    """Install a fake LLM provider whose async `chat` returns *json_str*."""
    fake_llm = _types.ModuleType("backend.llm.factory")
    provider = MagicMock()
    provider.chat = AsyncMock(return_value=json_str)
    fake_llm.get_provider = MagicMock(return_value=provider)
    monkeypatch.setitem(sys.modules, "backend.llm.factory", fake_llm)
    return provider


def test_llm_high_confidence_pick_overrides_deterministic(monkeypatch, _llm_settings):
    fake_pg = _types.ModuleType("backend.connectors.postgres")
    fake_pg.detect_partition_key = MagicMock(return_value=None)
    monkeypatch.setitem(sys.modules, "backend.connectors.postgres", fake_pg)
    _patch_provider_chat(
        monkeypatch,
        '{"picks": [{"table": "orders", "column": "ingested_at", "confidence": 0.9}]}',
    )

    out = resolve_watermark(
        _reg("postgres"), connector=MagicMock(),
        tables=["orders"],
        columns_by_table={"orders": [
            {"name": "created_at", "type": "timestamp"},
            {"name": "ingested_at", "type": "timestamp"},
        ]},
    )
    assert out == {"orders": "ingested_at"}


def test_llm_low_confidence_falls_back_to_deterministic(monkeypatch, _llm_settings):
    fake_pg = _types.ModuleType("backend.connectors.postgres")
    fake_pg.detect_partition_key = MagicMock(return_value=None)
    monkeypatch.setitem(sys.modules, "backend.connectors.postgres", fake_pg)
    _patch_provider_chat(
        monkeypatch,
        '{"picks": [{"table": "orders", "column": "ingested_at", "confidence": 0.3}]}',
    )

    out = resolve_watermark(
        _reg("postgres"), connector=MagicMock(),
        tables=["orders"],
        columns_by_table={"orders": [
            {"name": "created_at", "type": "timestamp"},
            {"name": "ingested_at", "type": "timestamp"},
        ]},
    )
    # Low confidence rejected → deterministic picks created_at (only canonical-tier
    # column in the list).
    assert out == {"orders": "created_at"}


def test_llm_error_falls_back_to_deterministic(monkeypatch, _llm_settings):
    fake_pg = _types.ModuleType("backend.connectors.postgres")
    fake_pg.detect_partition_key = MagicMock(return_value=None)
    monkeypatch.setitem(sys.modules, "backend.connectors.postgres", fake_pg)
    fake_llm = _types.ModuleType("backend.llm.factory")
    provider = MagicMock()
    provider.chat = AsyncMock(side_effect=RuntimeError("boom"))
    fake_llm.get_provider = MagicMock(return_value=provider)
    monkeypatch.setitem(sys.modules, "backend.llm.factory", fake_llm)

    out = resolve_watermark(
        _reg("postgres"), connector=MagicMock(),
        tables=["t"], columns_by_table={"t": [{"name": "updated_at", "type": "timestamp"}]},
    )
    assert out == {"t": "updated_at"}


def test_llm_unparseable_json_falls_back(monkeypatch, _llm_settings):
    fake_pg = _types.ModuleType("backend.connectors.postgres")
    fake_pg.detect_partition_key = MagicMock(return_value=None)
    monkeypatch.setitem(sys.modules, "backend.connectors.postgres", fake_pg)
    _patch_provider_chat(monkeypatch, "not json at all")

    out = resolve_watermark(
        _reg("postgres"), connector=MagicMock(),
        tables=["t"], columns_by_table={"t": [{"name": "updated_at", "type": "timestamp"}]},
    )
    assert out == {"t": "updated_at"}


def test_llm_batched_call_includes_all_unresolved_tables(monkeypatch, _llm_settings):
    """LLM should be called ONCE with every table still unresolved after step 1."""
    fake_pg = _types.ModuleType("backend.connectors.postgres")
    fake_pg.detect_partition_key = MagicMock(return_value=None)
    monkeypatch.setitem(sys.modules, "backend.connectors.postgres", fake_pg)
    provider = _patch_provider_chat(
        monkeypatch,
        '{"picks": ['
        ' {"table": "a", "column": "updated_at", "confidence": 0.9},'
        ' {"table": "b", "column": "created_at", "confidence": 0.7}'
        ']}',
    )

    out = resolve_watermark(
        _reg("postgres"), connector=MagicMock(),
        tables=["a", "b"],
        columns_by_table={
            "a": [{"name": "updated_at", "type": "timestamp"}],
            "b": [{"name": "created_at", "type": "timestamp"}],
        },
    )
    assert out == {"a": "updated_at", "b": "created_at"}
    assert provider.chat.call_count == 1


# ── LLM response parsing ─────────────────────────────────────────────────────


def test_parse_llm_response_tolerates_markdown_fences():
    raw = (
        "```json\n"
        '{"results": [{"table": "t", "column": "c", "confidence": "high"}]}'
        "\n```"
    )
    parsed = _parse_llm_response(raw)
    assert parsed["t"]["column"] == "c"
    assert parsed["t"]["confidence"] == "high"
