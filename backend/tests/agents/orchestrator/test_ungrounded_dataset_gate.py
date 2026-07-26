"""Grounding gate: a dataset was attached, no tool succeeded, so the answer
cannot be grounded in data.

The judge has no view of the tool trail or of what was in context, so the caller
arms it in code. The judge still decides — a greeting or a clarifying question on
the same turn must not trigger a retry.
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.agents.orchestrator import response_judge
from backend.agents.orchestrator.response_judge import JudgeVerdict, judge_response


@pytest.fixture
def captured_system_prompt(monkeypatch):
    """Capture the system prompt handed to the judge LLM."""
    seen: dict = {}

    structured = MagicMock()

    async def _ainvoke(messages):
        seen["system"] = messages[0]["content"]
        seen["user"] = messages[1]["content"]
        return JudgeVerdict(resolved=True, reason="ok")

    structured.ainvoke = _ainvoke
    llm = MagicMock()
    llm.with_structured_output = MagicMock(return_value=structured)
    provider = MagicMock()
    provider.get_langchain_llm = MagicMock(return_value=llm)

    monkeypatch.setattr(response_judge, "get_provider", lambda _name: provider)
    monkeypatch.setattr(response_judge.settings, "judge_enabled", True)
    monkeypatch.setattr(response_judge.settings, "judge_llm_model", "test-model")
    monkeypatch.setattr(response_judge.settings, "judge_highlight_enabled", False)
    return seen


@pytest.mark.asyncio
async def test_armed_turn_gets_the_grounding_rule(captured_system_prompt):
    await judge_response(
        "tell me more about the dataset",
        "Each row = one employee. satisfaction_level is a 0–1 score…",
        ungrounded_dataset_turn=True,
    )
    assert "DATASET GROUNDING" in captured_system_prompt["system"]


@pytest.mark.asyncio
async def test_ordinary_turn_pays_nothing(captured_system_prompt):
    """Unarmed turns must not carry the rule — no token cost, no false positives
    on legitimate schema talk (e.g. the user explicitly asked what columns exist)."""
    await judge_response("what is 2+2", "4")
    assert "DATASET GROUNDING" not in captured_system_prompt["system"]


# ---------------------------------------------------------------------------
# Arming condition, as computed by stream_orchestrator
# ---------------------------------------------------------------------------

def _armed(file_contents, any_tool_ran):
    """Mirror of the gate expression in stream_orchestrator."""
    return not any_tool_ran and any(
        str(f.get("file_id", "")).startswith("connection:")
        for f in (file_contents or [])
    )


def test_arms_on_dataset_chip_with_no_successful_tool():
    assert _armed([{"file_id": "connection:98"}], any_tool_ran=False) is True


def test_does_not_arm_when_a_tool_succeeded():
    assert _armed([{"file_id": "connection:98"}], any_tool_ran=True) is False


def test_does_not_arm_without_a_dataset_attachment():
    assert _armed([{"file_id": "abc-uuid"}], any_tool_ran=False) is False
    assert _armed(None, any_tool_ran=False) is False


# ---------------------------------------------------------------------------
# The gate must survive the retry, or it is one-shot
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_retry_that_calls_no_tool_stays_armed(monkeypatch):
    """If the retry also answers from context, the re-judge must still be armed —
    otherwise the second verdict falls open and the ungrounded answer ships."""
    from langchain_core.messages import AIMessage, HumanMessage
    from backend.agents.orchestrator import graph

    base = [HumanMessage(content="tell me more about the dataset")]
    orchestrator = MagicMock()
    orchestrator.ainvoke = AsyncMock(return_value={
        "messages": base + [
            AIMessage(content="initial"),
            HumanMessage(content="<directive>"),
            AIMessage(content="Still just describing the columns."),
        ],
    })

    seen: list = []

    async def fake_judge(_q, _a, **kwargs):
        seen.append(kwargs.get("ungrounded_dataset_turn"))
        return JudgeVerdict(resolved=True, reason="ok")

    monkeypatch.setattr(graph, "judge_response", fake_judge)

    await graph._run_judge_retry(
        user_question="tell me more about the dataset",
        initial_answer="initial",
        initial_verdict=JudgeVerdict(resolved=False, reason="ungrounded", suggested_directive="query it"),
        orchestrator=orchestrator,
        base_messages=base,
        ungrounded_dataset_turn=True,
    )

    assert seen == [True]


@pytest.mark.asyncio
async def test_retry_that_calls_a_tool_disarms(monkeypatch):
    import json
    from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
    from backend.agents.orchestrator import graph

    base = [HumanMessage(content="tell me more about the dataset")]
    tool_call = AIMessage(content="")
    tool_call.tool_calls = [{"name": "data_agent", "id": "tc1", "args": {"question": "profile it"}}]
    orchestrator = MagicMock()
    orchestrator.ainvoke = AsyncMock(return_value={
        "messages": base + [
            AIMessage(content="initial"),
            HumanMessage(content="<directive>"),
            tool_call,
            ToolMessage(content=json.dumps({"success": True}), tool_call_id="tc1"),
            AIMessage(content="14,999 employees, 23.8% left."),
        ],
    })

    seen: list = []

    async def fake_judge(_q, _a, **kwargs):
        seen.append(kwargs.get("ungrounded_dataset_turn"))
        return JudgeVerdict(resolved=True, reason="ok")

    monkeypatch.setattr(graph, "judge_response", fake_judge)

    answer, succeeded, _meta, retry_steps = await graph._run_judge_retry(
        user_question="tell me more about the dataset",
        initial_answer="initial",
        initial_verdict=JudgeVerdict(resolved=False, reason="ungrounded", suggested_directive="query it"),
        orchestrator=orchestrator,
        base_messages=base,
        ungrounded_dataset_turn=True,
    )

    assert succeeded is True
    assert answer == "14,999 employees, 23.8% left."
    assert [s["tool_name"] for s in retry_steps] == ["data_agent", "data_agent"]
    assert seen == [False]
