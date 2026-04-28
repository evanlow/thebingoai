"""Unit tests for backend.agents.invoke_helpers.extract_final_answer."""
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from backend.agents.invoke_helpers import extract_final_answer as _extract_final_answer


def _ai(content, *, tool_calls=None):
    """AIMessage with optional tool_calls — matches LangChain's runtime shape."""
    return AIMessage(content=content, tool_calls=list(tool_calls) if tool_calls else [])


def _tool_call(name="t"):
    return {"name": name, "args": {}, "id": f"call-{name}"}


def test_returns_none_for_empty_messages():
    assert _extract_final_answer([]) is None


def test_returns_last_ai_message_without_tool_calls():
    messages = [
        HumanMessage(content="what's 2+2?"),
        _ai("", tool_calls=[_tool_call("calc")]),
        ToolMessage(content="4", tool_call_id="call-calc"),
        _ai("The answer is 4."),
    ]
    assert _extract_final_answer(messages) == "The answer is 4."


def test_skips_ai_messages_with_tool_calls():
    messages = [
        HumanMessage(content="hi"),
        _ai("", tool_calls=[_tool_call("a")]),
        _ai("", tool_calls=[_tool_call("b")]),
    ]
    assert _extract_final_answer(messages) is None


def test_returns_most_recent_when_multiple_finals():
    messages = [
        _ai("first answer"),
        _ai("", tool_calls=[_tool_call("x")]),
        _ai("second answer"),
    ]
    assert _extract_final_answer(messages) == "second answer"


def test_ignores_human_and_tool_messages():
    messages = [
        HumanMessage(content="ignored"),
        ToolMessage(content="also ignored", tool_call_id="x"),
        _ai("real answer"),
        HumanMessage(content="follow-up question with no answer yet"),
    ]
    assert _extract_final_answer(messages) == "real answer"


def test_handles_messages_without_type_attr():
    """Defensive: messages missing .type should be skipped, not crash."""

    class Bare:
        content = "junk"

    messages = [Bare(), _ai("real")]
    assert _extract_final_answer(messages) == "real"
