"""Tests for backend.langgraph.nodes.generate_response.

Covers the LLM-invocation change: the node now routes through
`get_langchain_llm().ainvoke(messages, config=...)` (so LangGraph callbacks —
e.g. Langfuse — propagate) instead of the old `provider.chat()` path.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage


def _fake_provider(capture):
    """Provider whose langchain runnable records the messages + config it was invoked with."""
    async def ainvoke(messages, config=None):
        capture["messages"] = messages
        capture["config"] = config
        return AIMessage(content="stubbed answer")

    lc_llm = SimpleNamespace(ainvoke=ainvoke)
    provider = MagicMock()
    provider.get_langchain_llm.return_value = lc_llm
    # If the node ever fell back to the old path this would blow up the test.
    provider.chat.side_effect = AssertionError("generate_response must not call provider.chat()")
    return provider, lc_llm


@pytest.mark.asyncio
async def test_generate_response_uses_langchain_ainvoke(monkeypatch):
    from backend.langgraph import nodes

    capture = {}
    provider, _ = _fake_provider(capture)
    monkeypatch.setattr(nodes, "get_provider", lambda *_a, **_k: provider)

    state = {
        "question": "How many orders?",
        "context": [],
        "provider": "openai",
        "model": None,
        "temperature": 0.3,
        "messages": [],
    }
    result = await nodes.generate_response(state)

    assert result["answer"] == "stubbed answer"
    # New answer + question appended for the add_messages reducer.
    assert [type(m) for m in result["messages"]] == [HumanMessage, AIMessage]
    provider.get_langchain_llm.assert_called_once_with(temperature=0.3)
    # First message is the system prompt; the question is the final message.
    assert isinstance(capture["messages"][0], SystemMessage)
    assert capture["messages"][-1].content == "How many orders?"


@pytest.mark.asyncio
async def test_generate_response_propagates_config(monkeypatch):
    """A RunnableConfig passed to the node reaches the LLM (callback propagation)."""
    from backend.langgraph import nodes

    capture = {}
    provider, _ = _fake_provider(capture)
    monkeypatch.setattr(nodes, "get_provider", lambda *_a, **_k: provider)

    sentinel_config = {"callbacks": ["langfuse-handler"]}
    state = {
        "question": "q", "context": [], "provider": "openai",
        "model": None, "temperature": 0.0, "messages": [],
    }
    await nodes.generate_response(state, config=sentinel_config)

    assert capture["config"] == sentinel_config


@pytest.mark.asyncio
async def test_generate_response_includes_history(monkeypatch):
    """Prior conversation messages are forwarded to the LLM before the new question."""
    from backend.langgraph import nodes

    capture = {}
    provider, _ = _fake_provider(capture)
    monkeypatch.setattr(nodes, "get_provider", lambda *_a, **_k: provider)

    prior = HumanMessage(content="earlier turn")
    state = {
        "question": "follow-up", "context": [], "provider": "openai",
        "model": None, "temperature": 0.0, "messages": [prior],
    }
    await nodes.generate_response(state)

    contents = [m.content for m in capture["messages"]]
    assert "earlier turn" in contents
    assert contents[-1] == "follow-up"
