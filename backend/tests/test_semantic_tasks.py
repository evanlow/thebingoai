"""Tests for the LLM glossary-draft merge + prompt building.

The task's DB/Redis/Celery wiring is thin; the logic that can break is in the two
pure helpers: `_merge_drafts` (never clobber human/confirmed, tag drafts) and
`_build_prompt` (leak real values only when allowed).
"""
from backend.tasks.semantic_tasks import _build_prompt, _merge_drafts


def _tdata():
    return {
        "rowCount": 100,
        "columns": {
            "cust_nm": {"type": "text", "role": "attribute", "topValues": ["Acme", "Globex"]},
            "amt_lcy": {"type": "numeric", "role": "measure", "min": 1, "max": 999},
        },
    }


# --- _merge_drafts ---------------------------------------------------------

def test_drafts_tagged_llm_draft():
    glossary = {}
    parsed = {
        "table_description": "Sales orders",
        "columns": {
            "cust_nm": {"description": "Customer name", "display_name": "Customer"},
            "amt_lcy": {"description": "Amount in local currency"},
        },
    }
    _merge_drafts(glossary, "orders", _tdata(), parsed, existing={})
    assert glossary["orders"] == {"description": "Sales orders", "source": "llm", "status": "draft"}
    assert glossary["orders.cust_nm"]["source"] == "llm"
    assert glossary["orders.cust_nm"]["status"] == "draft"
    assert glossary["orders.cust_nm"]["display_name"] == "Customer"
    assert glossary["orders.amt_lcy"]["description"] == "Amount in local currency"


def test_human_and_confirmed_not_overwritten():
    existing = {
        "orders.cust_nm": {"description": "Hand written", "source": "human", "status": "confirmed"},
        "orders.amt_lcy": {"description": "Confirmed LLM", "source": "llm", "status": "confirmed"},
    }
    glossary = dict(existing)
    parsed = {"columns": {
        "cust_nm": {"description": "AI guess"},
        "amt_lcy": {"description": "AI guess 2"},
    }}
    _merge_drafts(glossary, "orders", _tdata(), parsed, existing)
    assert glossary["orders.cust_nm"]["description"] == "Hand written"
    assert glossary["orders.amt_lcy"]["description"] == "Confirmed LLM"


def test_unknown_columns_skipped():
    glossary = {}
    parsed = {"columns": {"nonexistent": {"description": "x"}, "cust_nm": {"description": "y"}}}
    _merge_drafts(glossary, "orders", _tdata(), parsed, existing={})
    assert "orders.nonexistent" not in glossary
    assert glossary["orders.cust_nm"]["description"] == "y"


def test_empty_description_and_displayname_skipped():
    glossary = {}
    parsed = {"columns": {"cust_nm": {"description": "", "display_name": ""}}}
    _merge_drafts(glossary, "orders", _tdata(), parsed, existing={})
    assert "orders.cust_nm" not in glossary


# --- _build_prompt ---------------------------------------------------------

def test_prompt_includes_values_when_flag_off():
    prompt = _build_prompt("orders", _tdata(), meta_only=False, existing_glossary={})
    assert "Acme" in prompt          # top values
    assert "range 1–999" in prompt   # min/max


def test_prompt_excludes_values_when_flag_on():
    prompt = _build_prompt("orders", _tdata(), meta_only=True, existing_glossary={})
    assert "Acme" not in prompt
    assert "range 1–999" not in prompt


def test_prompt_excludes_values_for_sensitive_column():
    existing = {"orders.amt_lcy": {"sensitive": True}}
    prompt = _build_prompt("orders", _tdata(), meta_only=False, existing_glossary=existing)
    assert "range 1–999" not in prompt   # amt_lcy sensitive → no min/max
    assert "Acme" in prompt              # cust_nm still leaks


def test_prompt_seeds_known_meaning():
    existing = {"orders.cust_nm": {"description": "Customer Name", "source": "human", "status": "confirmed"}}
    prompt = _build_prompt("orders", _tdata(), meta_only=False, existing_glossary=existing)
    assert "known meaning" in prompt
    assert "Customer Name" in prompt
