"""Phase 2: loop_detector soft query budget.

The pre-model hook counts execute_query tool calls and injects a one-time
"summarize now" nudge at the budget, while leaving the hard LoopDetectedError
backstop (max_total_calls) intact. Non-execute_query tools don't count.
"""
import pytest
from langchain_core.messages import AIMessage, SystemMessage

from backend.agents.loop_detector import make_loop_detector
from backend.agents.exceptions import LoopDetectedError


def _exec_msgs(n):
    """n AI messages, each carrying one execute_query call with distinct args
    (distinct args avoids tripping the identical-repeat detector)."""
    return [
        AIMessage(content="", tool_calls=[{"name": "execute_query", "args": {"sql": f"select {i}"}, "id": f"q{i}"}])
        for i in range(n)
    ]


def _named_msgs(names):
    return [
        AIMessage(content="", tool_calls=[{"name": name, "args": {"n": i}, "id": f"t{i}"}])
        for i, name in enumerate(names)
    ]


def test_budget_injects_nudge_at_threshold():
    detect = make_loop_detector(query_budget=5)
    out = detect({"messages": _exec_msgs(5)})
    assert out.get("messages"), "expected an injected message once the budget is reached"
    assert out["messages"][0].content.startswith("[Query budget]")


def test_below_budget_no_injection():
    detect = make_loop_detector(query_budget=5)
    assert detect({"messages": _exec_msgs(4)}) == {}


def test_non_execute_query_tools_do_not_count():
    # High family/total caps so only the budget could plausibly fire; it must not.
    detect = make_loop_detector(query_budget=5, max_same_tool=100, max_total_calls=100)
    names = ["list_tables", "get_table_schema", "search_tables", "profile_table"] * 3  # 12 calls, 0 execute_query
    assert detect({"messages": _named_msgs(names)}) == {}


def test_budget_injected_once_idempotent():
    detect = make_loop_detector(query_budget=5)
    msgs = _exec_msgs(6)  # over budget
    msgs.append(SystemMessage(content="[Query budget] You have run 5 queries. Summarize your findings now and answer the user — do not run more queries."))
    # A budget nudge is already present → the hook must not inject a second one.
    assert detect({"messages": msgs}) == {}


def test_hard_cap_still_raises():
    # query_budget high so the soft path is out of the way; 25 varied-name calls
    # (no 10-in-a-row same tool) so the family detector doesn't pre-empt the cap.
    detect = make_loop_detector(query_budget=100, max_total_calls=25)
    names = ["list_tables", "get_table_schema", "search_tables", "execute_query", "profile_table"]
    msgs = [
        AIMessage(content="", tool_calls=[{"name": names[i % 5], "args": {"n": i}, "id": f"t{i}"}])
        for i in range(25)
    ]
    with pytest.raises(LoopDetectedError):
        detect({"messages": msgs})


def test_default_query_budget_is_five():
    detect = make_loop_detector()  # no query_budget passed → default 5
    out = detect({"messages": _exec_msgs(5)})
    assert out.get("messages") and out["messages"][0].content.startswith("[Query budget]")
