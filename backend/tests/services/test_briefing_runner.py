import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from backend.services import briefing_runner


class _FakeCreditMgr:
    """Stand-in for CreditContextManager: records the kwargs on a clean,
    non-voided exit so a test can assert whether a credit was charged."""

    recorded: list = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.voided = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None and not self.voided:
            _FakeCreditMgr.recorded.append(self.kwargs)
        return False

    def void(self, reason: str = ""):
        self.voided = True


def test_run_returns_failed_status_when_orchestrator_raises():
    briefing = MagicMock(id=1, user_id="u1", dashboard_id=10, status="generating", error=None)
    user = MagicMock(id="u1")
    dashboard = MagicMock(id=10, title="Sales", date_range_from=None, date_range_to=None)

    db = MagicMock()
    queries = {"Briefing": briefing, "Dashboard": dashboard, "User": user}
    def query_side_effect(model):
        q = MagicMock()
        q.filter.return_value.first.return_value = queries.get(model.__name__)
        return q
    db.query.side_effect = query_side_effect

    with patch("backend.services.briefing_runner.SessionLocal", return_value=db), \
         patch("backend.services.briefing_runner.build_orchestrator_context", new=AsyncMock(side_effect=RuntimeError("boom"))):
        asyncio.run(briefing_runner.run(briefing_id=1))

    assert briefing.status == "failed"
    assert "boom" in (briefing.error or "")


def test_run_invokes_orchestrator_with_briefing_context():
    briefing = MagicMock(id=1, user_id="u1", dashboard_id=10, status="generating")
    dashboard = MagicMock(id=10, title="Sales", date_range_from=None, date_range_to=None)
    user = MagicMock(id="u1")

    db = MagicMock()
    queries = {"Briefing": briefing, "Dashboard": dashboard, "User": user}
    def query_side_effect(model):
        q = MagicMock()
        q.filter.return_value.first.return_value = queries.get(model.__name__)
        return q
    db.query.side_effect = query_side_effect

    fake_ctx = MagicMock(agent_context=MagicMock(), custom_agents=None,
                         memory_context="", user_skills=None,
                         user_memories_context="", soul_prompt="", skill_suggestions=None,
                         profile=MagicMock())

    async def fake_orch(**kwargs):
        briefing.status = "ready"
        return {"success": True}

    with patch("backend.services.briefing_runner.SessionLocal", return_value=db), \
         patch("backend.services.briefing_runner.build_orchestrator_context", new=AsyncMock(return_value=fake_ctx)) as build_ctx, \
         patch("backend.services.briefing_runner.run_orchestrator", new=AsyncMock(side_effect=fake_orch)) as run_orch, \
         patch("backend.agents.profile_llm.resolve_published_llm", return_value=(None, None, None)), \
         patch("backend.plugins.loader.get_loaded_plugins", return_value=set()), \
         patch("backend.services.token_tracking_service.CreditContextManager", _FakeCreditMgr):
        asyncio.run(briefing_runner.run(briefing_id=1))

    assert build_ctx.await_count == 1
    assert run_orch.await_count == 1
    assert fake_ctx.agent_context.briefing_id == 1


def test_run_records_one_credit_on_success():
    _FakeCreditMgr.recorded = []
    briefing = MagicMock(id=1, user_id="u1", dashboard_id=10, status="generating")
    dashboard = MagicMock(id=10, title="Sales", date_range_from=None, date_range_to=None)
    user = MagicMock(id="u1")

    db = MagicMock()
    queries = {"Briefing": briefing, "Dashboard": dashboard, "User": user}
    def qse(model):
        q = MagicMock()
        q.filter.return_value.first.return_value = queries.get(model.__name__)
        return q
    db.query.side_effect = qse

    fake_ctx = MagicMock(agent_context=MagicMock(), custom_agents=None,
                         memory_context="", user_skills=None,
                         user_memories_context="", soul_prompt="",
                         skill_suggestions=None, profile=MagicMock())

    async def fake_orch(**kwargs):
        briefing.status = "ready"  # simulate emit_briefing
        return {"success": True}

    with patch("backend.services.briefing_runner.SessionLocal", return_value=db), \
         patch("backend.services.briefing_runner.build_orchestrator_context", new=AsyncMock(return_value=fake_ctx)), \
         patch("backend.services.briefing_runner.run_orchestrator", new=AsyncMock(side_effect=fake_orch)), \
         patch("backend.agents.profile_llm.resolve_published_llm", return_value=(None, None, None)), \
         patch("backend.plugins.loader.get_loaded_plugins", return_value=set()), \
         patch("backend.services.token_tracking_service.CreditContextManager", _FakeCreditMgr):
        asyncio.run(briefing_runner.run(briefing_id=1))

    assert len(_FakeCreditMgr.recorded) == 1
    assert _FakeCreditMgr.recorded[0]["title"] == "Briefing: Sales"
    assert _FakeCreditMgr.recorded[0]["user_id"] == "u1"


def test_run_voids_credit_when_payload_not_emitted():
    _FakeCreditMgr.recorded = []
    briefing = MagicMock(id=1, user_id="u1", dashboard_id=10, status="generating")
    dashboard = MagicMock(id=10, title="Sales", date_range_from=None, date_range_to=None)
    user = MagicMock(id="u1")

    db = MagicMock()
    queries = {"Briefing": briefing, "Dashboard": dashboard, "User": user}
    def qse(model):
        q = MagicMock()
        q.filter.return_value.first.return_value = queries.get(model.__name__)
        return q
    db.query.side_effect = qse

    fake_ctx = MagicMock(agent_context=MagicMock(), custom_agents=None,
                         memory_context="", user_skills=None,
                         user_memories_context="", soul_prompt="",
                         skill_suggestions=None, profile=MagicMock())

    # Orchestrator returns but leaves status == "generating" (never emitted).
    with patch("backend.services.briefing_runner.SessionLocal", return_value=db), \
         patch("backend.services.briefing_runner.build_orchestrator_context", new=AsyncMock(return_value=fake_ctx)), \
         patch("backend.services.briefing_runner.run_orchestrator", new=AsyncMock(return_value={"success": True})), \
         patch("backend.agents.profile_llm.resolve_published_llm", return_value=(None, None, None)), \
         patch("backend.plugins.loader.get_loaded_plugins", return_value=set()), \
         patch("backend.services.token_tracking_service.CreditContextManager", _FakeCreditMgr):
        asyncio.run(briefing_runner.run(briefing_id=1))

    assert briefing.status == "failed"
    assert _FakeCreditMgr.recorded == []  # voided → no charge
