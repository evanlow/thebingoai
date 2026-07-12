"""Guards against duplicate dashboard generation.

Two paths could insert a second Dashboard row in one turn:
  1. `_verify_and_retry` re-invokes the dashboard agent to REPAIR the existing
     dashboard; if the agent ignores the prompt and calls create_dashboard, the
     stray must be deleted (not left alongside the original).
  2. `run_orchestrator`'s Layer-4 judge retry re-runs the whole orchestrator; it
     must be skipped when a dashboard tool already succeeded this turn.
"""
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from backend.agents.orchestrator import orchestrator_dashboard_tools as odt
from backend.agents.orchestrator import graph
from backend.agents.orchestrator.graph import _dashboard_tool_succeeded
from backend.agents.orchestrator.response_judge import JudgeVerdict


def _ai_with_tool_call(tool_name: str, tc_id: str, args: dict) -> AIMessage:
    msg = AIMessage(content="")
    msg.tool_calls = [{"name": tool_name, "id": tc_id, "args": args}]
    return msg


class _FakeSession:
    """Records delete/commit; query().filter().first() returns the stray row."""

    def __init__(self, stray):
        self._stray = stray
        self.deleted = []
        self.committed = False
        self.closed = False

    def query(self, *a, **k):
        return self

    def filter(self, *a, **k):
        return self

    def first(self):
        return self._stray

    def delete(self, obj):
        self.deleted.append(obj)

    def commit(self):
        self.committed = True

    def close(self):
        self.closed = True


# ---------------------------------------------------------------------------
# Fix 1 — _verify_and_retry deletes a stray dashboard the repair agent created
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_verify_and_retry_deletes_stray_dashboard(monkeypatch):
    original_widgets = [{"widget": {"type": "kpi"}}] * 14
    context = SimpleNamespace(user_id="u1")

    monkeypatch.setattr(odt, "_load_dashboard_widgets", lambda *a, **k: original_widgets)
    monkeypatch.setattr(odt, "verify_dashboard_widgets", lambda widgets: ["dup KPI 'Spend'"])
    # Repair agent wrongly CREATES a new dashboard (id 2) instead of updating id 1.
    monkeypatch.setattr(
        odt, "invoke_dashboard_agent",
        AsyncMock(return_value={"success": True, "dashboard_id": 2}),
    )
    stray = object()
    session = _FakeSession(stray)

    result = await odt._verify_and_retry(
        {"success": True, "dashboard_id": 1},
        context,
        db_session_factory=lambda: session,
        target_connection_id=None,
    )

    assert session.deleted == [stray]      # stray row deleted
    assert session.committed is True
    assert result["dashboard_id"] == 1     # original kept
    assert "violations" in result
    assert "structural issues" in result["warning"]


@pytest.mark.asyncio
async def test_verify_and_retry_keeps_row_when_repair_updates_in_place(monkeypatch):
    """Repair returns the SAME id (proper update) → no stray, nothing deleted."""
    context = SimpleNamespace(user_id="u1")
    monkeypatch.setattr(odt, "_load_dashboard_widgets", lambda *a, **k: [{"w": 1}] * 8)
    monkeypatch.setattr(odt, "verify_dashboard_widgets", lambda widgets: ["still bad"])
    invoke = AsyncMock(return_value={"success": True, "dashboard_id": 1})
    monkeypatch.setattr(odt, "invoke_dashboard_agent", invoke)
    session = _FakeSession(object())

    result = await odt._verify_and_retry(
        {"success": True, "dashboard_id": 1},
        context,
        db_session_factory=lambda: session,
        target_connection_id=None,
    )

    assert session.deleted == []           # no stray deleted
    assert result["dashboard_id"] == 1


# ---------------------------------------------------------------------------
# Fix 2 — _dashboard_tool_succeeded predicate
# ---------------------------------------------------------------------------

def test_dashboard_tool_succeeded_true_on_create():
    msgs = [
        _ai_with_tool_call("create_dashboard", "tc1", {}),
        ToolMessage(content=json.dumps({"success": True, "dashboard_id": 7}), tool_call_id="tc1"),
    ]
    assert _dashboard_tool_succeeded(msgs) is True


def test_dashboard_tool_succeeded_false_on_failure():
    msgs = [
        _ai_with_tool_call("create_dashboard", "tc1", {}),
        ToolMessage(content=json.dumps({"success": False}), tool_call_id="tc1"),
    ]
    assert _dashboard_tool_succeeded(msgs) is False


def test_dashboard_tool_succeeded_false_for_non_dashboard_tool():
    msgs = [
        _ai_with_tool_call("run_sql", "tc1", {}),
        ToolMessage(content=json.dumps({"success": True}), tool_call_id="tc1"),
    ]
    assert _dashboard_tool_succeeded(msgs) is False


# ---------------------------------------------------------------------------
# Fix 2 wiring — run_orchestrator skips the judge when a dashboard was created
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_orchestrator_skips_judge_when_dashboard_created(monkeypatch):
    context = SimpleNamespace(user_id="u1", thread_id="t1")
    messages_with_dashboard = [
        HumanMessage(content="build me a dashboard"),
        _ai_with_tool_call("create_dashboard", "tc1", {}),
        ToolMessage(content=json.dumps({"success": True, "dashboard_id": 5}), tool_call_id="tc1"),
        AIMessage(content="Here is your dashboard."),
    ]
    orchestrator = MagicMock()
    orchestrator.ainvoke = AsyncMock(return_value={"messages": messages_with_dashboard})

    monkeypatch.setattr(graph, "build_orchestrator_tools", lambda *a, **k: [])
    monkeypatch.setattr(graph, "_load_profile_if_missing", lambda *a, **k: None)
    monkeypatch.setattr(graph, "_render_orchestrator_prompt", AsyncMock(return_value=""))
    monkeypatch.setattr(graph, "_create_orchestrator_agent", lambda *a, **k: orchestrator)
    monkeypatch.setattr("backend.agents.callbacks.get_callbacks", lambda **k: [])
    monkeypatch.setattr(graph.settings, "judge_enabled", True)
    judge = AsyncMock(return_value=JudgeVerdict(resolved=True, reason="", suggested_directive="", highlighted_response=""))
    monkeypatch.setattr(graph, "judge_response", judge)

    out = await graph.run_orchestrator("build me a dashboard", context)

    assert out["success"] is True
    judge.assert_not_called()   # judge (and its retry) skipped — no duplicate


@pytest.mark.asyncio
async def test_run_orchestrator_runs_judge_when_no_dashboard(monkeypatch):
    """Contrast: without a dashboard tool, the judge still runs."""
    context = SimpleNamespace(user_id="u1", thread_id="t1")
    messages_plain = [
        HumanMessage(content="what is 2+2"),
        AIMessage(content="4"),
    ]
    orchestrator = MagicMock()
    orchestrator.ainvoke = AsyncMock(return_value={"messages": messages_plain})

    monkeypatch.setattr(graph, "build_orchestrator_tools", lambda *a, **k: [])
    monkeypatch.setattr(graph, "_load_profile_if_missing", lambda *a, **k: None)
    monkeypatch.setattr(graph, "_render_orchestrator_prompt", AsyncMock(return_value=""))
    monkeypatch.setattr(graph, "_create_orchestrator_agent", lambda *a, **k: orchestrator)
    monkeypatch.setattr("backend.agents.callbacks.get_callbacks", lambda **k: [])
    monkeypatch.setattr(graph.settings, "judge_enabled", True)
    judge = AsyncMock(return_value=JudgeVerdict(resolved=True, reason="", suggested_directive="", highlighted_response=""))
    monkeypatch.setattr(graph, "judge_response", judge)

    await graph.run_orchestrator("what is 2+2", context)

    judge.assert_called_once()
