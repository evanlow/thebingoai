"""Phase 3: the data_agent prompt routes open-ended EDA to profile_table.

These are content guards — they prove the prompt text changed. True loop-collapse
behaviour is verified by the integration run (plan Phase 4 manual ship-gate).
"""
import copy
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from backend.agents.data_agent.prompts import DATA_AGENT_SYSTEM_PROMPT as P
from backend.agents.data_agent.prompts import build_dataset_context_block


def test_prompt_lists_profile_table():
    assert "profile_table(connection_id, table_name)" in P


def test_prompt_has_eda_rule_profile_before_query():
    assert "ONCE per relevant table" in P
    assert "analyze this dataset" in P.lower()


def test_prompt_budget_is_five_not_fifteen():
    assert "5 execute_query calls" in P
    assert "maximum of 15" not in P
    assert "15 tool calls" not in P


def test_worked_example_opens_with_profile_table():
    example = P[P.index("Example workflow"):]
    assert "profile_table(" in example
    assert example.index("profile_table(") < example.index("execute_query("), \
        "the worked example must lead with profile_table, then execute_query"


def test_worked_example_still_answers():
    example = P[P.index("Example workflow"):]
    assert "ANSWER:" in example  # profiling is the entry point, not the whole job


# ---------------------------------------------------------------------------
# Pre-loaded dataset schema block carries semantic-layer meaning
# ---------------------------------------------------------------------------

_CTX = {
    "tables": {
        "sales_q4": {
            "rowCount": 12043,
            "columns": {
                "rev_amt": {"type": "numeric", "role": "measure", "cardinality": 8821},
            },
        }
    }
}


def _block(ctx):
    conn = SimpleNamespace(id=7, name="sales_q4.csv", db_type="dataset", database="d")
    with patch("backend.database.session.SessionLocal", return_value=MagicMock()), \
         patch("backend.services.semantic_layer.load_enriched_context", return_value=ctx), \
         patch("backend.services.llm_privacy.metadata_only_for_connection", return_value=False):
        return build_dataset_context_block([conn])


def test_dataset_block_without_glossary_keeps_the_bare_column_line():
    assert "- rev_amt: numeric | role=measure | 8821 distinct" in _block(copy.deepcopy(_CTX))


def test_dataset_block_carries_display_name_and_description():
    ctx = copy.deepcopy(_CTX)
    table = ctx["tables"]["sales_q4"]
    table["description"] = "Line-level order revenue by channel"
    table["columns"]["rev_amt"]["displayName"] = "Revenue Amount"
    table["columns"]["rev_amt"]["description"] = "order revenue in MYR, excludes tax"

    out = _block(ctx)
    assert "Line-level order revenue by channel" in out
    assert "- rev_amt (Revenue Amount):" in out
    assert "order revenue in MYR, excludes tax" in out
