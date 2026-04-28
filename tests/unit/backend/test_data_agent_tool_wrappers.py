"""Unit tests for the per-tool wrappers in backend.agents.data_agent.tools.

Locks down the contract so the five wrappers can be safely collapsed into
a single helper without changing observable tool sets.
"""
import pytest

from backend.agents.context import AgentContext
from backend.agents.data_agent.tools import (
    build_data_agent_tools,
    build_execute_query_tool,
    build_get_table_schema_tool,
    build_list_tables_tool,
    build_profile_table_tool,
    build_search_tables_tool,
)


def _ctx() -> AgentContext:
    return AgentContext(user_id="user-1", available_connections=[1])


@pytest.mark.parametrize(
    "builder, expected_name",
    [
        (build_list_tables_tool, "list_tables"),
        (build_get_table_schema_tool, "get_table_schema"),
        (build_search_tables_tool, "search_tables"),
        (build_execute_query_tool, "execute_query"),
        (build_profile_table_tool, "profile_table"),
    ],
)
def test_wrapper_returns_only_its_named_tool(builder, expected_name):
    tools = builder(_ctx())
    assert len(tools) == 1
    assert tools[0].name == expected_name


def test_each_wrapper_returns_a_subset_of_build_data_agent_tools():
    """Every wrapper's output must be drawn from the canonical toolset."""
    full = {t.name for t in build_data_agent_tools(_ctx())}
    wrappers = [
        build_list_tables_tool,
        build_get_table_schema_tool,
        build_search_tables_tool,
        build_execute_query_tool,
        build_profile_table_tool,
    ]
    wrapper_names = {builder(_ctx())[0].name for builder in wrappers}
    assert wrapper_names <= full
    # And the wrappers cover exactly the five public data-agent tools.
    assert wrapper_names == {
        "list_tables", "get_table_schema", "search_tables",
        "execute_query", "profile_table",
    }
