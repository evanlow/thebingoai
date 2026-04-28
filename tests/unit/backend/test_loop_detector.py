"""Unit tests for backend.agents.loop_detector.make_loop_detector."""
import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from backend.agents.exceptions import LoopDetectedError
from backend.agents.loop_detector import make_loop_detector


def _ai_with_calls(*calls):
    """Build an AIMessage that exposes the given tool_calls list."""
    return AIMessage(content="", tool_calls=list(calls))


def _call(name, args=None):
    return {"name": name, "args": args or {}, "id": f"call-{name}"}


def _run(detector, messages):
    return detector({"messages": messages})


def test_loop_detector_no_calls_returns_empty():
    detect = make_loop_detector(max_repeats=2, max_same_tool=10, max_total_calls=25)
    assert _run(detect, []) == {}
    assert _run(detect, [HumanMessage(content="hello")]) == {}


def test_loop_detector_under_repeat_threshold_returns_empty():
    detect = make_loop_detector(max_repeats=2, max_same_tool=10, max_total_calls=25)
    msgs = [_ai_with_calls(_call("list_tables", {"connection_id": 1}))]
    assert _run(detect, msgs) == {}


def test_loop_detector_repeat_threshold_injects_warning():
    detect = make_loop_detector(max_repeats=2, max_same_tool=10, max_total_calls=25)
    same = _call("list_tables", {"connection_id": 1})
    msgs = [_ai_with_calls(same), _ai_with_calls(same)]

    out = _run(detect, msgs)

    assert "messages" in out
    assert len(out["messages"]) == 1
    msg = out["messages"][0]
    assert isinstance(msg, SystemMessage)
    assert "[Loop detected]" in msg.content
    assert "list_tables" in msg.content


def test_loop_detector_max_same_tool_threshold_injects_warning():
    detect = make_loop_detector(max_repeats=99, max_same_tool=3, max_total_calls=25)
    msgs = [
        _ai_with_calls(_call("execute_query", {"sql": "SELECT 1"})),
        _ai_with_calls(_call("execute_query", {"sql": "SELECT 2"})),
        _ai_with_calls(_call("execute_query", {"sql": "SELECT 3"})),
    ]

    out = _run(detect, msgs)

    assert "messages" in out
    msg = out["messages"][0]
    assert isinstance(msg, SystemMessage)
    assert "[Loop detected]" in msg.content
    assert "execute_query" in msg.content


def test_loop_detector_max_total_calls_threshold_raises():
    """Check 3 is a hard stop — raises LoopDetectedError so the LLM can't ignore it."""
    detect = make_loop_detector(max_repeats=99, max_same_tool=99, max_total_calls=3)
    msgs = [
        _ai_with_calls(_call("a"), _call("b")),
        _ai_with_calls(_call("c")),
    ]

    with pytest.raises(LoopDetectedError) as excinfo:
        _run(detect, msgs)

    assert excinfo.value.total_calls == 3
    assert "Tool-call budget exhausted" in str(excinfo.value)


def test_loop_detector_thresholds_fire_independently():
    """Each threshold can trigger on its own without the others tripping."""
    only_repeats = make_loop_detector(max_repeats=2, max_same_tool=99, max_total_calls=99)
    only_same_tool = make_loop_detector(max_repeats=99, max_same_tool=2, max_total_calls=99)
    only_total = make_loop_detector(max_repeats=99, max_same_tool=99, max_total_calls=2)

    same = _call("foo", {"x": 1})
    repeat_msgs = [_ai_with_calls(same), _ai_with_calls(same)]
    same_tool_msgs = [_ai_with_calls(_call("foo", {"x": 1})), _ai_with_calls(_call("foo", {"x": 2}))]
    total_msgs = [_ai_with_calls(_call("a"), _call("b"))]

    assert "[Loop detected]" in only_repeats({"messages": repeat_msgs})["messages"][0].content
    assert "[Loop detected]" in only_same_tool({"messages": same_tool_msgs})["messages"][0].content
    with pytest.raises(LoopDetectedError):
        only_total({"messages": total_msgs})
