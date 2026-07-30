"""The ask_user_question turn must persist what it asked.

`final_message` accumulates only from `token` events, and the ask force-stop
yields `done` without streaming any — so the turn persisted an EMPTY assistant
message. `_build_messages` then replayed `AIMessage(content="")` and the
follow-up turn read `user → assistant:"" → user`, leaving the model to re-infer
its own question. An empty assistant turn is also a provider-compatibility
hazard.

Covers both halves of the seam: the `done` event graph.py emits, and the fold
websocket.py applies to it.
"""
from __future__ import annotations

import asyncio
import json

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from backend.agents.context import AgentContext
from backend.agents.orchestrator import graph as graph_mod
from backend.agents.orchestrator.graph import (
    _build_messages,
    _render_asked_questions,
)
from backend.api.websocket import _fold_ask_persist_content


_QUESTIONS = [
    {
        "question": "What time range should the dashboard cover?",
        "header": "Time range",
        "options": [
            {"label": "Last 7 days", "description": "Recent activity"},
            {"label": "Last 30 days", "description": "Monthly trends"},
        ],
    },
    {
        "question": "Which metrics matter most?",
        "header": "Metrics",
        "options": [
            {"label": "Revenue", "description": "Topline"},
            {"label": "Volume", "description": "Units"},
        ],
    },
]


# --- the rendering ---------------------------------------------------------


def test_rendering_names_every_question_asked():
    out = _render_asked_questions(_QUESTIONS)
    assert "What time range should the dashboard cover?" in out
    assert "Which metrics matter most?" in out


def test_rendering_carries_the_offered_options():
    out = _render_asked_questions(_QUESTIONS)
    assert "Last 7 days" in out and "Last 30 days" in out
    assert "Revenue" in out and "Volume" in out


def test_rendering_is_non_empty_for_a_valid_payload():
    assert _render_asked_questions(_QUESTIONS).strip()


@pytest.mark.parametrize("payload", [
    [],
    [{"question": "   ", "options": []}],
    [{"header": "no question text"}],
    ["not a dict"],
])
def test_rendering_is_empty_when_there_is_nothing_to_say(payload):
    """An empty string must not displace a real message downstream."""
    assert _render_asked_questions(payload) == ""


def test_rendering_survives_malformed_options():
    out = _render_asked_questions([
        {"question": "Pick one", "options": ["bare string", {"no_label": 1}, {"label": "Good"}]}
    ])
    assert "Pick one" in out
    assert "Good" in out


# --- the websocket fold ----------------------------------------------------


def test_ask_turn_persists_the_questions_when_no_tokens_streamed():
    event = {"type": "done", "content": "Waiting for user input",
             "persist_content": _render_asked_questions(_QUESTIONS)}
    assert "What time range" in _fold_ask_persist_content(event, "")


def test_the_key_is_popped_so_it_never_reaches_the_client():
    """`done` spreads every remaining event key into the WS payload."""
    event = {"type": "done", "content": "Waiting for user input",
             "persist_content": "I asked the user:\n- x"}
    _fold_ask_persist_content(event, "")
    assert "persist_content" not in event


def test_a_streamed_turn_is_unaffected():
    """Real tokens win — the fallback must never override a streamed answer."""
    event = {"type": "done", "content": "ok", "persist_content": "I asked the user:\n- x"}
    assert _fold_ask_persist_content(event, "Here is your dashboard.") == "Here is your dashboard."


def test_a_normal_done_event_is_passed_through_untouched():
    event = {"type": "done", "content": "ok"}
    assert _fold_ask_persist_content(event, "streamed answer") == "streamed answer"


def test_an_errored_turn_still_persists_empty():
    """No tokens and no ask — the fallback must not leak into unrelated paths."""
    event = {"type": "done", "content": "error"}
    assert _fold_ask_persist_content(event, "") == ""


def test_an_empty_rendering_does_not_displace_an_empty_message():
    event = {"type": "done", "persist_content": ""}
    assert _fold_ask_persist_content(event, "") == ""


# --- the replay ------------------------------------------------------------


class _Msg:
    def __init__(self, role, content, source="chat"):
        self.role = role
        self.content = content
        self.source = source
        self.attachments = None


def test_replaying_the_persisted_ask_turn_yields_a_non_empty_ai_message():
    persisted = _render_asked_questions(_QUESTIONS)
    history = [
        _Msg("user", "build me a dashboard"),
        _Msg("assistant", persisted),
    ]
    messages = _build_messages("last 30 days, revenue", history, None)
    ai = [m for m in messages if isinstance(m, AIMessage)]
    assert len(ai) == 1
    assert ai[0].content.strip(), "the ask turn must not replay as an empty AIMessage"


def test_the_question_text_survives_into_the_replayed_history():
    history = [
        _Msg("user", "build me a dashboard"),
        _Msg("assistant", _render_asked_questions(_QUESTIONS)),
    ]
    replayed = "\n".join(
        m.content for m in _build_messages("answer", history, None) if isinstance(m, AIMessage)
    )
    assert "What time range should the dashboard cover?" in replayed
    assert "Which metrics matter most?" in replayed


def test_a_normal_turn_replays_exactly_as_before():
    history = [_Msg("user", "hi"), _Msg("assistant", "hello")]
    messages = _build_messages("next", history, None)
    assert [type(m) for m in messages] == [HumanMessage, AIMessage, HumanMessage]
    assert messages[1].content == "hello"


# --- the force-stop, driven through the real event loop --------------------


def _drive(monkeypatch, tool_output):
    """Run stream_orchestrator over a scripted ask_user_question tool result."""
    events = [
        {"event": "on_tool_start", "name": "ask_user_question",
         "data": {"input": {"questions": "[]"}}, "run_id": "r1"},
        {"event": "on_tool_end", "name": "ask_user_question",
         "data": {"output": tool_output}, "run_id": "r1"},
        {"event": "on_chain_end", "name": "agent", "data": {"output": {}}, "run_id": "r1"},
    ]

    class _FakeAgent:
        async def astream_events(self, _inputs, **_kw):
            for e in events:
                yield e

    monkeypatch.setattr(graph_mod, "build_orchestrator_tools", lambda *a, **k: [])
    monkeypatch.setattr(graph_mod, "_create_orchestrator_agent", lambda *a, **k: _FakeAgent())
    monkeypatch.setattr(graph_mod, "get_default_callbacks", lambda **k: [], raising=False)

    async def fake_prompt(*_a, **_k):
        return "system prompt"

    monkeypatch.setattr(graph_mod, "_render_orchestrator_prompt", fake_prompt)
    monkeypatch.setattr(
        "backend.agents.callbacks.get_callbacks", lambda **k: [], raising=False
    )

    ctx = AgentContext(
        user_id="u1", available_connections=[], connection_metadata=[], thread_id="t1",
    )

    async def _collect():
        return [e async for e in graph_mod.stream_orchestrator("build a dashboard", ctx)]

    return asyncio.run(_collect())


def test_a_successful_ask_stops_the_turn_and_carries_the_questions(monkeypatch):
    out = _drive(monkeypatch, json.dumps({"questions": _QUESTIONS}))
    done = [e for e in out if e.get("type") == "done"]
    assert len(done) == 1
    assert done[0]["content"] == "Waiting for user input"
    assert "What time range should the dashboard cover?" in done[0]["persist_content"]


def test_a_capped_ask_does_not_stop_the_turn(monkeypatch):
    """The one-round cap must let the agent keep going and finish the task —
    otherwise the cap strands the turn on a question the user never saw."""
    out = _drive(monkeypatch, json.dumps({"error": "You already asked the user a question"}))
    done = [e for e in out if e.get("type") == "done"]
    assert not any(d.get("content") == "Waiting for user input" for d in done)


def test_a_rejected_payload_does_not_stop_the_turn(monkeypatch):
    out = _drive(monkeypatch, json.dumps({"error": "Must provide 1-4 questions"}))
    assert not any(
        e.get("type") == "done" and e.get("content") == "Waiting for user input"
        for e in out
    )
