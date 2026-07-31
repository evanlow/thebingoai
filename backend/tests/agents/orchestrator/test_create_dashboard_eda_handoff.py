"""Findings established in chat must survive the handoff to the dashboard agent.

`invoke_dashboard_agent` takes a request string and an `AgentContext` that carries no
messages, so the sub-agent cannot see the conversation. Without `eda_findings` an EDA
turn followed by "now build a dashboard" throws away everything the user just agreed
to and re-derives a generic story from schema stats.
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.agents.context import AgentContext
from backend.agents.orchestrator import orchestrator_dashboard_tools as odt

_FINDINGS = (
    "Attrition is 23.8% overall, concentrated in sales and support. "
    "Low satisfaction is the strongest signal."
)


class _FakeSession:
    """query(...).filter(...).all() returns the readable connection ids."""

    def __init__(self):
        self.closed = False

    def query(self, *a, **k):
        return self

    def filter(self, *a, **k):
        return self

    def all(self):
        return [SimpleNamespace(id=1)]

    def close(self):
        self.closed = True


@pytest.fixture
def inline(monkeypatch):
    """Run _do_create_dashboard on the inline path, capturing the sub-agent request."""
    from backend.config import settings

    monkeypatch.setattr(settings, "agent_mesh_enabled", False, raising=False)
    invoke = AsyncMock(return_value={"success": True, "dashboard_id": 7, "message": "done"})
    monkeypatch.setattr(odt, "invoke_dashboard_agent", invoke)
    monkeypatch.setattr(odt, "_verify_and_retry", AsyncMock(side_effect=lambda r, *a, **k: r))
    monkeypatch.setattr(odt, "_attach_widget_summary", MagicMock())

    async def _run(**kwargs):
        await odt._do_create_dashboard(
            AgentContext(user_id="u1", available_connections=[1]),
            lambda: _FakeSession(),
            **kwargs,
        )
        return invoke.await_args.args[0]

    return _run


@pytest.mark.asyncio
async def test_findings_reach_the_sub_agent(inline):
    request = await _run_ok(inline)
    assert "## Findings already established with the user" in request
    assert "23.8%" in request
    assert "build me a dashboard" in request  # original request preserved


async def _run_ok(inline):
    return await inline(request="build me a dashboard", eda_findings=_FINDINGS)


@pytest.mark.asyncio
async def test_findings_instruct_the_agent_not_to_re_derive(inline):
    request = await _run_ok(inline)
    assert "do not re-derive a generic one" in request
    assert "do not contradict them" in request


@pytest.mark.asyncio
async def test_no_findings_leaves_the_request_byte_identical(inline):
    """A create turn with no prior analysis must behave exactly as before."""
    assert await inline(request="build me a dashboard") == "build me a dashboard"
    assert await inline(request="build me a dashboard", eda_findings="") == "build me a dashboard"


@pytest.mark.asyncio
async def test_findings_reach_the_mesh_peer_too(monkeypatch):
    """The mesh branch dispatches `request` before the inline call site is reached,
    so enrichment has to happen at the top of the function. If someone moves it down
    next to invoke_dashboard_agent, mesh users silently lose the findings.
    """
    from backend.config import settings

    monkeypatch.setattr(settings, "agent_mesh_enabled", True, raising=False)

    bus = MagicMock()
    bus.send_and_wait.return_value = {"success": True, "dashboard_id": 7, "message": "done"}
    monkeypatch.setattr("backend.services.agent_registry.AgentRegistry", MagicMock())
    monkeypatch.setattr("backend.services.agent_discovery.AgentDiscovery", MagicMock(
        return_value=MagicMock(find_session_by_type=MagicMock(return_value={"session_id": "s2"}))
    ))
    monkeypatch.setattr("backend.services.agent_message_bus.AgentMessageBus", MagicMock(return_value=bus))
    monkeypatch.setattr(odt, "_verify_and_retry", AsyncMock(side_effect=lambda r, *a, **k: r))
    monkeypatch.setattr(odt, "_attach_widget_summary", MagicMock())

    await odt._do_create_dashboard(
        AgentContext(user_id="u1", available_connections=[1], session_id="s1"),
        lambda: _FakeSession(),
        request="build me a dashboard",
        eda_findings=_FINDINGS,
    )

    sent = bus.send_and_wait.call_args.kwargs["content"]["text"]
    assert "## Findings already established with the user" in sent
    assert "23.8%" in sent
