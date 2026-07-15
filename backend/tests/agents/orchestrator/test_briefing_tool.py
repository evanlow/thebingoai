import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from backend.agents.orchestrator.orchestrator_briefing_tool import build_briefing_tools
from backend.agents.context import AgentContext


def _ctx():
    return AgentContext(
        user_id="u1",
        available_connections=[],
        connection_metadata=[],
        thread_id="t1",
    )


def test_emit_briefing_validates_payload():
    captured = {}

    def fake_factory():
        s = MagicMock()
        s.query.return_value.filter.return_value.first.return_value = MagicMock(
            id=42, user_id="u1", dashboard_id=1, status="generating"
        )
        captured["session"] = s
        return s

    tools = build_briefing_tools(_ctx(), db_session_factory=fake_factory, briefing_id=42)
    emit = next(t for t in tools if t.name == "emit_briefing")

    bad_payload = {"headline": "x", "deck": "y", "kpis": [], "sections": [], "key_takeaways": []}
    result = asyncio.run(emit.ainvoke({"payload": bad_payload}))
    assert "invalid" in result.lower() or "error" in result.lower()


def test_emit_briefing_persists_valid_payload():
    persisted = {}

    def fake_factory():
        s = MagicMock()
        briefing = MagicMock(id=42, user_id="u1", dashboard_id=1, status="generating", payload=None)
        s.query.return_value.filter.return_value.first.return_value = briefing
        persisted["briefing"] = briefing
        return s

    tools = build_briefing_tools(_ctx(), db_session_factory=fake_factory, briefing_id=42)
    emit = next(t for t in tools if t.name == "emit_briefing")

    good = {
        "headline": "Revenue held",
        "deck": "Topline tracked.",
        "kpis": [{"label": "MRR", "value": "$13,816"}],
        "sections": [{"heading": "1. Lift", "prose": "Strong."}],
        "key_takeaways": ["a", "b", "c"],
    }
    with patch("backend.agents.orchestrator.orchestrator_briefing_tool._post_chat_message") as post_msg, \
         patch("backend.agents.orchestrator.orchestrator_briefing_tool._emit_ws") as emit_ws:
        result = asyncio.run(emit.ainvoke({"payload": good}))

    assert "ready" in result.lower() or "ok" in result.lower()
    assert persisted["briefing"].status == "ready"
    assert persisted["briefing"].payload["headline"] == "Revenue held"
    post_msg.assert_called_once()
    emit_ws.assert_called_once()


def test_emit_briefing_persists_recommended_actions():
    persisted = {}

    def fake_factory():
        s = MagicMock()
        briefing = MagicMock(id=42, user_id="u1", dashboard_id=1, status="generating", payload=None)
        s.query.return_value.filter.return_value.first.return_value = briefing
        persisted["briefing"] = briefing
        return s

    tools = build_briefing_tools(_ctx(), db_session_factory=fake_factory, briefing_id=42)
    emit = next(t for t in tools if t.name == "emit_briefing")

    good = {
        "headline": "Revenue held",
        "deck": "Topline tracked.",
        "kpis": [],
        "sections": [{"heading": "1. Lift", "prose": "Strong."}],
        "key_takeaways": ["a", "b", "c"],
        "recommended_actions": ["Ship the fix", "Review pricing"],
    }
    with patch("backend.agents.orchestrator.orchestrator_briefing_tool._post_chat_message"), \
         patch("backend.agents.orchestrator.orchestrator_briefing_tool._emit_ws"):
        result = asyncio.run(emit.ainvoke({"payload": good}))

    assert "ready" in result.lower()
    assert persisted["briefing"].payload["recommended_actions"] == ["Ship the fix", "Review pricing"]


_DASHBOARD_WIDGETS = [
    {"id": "chart_x", "widget": {"type": "chart", "title": "Revenue"}},
    {"id": "flt_region", "widget": {"type": "filter", "title": "Region"}},
]


def _factory_with_dashboard(persisted: dict):
    """Every lookup (briefing, dashboard, user) resolves to one truthy mock, so the
    snapshot block runs and reads `.widgets` off it."""
    def fake_factory():
        s = MagicMock()
        row = MagicMock(
            id=42, user_id="u1", dashboard_id=1, status="generating", payload=None,
            widgets=_DASHBOARD_WIDGETS,
        )
        s.query.return_value.filter.return_value.first.return_value = row
        persisted["briefing"] = row
        return s
    return fake_factory


def test_emit_briefing_injects_widget_snapshots():
    persisted = {}
    tools = build_briefing_tools(
        _ctx(), db_session_factory=_factory_with_dashboard(persisted), briefing_id=42
    )
    emit = next(t for t in tools if t.name == "emit_briefing")

    good = {
        "headline": "Revenue held",
        "deck": "Topline tracked.",
        "kpis": [],
        "sections": [
            {"heading": "1. Lift", "prose": "Strong.", "widget_id": "chart_x"},
            {"heading": "2. No widget", "prose": "Text only."},
        ],
        "key_takeaways": ["a", "b", "c"],
    }
    render = AsyncMock(return_value={"chart_x": {"series": [1, 2]}})
    with patch("backend.agents.orchestrator.orchestrator_briefing_tool._post_chat_message"), \
         patch("backend.agents.orchestrator.orchestrator_briefing_tool._emit_ws"), \
         patch("backend.api.widget_data.render_widget_snapshots", render):
        result = asyncio.run(emit.ainvoke({"payload": good}))

    assert "ready" in result.lower()
    # Only the referenced widget id is passed to the renderer.
    assert render.await_args.args[1] == ["chart_x"]
    assert persisted["briefing"].payload["widget_snapshots"] == {"chart_x": {"series": [1, 2]}}


def test_emit_briefing_drops_sections_pointing_at_a_filter_widget():
    """The prompt catalog hides filter widgets, but analyze_dashboard still shows them,
    so emit_briefing is the enforcing end: a filter reference is stripped, not rendered."""
    persisted = {}
    tools = build_briefing_tools(
        _ctx(), db_session_factory=_factory_with_dashboard(persisted), briefing_id=42
    )
    emit = next(t for t in tools if t.name == "emit_briefing")

    payload = {
        "headline": "Revenue held",
        "deck": "Topline tracked.",
        "kpis": [],
        "sections": [
            {"heading": "1. Lift", "prose": "Strong.", "widget_id": "chart_x"},
            {"heading": "2. Region", "prose": "Mixed.", "widget_id": "flt_region"},
        ],
        "key_takeaways": ["a", "b", "c"],
    }
    render = AsyncMock(return_value={"chart_x": {"series": [1, 2]}})
    with patch("backend.agents.orchestrator.orchestrator_briefing_tool._post_chat_message"), \
         patch("backend.agents.orchestrator.orchestrator_briefing_tool._emit_ws"), \
         patch("backend.api.widget_data.render_widget_snapshots", render):
        result = asyncio.run(emit.ainvoke({"payload": payload}))

    assert "ready" in result.lower()
    sections = persisted["briefing"].payload["sections"]
    assert sections[0]["widget_id"] == "chart_x"
    assert sections[1]["widget_id"] is None  # filter reference stripped
    assert render.await_args.args[1] == ["chart_x"]  # and never snapshotted
