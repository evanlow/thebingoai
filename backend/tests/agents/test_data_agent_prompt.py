"""Phase 3: the data_agent prompt routes open-ended EDA to profile_table.

These are content guards — they prove the prompt text changed. True loop-collapse
behaviour is verified by the integration run (plan Phase 4 manual ship-gate).
"""
from backend.agents.data_agent.prompts import DATA_AGENT_SYSTEM_PROMPT as P


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
