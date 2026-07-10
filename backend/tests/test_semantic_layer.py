"""Tests for the semantic-layer read-time merge (backend/services/semantic_layer.py).

The merge is a pure function, so these need no DB. The round-trip test proves the
key design guarantee: human edits live outside data_context and survive a full
re-profile (build_connection_context rebuild).
"""
from backend.services.semantic_layer import merge_semantics_into_context
from backend.services.connection_context import build_connection_context


def _context():
    return {
        "connectionId": 1,
        "tables": {
            "orders": {
                "schema": "public",
                "rowCount": 100,
                "columns": {
                    "cust_nm": {"type": "text", "role": "attribute", "nullable": True},
                    "amt_lcy": {"type": "numeric", "role": "measure", "nullable": True},
                    "customer_id": {"type": "integer", "role": "key", "nullable": False},
                },
            },
            "customers": {
                "schema": "public",
                "rowCount": 10,
                "columns": {"id": {"type": "integer", "role": "key", "nullable": False}},
            },
        },
        "relationships": [
            {"from": "orders.customer_id", "to": "customers.id", "type": "many_to_one", "inferred": True},
        ],
    }


def test_human_description_and_display_name_applied():
    semantics = {
        "glossary": {
            "orders.cust_nm": {"display_name": "Customer Name", "description": "Full name",
                               "source": "human", "status": "confirmed"},
        },
    }
    out = merge_semantics_into_context(_context(), semantics)
    col = out["tables"]["orders"]["columns"]["cust_nm"]
    assert col["description"] == "Full name"
    assert col["displayName"] == "Customer Name"


def test_draft_llm_entry_not_injected():
    semantics = {
        "glossary": {
            "orders.amt_lcy": {"description": "Amount in local currency",
                               "source": "llm", "status": "draft"},
        },
    }
    out = merge_semantics_into_context(_context(), semantics)
    # draft description must NOT reach the merged (agent-facing) context
    assert "description" not in out["tables"]["orders"]["columns"]["amt_lcy"]


def test_db_comment_is_lowest_precedence_and_overridden_by_human():
    ctx = _context()
    ctx["tables"]["orders"]["columns"]["amt_lcy"]["description"] = "db comment"
    semantics = {
        "glossary": {
            "orders.amt_lcy": {"description": "human wins", "source": "human", "status": "confirmed"},
        },
    }
    out = merge_semantics_into_context(ctx, semantics)
    assert out["tables"]["orders"]["columns"]["amt_lcy"]["description"] == "human wins"


def test_db_comment_survives_when_no_glossary_entry():
    ctx = _context()
    ctx["tables"]["orders"]["columns"]["amt_lcy"]["description"] = "db comment"
    out = merge_semantics_into_context(ctx, {"glossary": {}})
    assert out["tables"]["orders"]["columns"]["amt_lcy"]["description"] == "db comment"


def test_sensitive_flag_applied():
    semantics = {"glossary": {"orders.amt_lcy": {"sensitive": True}}}
    out = merge_semantics_into_context(_context(), semantics)
    assert out["tables"]["orders"]["columns"]["amt_lcy"]["sensitive"] is True


def test_rejected_relationship_suppressed():
    semantics = {
        "relationships": [
            {"from": "orders.customer_id", "to": "customers.id", "status": "rejected"},
        ],
    }
    out = merge_semantics_into_context(_context(), semantics)
    assert out["relationships"] == []


def test_confirmed_relationship_added_once():
    semantics = {
        "relationships": [
            {"from": "orders.rep_id", "to": "reps.id", "type": "many_to_one",
             "source": "human", "status": "confirmed"},
        ],
    }
    out = merge_semantics_into_context(_context(), semantics)
    pairs = [(r["from"], r["to"]) for r in out["relationships"]]
    assert ("orders.rep_id", "reps.id") in pairs
    assert len(pairs) == len(set(pairs))  # no dupes


def test_definitions_surface():
    semantics = {
        "definitions": [
            {"id": "d1", "name": "revenue", "description": "local-currency revenue",
             "sql": "SUM(amt_lcy)", "tables": ["orders"]},
        ],
    }
    out = merge_semantics_into_context(_context(), semantics)
    assert out["definitions"][0]["name"] == "revenue"


def test_merge_is_non_destructive():
    ctx = _context()
    semantics = {"glossary": {"orders.cust_nm": {"display_name": "X", "source": "human", "status": "confirmed"}}}
    merge_semantics_into_context(ctx, semantics)
    assert "displayName" not in ctx["tables"]["orders"]["columns"]["cust_nm"]


def test_edits_survive_reprofiling_round_trip():
    """The design guarantee: rebuild data_context from scratch, re-merge the same
    semantics — the human edit is still present because it lives outside the rebuild."""
    schema_json = {
        "schemas": {
            "public": {
                "tables": {
                    "orders": {
                        "row_count": 100,
                        "columns": [
                            {"name": "cust_nm", "type": "text", "nullable": True, "primary_key": False},
                        ],
                    },
                },
            },
        },
        "relationships": [],
    }
    semantics = {
        "glossary": {
            "orders.cust_nm": {"display_name": "Customer Name", "description": "Full name",
                               "source": "human", "status": "confirmed"},
        },
    }

    # First profile → merge
    ctx1 = build_connection_context(1, schema_json, {})
    merged1 = merge_semantics_into_context(ctx1, semantics)
    assert merged1["tables"]["orders"]["columns"]["cust_nm"]["displayName"] == "Customer Name"

    # Re-profile (fresh rebuild, semantics untouched) → merge again
    ctx2 = build_connection_context(1, schema_json, {})
    assert "displayName" not in ctx2["tables"]["orders"]["columns"]["cust_nm"]  # rebuild has no edit
    merged2 = merge_semantics_into_context(ctx2, semantics)
    assert merged2["tables"]["orders"]["columns"]["cust_nm"]["displayName"] == "Customer Name"
