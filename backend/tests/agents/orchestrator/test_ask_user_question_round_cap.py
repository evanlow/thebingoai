"""One clarification round per exchange, enforced inside `ask_user_question`.

The cap lives in the tool body, not in prompt text: prompt-only instruction did
not hold in the 2026-03-29 regression, and the loop detector structurally cannot
catch it (it reads `tool_calls` off `state["messages"]`, but `_build_messages`
replays history as plain Human/AIMessage with no `tool_calls`, so every turn
starts with a blank detector).

Uses a real SQLite session (mirrors test_refresh_visibility.py) so the
join/order_by that finds the preceding assistant message is actually exercised.
"""
from __future__ import annotations

import asyncio
import json

import pytest
from sqlalchemy import create_engine, JSON, LargeBinary
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.postgresql import BYTEA, JSONB

from backend.database.base import Base
from backend.agents.context import AgentContext
from backend.agents.orchestrator import graph as graph_mod
from backend.agents.orchestrator.graph import _previous_turn_asked_question
from backend.models.agent_step import AgentStep
from backend.models.conversation import Conversation
from backend.models.message import Message
from backend.models.user import User


@pytest.fixture(scope="function")
def db():
    engine = create_engine("sqlite:///:memory:")
    for table in Base.metadata.tables.values():
        for col in table.columns:
            if isinstance(col.type, JSONB):
                col.type = JSON()
                col.server_default = None
            elif isinstance(col.type, BYTEA):
                col.type = LargeBinary()
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(engine)


def _ctx(thread_id="t1"):
    return AgentContext(
        user_id="u1",
        available_connections=[],
        connection_metadata=[],
        thread_id=thread_id,
    )


def _seed(db, *, steps_on_last_assistant=()):
    """Seed user → conversation → user msg → assistant msg (+ optional steps)."""
    db.add(User(id="u1", email="u1@x.test"))
    conv = Conversation(thread_id="t1", user_id="u1", title="t")
    db.add(conv)
    db.flush()
    db.add(Message(conversation_id=conv.id, role="user", content="build me a dashboard"))
    db.flush()
    assistant = Message(conversation_id=conv.id, role="assistant", content="")
    db.add(assistant)
    db.flush()
    for i, tool_name in enumerate(steps_on_last_assistant):
        db.add(AgentStep(
            message_id=assistant.id,
            step_number=i,
            agent_type="orchestrator",
            step_type="tool_call",
            tool_name=tool_name,
            content={"tool": tool_name},
        ))
    db.commit()
    return conv, assistant


def _factory(db):
    class _NoCloseSession:
        """Hands the test's session to the helper but survives its .close()."""

        def __getattr__(self, name):
            return getattr(db, name)

        def close(self):
            pass

    return lambda: _NoCloseSession()


# --- the gate helper itself ------------------------------------------------


def test_prior_ask_step_is_detected(db):
    _seed(db, steps_on_last_assistant=("ask_user_question",))
    assert _previous_turn_asked_question(_ctx(), _factory(db)) is True


def test_no_prior_assistant_message_allows_asking(db):
    db.add(User(id="u1", email="u1@x.test"))
    conv = Conversation(thread_id="t1", user_id="u1", title="t")
    db.add(conv)
    db.flush()
    db.add(Message(conversation_id=conv.id, role="user", content="build me a dashboard"))
    db.commit()
    assert _previous_turn_asked_question(_ctx(), _factory(db)) is False


def test_prior_non_ask_step_allows_asking(db):
    """A previous turn that called create_dashboard must not block a new question."""
    _seed(db, steps_on_last_assistant=("create_dashboard",))
    assert _previous_turn_asked_question(_ctx(), _factory(db)) is False


def test_ask_step_on_an_older_turn_does_not_block(db):
    """Only the immediately-preceding assistant message counts."""
    db.add(User(id="u1", email="u1@x.test"))
    conv = Conversation(thread_id="t1", user_id="u1", title="t")
    db.add(conv)
    db.flush()
    old = Message(conversation_id=conv.id, role="assistant", content="")
    db.add(old)
    db.flush()
    db.add(AgentStep(
        message_id=old.id, step_number=0, agent_type="orchestrator",
        step_type="tool_call", tool_name="ask_user_question", content={},
    ))
    db.add(Message(conversation_id=conv.id, role="user", content="answer"))
    db.flush()
    newer = Message(conversation_id=conv.id, role="assistant", content="built it")
    db.add(newer)
    db.flush()
    db.add(AgentStep(
        message_id=newer.id, step_number=0, agent_type="orchestrator",
        step_type="tool_call", tool_name="create_dashboard", content={},
    ))
    db.commit()
    assert _previous_turn_asked_question(_ctx(), _factory(db)) is False


def test_other_users_thread_is_not_consulted(db):
    _seed(db, steps_on_last_assistant=("ask_user_question",))
    other = AgentContext(
        user_id="u2", available_connections=[], connection_metadata=[], thread_id="t1",
    )
    assert _previous_turn_asked_question(other, _factory(db)) is False


def test_fails_open_without_thread_id():
    assert _previous_turn_asked_question(_ctx(thread_id=None), lambda: None) is False


def test_fails_open_without_session_factory():
    assert _previous_turn_asked_question(_ctx(), None) is False


def test_fails_open_when_the_query_raises():
    """A broken DB must never block a legitimate first ask."""
    def boom():
        raise RuntimeError("db down")

    assert _previous_turn_asked_question(_ctx(), boom) is False


# --- the tool body ---------------------------------------------------------


def _ask_tool(monkeypatch, *, previous_asked: bool):
    """Build just the ask_user_question tool with the sub-builders stubbed out."""
    for name in (
        "build_skill_tools", "build_profile_tools", "build_soul_tools",
        "build_dashboard_tools", "build_memory_tools",
    ):
        monkeypatch.setattr(graph_mod, name, lambda *a, **k: [])
    monkeypatch.setattr(graph_mod, "_build_legacy_tools", lambda *a, **k: [])
    monkeypatch.setattr(
        graph_mod, "_previous_turn_asked_question", lambda *a, **k: previous_asked
    )
    tools = graph_mod.build_orchestrator_tools(_ctx(), db_session_factory=lambda: None)
    return next(t for t in tools if t.name == "ask_user_question")


_VALID = json.dumps([
    {
        "question": "What time range should the dashboard cover?",
        "header": "Time range",
        "options": [
            {"label": "Last 7 days", "description": "Recent activity"},
            {"label": "Last 30 days", "description": "Monthly trends"},
        ],
        "select": "single",
    }
])


def test_first_ask_returns_the_validated_questions(monkeypatch):
    tool = _ask_tool(monkeypatch, previous_asked=False)
    result = json.loads(asyncio.run(tool.ainvoke({"questions": _VALID})))
    assert "error" not in result
    assert result["questions"][0]["header"] == "Time range"


def test_second_ask_in_a_row_returns_an_error_not_questions(monkeypatch):
    tool = _ask_tool(monkeypatch, previous_asked=True)
    result = json.loads(asyncio.run(tool.ainvoke({"questions": _VALID})))
    assert "questions" not in result
    assert "error" in result
    assert "already asked" in result["error"].lower()


def test_error_payload_matches_the_shape_of_the_other_error_paths(monkeypatch):
    """Same {"error": <str>} contract the model already handles elsewhere."""
    capped = json.loads(asyncio.run(
        _ask_tool(monkeypatch, previous_asked=True).ainvoke({"questions": _VALID})
    ))
    bad_json = json.loads(asyncio.run(
        _ask_tool(monkeypatch, previous_asked=False).ainvoke({"questions": "not json"})
    ))
    assert set(capped) == set(bad_json) == {"error"}
    assert isinstance(capped["error"], str) and capped["error"]


# --- pre-existing validation is unchanged ----------------------------------


@pytest.mark.parametrize("payload,fragment", [
    ("not json", "Invalid JSON"),
    (json.dumps([]), "1-4 questions"),
    (json.dumps({"question": "x"}), "1-4 questions"),
])
def test_existing_shape_validation_still_fires(monkeypatch, payload, fragment):
    tool = _ask_tool(monkeypatch, previous_asked=False)
    result = json.loads(asyncio.run(tool.ainvoke({"questions": payload})))
    assert fragment in result["error"]


def test_more_than_four_questions_rejected(monkeypatch):
    tool = _ask_tool(monkeypatch, previous_asked=False)
    five = json.dumps([json.loads(_VALID)[0]] * 5)
    result = json.loads(asyncio.run(tool.ainvoke({"questions": five})))
    assert "1-4 questions" in result["error"]


@pytest.mark.parametrize("n_options", [1, 5])
def test_option_count_validation_still_fires(monkeypatch, n_options):
    tool = _ask_tool(monkeypatch, previous_asked=False)
    q = json.loads(_VALID)[0]
    q["options"] = [{"label": f"o{i}", "description": "d"} for i in range(n_options)]
    result = json.loads(asyncio.run(tool.ainvoke({"questions": json.dumps([q])})))
    assert "2-4 options" in result["error"]


def test_missing_question_text_still_rejected(monkeypatch):
    tool = _ask_tool(monkeypatch, previous_asked=False)
    q = json.loads(_VALID)[0]
    q["question"] = "   "
    result = json.loads(asyncio.run(tool.ainvoke({"questions": json.dumps([q])})))
    assert "'question' field is required" in result["error"]


def test_the_cap_is_checked_before_payload_validation(monkeypatch):
    """A capped call reports the cap even when the payload is also malformed —
    proves the gate is in the tool body, ahead of the parse."""
    tool = _ask_tool(monkeypatch, previous_asked=True)
    result = json.loads(asyncio.run(tool.ainvoke({"questions": "not json"})))
    assert "already asked" in result["error"].lower()
