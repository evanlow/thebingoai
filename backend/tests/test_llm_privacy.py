"""Tests for the metadata_only_llm privacy controls (backend/services/llm_privacy.py)."""
from types import SimpleNamespace

import pytest

from backend.services import llm_privacy
from backend.profiler.dataset_profiler import profile_dataframe


# --- pure redaction functions ------------------------------------------------

def test_strip_profile_values_drops_real_values_keeps_derived():
    profile = {
        "table_name": "orders",
        "row_count": 100,
        "columns": {
            "amt": {"type": "numeric", "min": 5, "max": 999, "avg": 50.0, "null_count": 2},
            "status": {"type": "categorical", "distinct_count": 3,
                       "null_count": 0, "top_values": ["A", "B", "C"]},
        },
    }
    out = llm_privacy.strip_profile_values(profile)

    # real values gone
    assert "min" not in out["columns"]["amt"]
    assert "max" not in out["columns"]["amt"]
    assert "top_values" not in out["columns"]["status"]
    # derived kept
    assert out["columns"]["amt"]["avg"] == 50.0
    assert out["columns"]["amt"]["null_count"] == 2
    assert out["columns"]["status"]["distinct_count"] == 3
    # non-destructive
    assert "min" in profile["columns"]["amt"]


def test_strip_preview_empties_rows_and_flags():
    result = {"columns": ["a", "b"], "rows": [[1, 2], [3, 4]], "row_count": 2, "result_ref": "x"}
    out = llm_privacy.strip_preview(result)
    assert out["rows"] == []
    assert out["values_withheld"] is True
    assert "note" in out
    assert out["columns"] == ["a", "b"] and out["row_count"] == 2
    assert result["rows"] == [[1, 2], [3, 4]]  # input untouched


def test_redact_sensitive_columns_case_insensitive():
    rows = [["Alice", 90000], ["Bob", 70000]]
    out = llm_privacy.redact_sensitive_columns(rows, ["name", "Salary"], {"salary"})
    assert out == [["Alice", "[REDACTED]"], ["Bob", "[REDACTED]"]]


def test_redact_sensitive_columns_noop_when_none_match():
    rows = [["Alice", 1]]
    out = llm_privacy.redact_sensitive_columns(rows, ["name", "score"], {"salary"})
    assert out == [["Alice", 1]]


# --- global privacy floor ----------------------------------------------------

def _floor(monkeypatch, on: bool):
    """Force the LLM_METADATA_ONLY floor on/off for a test."""
    from backend.config import settings
    monkeypatch.setattr(settings, "llm_metadata_only", on, raising=False)


def test_floor_on_forces_strict_regardless_of_org(monkeypatch):
    _floor(monkeypatch, True)
    # even an org with the per-Org flag off, and a legacy no-org connection, are strict
    monkeypatch.setattr(
        "backend.config.feature_flags.enabled",
        lambda org_id, flag, default=False: False,
    )
    assert llm_privacy.metadata_only_for_connection(SimpleNamespace(org_id="org-2")) is True
    assert llm_privacy.metadata_only_for_connection(SimpleNamespace(org_id=None)) is True


def test_floor_defaults_on(monkeypatch):
    # A fresh install (no env, no per-Org flag) withholds values.
    monkeypatch.setattr(
        "backend.config.feature_flags.enabled",
        lambda org_id, flag, default=False: False,
    )
    assert llm_privacy.metadata_only_for_connection(SimpleNamespace(org_id="org-2")) is True


# --- per-Org flag resolution (floor off) -------------------------------------

def test_metadata_only_for_connection_none_org_is_false(monkeypatch):
    _floor(monkeypatch, False)
    conn = SimpleNamespace(org_id=None)
    assert llm_privacy.metadata_only_for_connection(conn) is False


def test_metadata_only_for_connection_respects_flag(monkeypatch):
    _floor(monkeypatch, False)
    monkeypatch.setattr(
        "backend.config.feature_flags.enabled",
        lambda org_id, flag, default=False: flag == "metadata_only_llm" and org_id == "org-1",
    )
    assert llm_privacy.metadata_only_for_connection(SimpleNamespace(org_id="org-1")) is True
    assert llm_privacy.metadata_only_for_connection(SimpleNamespace(org_id="org-2")) is False


# --- dataset profiler render gate -------------------------------------------

def test_to_prompt_text_include_values_false_omits_real_values():
    import pandas as pd

    df = pd.DataFrame({
        "amount": [10, 20, 30, 40, 1000],
        "category": ["a", "a", "b", "b", "c"],
    })
    profile = profile_dataframe(df)

    full = profile.to_prompt_text("f.csv", include_values=True)
    safe = profile.to_prompt_text("f.csv", include_values=False)

    # full render exposes samples + value counts + min/max
    assert "## Sample Data" in full
    # safe render withholds them
    assert "## Sample Data" not in safe
    assert "Value counts" not in safe
    assert "Min:" not in safe
    assert "Mode:" not in safe
    # derived stats survive
    assert "Mean:" in safe
    # structural info survives
    assert "Columns Overview" in safe
