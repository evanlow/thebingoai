"""The dashboard-scoping kill switch.

The 2026-03-29 `propose_action_plan` regression is documented, and this feature
can degrade dashboard quality if it misfires, so it must be disableable without
shipping a second migration. Seeded profiles carry the scoping block in their
stored text, so the flag has to strip it from the *rendered* prompt.

The Phase-1 round cap is deliberately NOT gated on the flag: it only prevents
loops and is never the thing you want to turn off.
"""
from __future__ import annotations

import asyncio

import pytest

from backend.agents.context import AgentContext
from backend.agents.orchestrator import graph as graph_mod
from backend.agents.orchestrator_prompt_blocks import (
    ORCHESTRATOR_APPROACH,
    ORCHESTRATOR_ASK_RULES,
    ORCHESTRATOR_DASHBOARD_SCOPING,
)
from backend.config import Settings, settings


def _ctx():
    return AgentContext(
        user_id="u1", available_connections=[], connection_metadata=[], thread_id="t1",
    )


def _render(monkeypatch, *, flag: bool):
    """Render through the legacy (no-profile) path, which composes the chassis."""
    monkeypatch.setattr(settings, "dashboard_scoping_questions", flag, raising=False)
    monkeypatch.setattr(settings, "orchestrator_lean_tools", False, raising=False)
    return asyncio.run(graph_mod._render_orchestrator_prompt(
        None, "build me a dashboard", _ctx(), None, None, None, "", "", "", None, "test",
    ))


# --- the setting itself ----------------------------------------------------


def test_flag_defaults_to_on():
    assert Settings().dashboard_scoping_questions is True


def test_flag_shape_matches_the_surrounding_settings():
    fields = Settings.model_fields
    assert fields["dashboard_scoping_questions"].annotation is bool
    assert fields["orchestrator_lean_tools"].annotation is bool


def test_flag_is_env_overridable():
    assert Settings(dashboard_scoping_questions=False).dashboard_scoping_questions is False


def test_env_example_documents_the_flag():
    import pathlib

    env = pathlib.Path(__file__).resolve().parents[4] / ".env.example"
    if not env.is_file():
        # The backend test container bind-mounts only backend/, alembic/ and
        # data/ — the repo root is absent. Skip rather than false-pass; this
        # runs for real in a repo checkout and in CI.
        pytest.skip(f"{env} not present in this environment")
    assert "DASHBOARD_SCOPING_QUESTIONS=true" in env.read_text()


# --- what the flag does to the rendered prompt -----------------------------


def test_block_is_present_when_the_flag_is_on(monkeypatch):
    assert ORCHESTRATOR_DASHBOARD_SCOPING in _render(monkeypatch, flag=True)


def test_block_is_omitted_when_the_flag_is_off(monkeypatch):
    assert ORCHESTRATOR_DASHBOARD_SCOPING not in _render(monkeypatch, flag=False)


def test_the_four_dimensions_disappear_with_the_block(monkeypatch):
    off = _render(monkeypatch, flag=False)
    for dimension in ("Audience & purpose", "Priority metrics", "Ask only what is still unresolved"):
        assert dimension not in off


def test_turning_it_off_keeps_the_rest_of_the_workflow(monkeypatch):
    """Only the scoping block goes — the agent must still plan and still know
    how ask_user_question behaves."""
    off = _render(monkeypatch, flag=False)
    assert ORCHESTRATOR_APPROACH in off
    assert ORCHESTRATOR_ASK_RULES in off


def test_turning_it_off_leaves_no_ragged_blank_run(monkeypatch):
    assert "\n\n\n" not in _render(monkeypatch, flag=False)


def test_a_seeded_profile_is_stripped_too(monkeypatch):
    """The stored row carries the block; stripping must survive ProfileRenderer."""
    from backend.agents.profile_defaults import DEFAULTS
    from backend.models.agent_profile import AgentProfile

    profile = AgentProfile(
        agent_type="orchestrator",
        identity=DEFAULTS["orchestrator"]["identity"],
        is_active=True,
        version=1,
    )
    monkeypatch.setattr(settings, "dashboard_scoping_questions", False, raising=False)
    monkeypatch.setattr(settings, "orchestrator_lean_tools", False, raising=False)

    async def no_pre_steps(_ctx):
        return None

    monkeypatch.setattr(graph_mod, "run_pre_steps", no_pre_steps)
    rendered = asyncio.run(graph_mod._render_orchestrator_prompt(
        profile, "build me a dashboard", _ctx(), None, None, None, "", "", "", None, "test",
    ))
    assert ORCHESTRATOR_DASHBOARD_SCOPING not in rendered
    assert ORCHESTRATOR_ASK_RULES in rendered


# --- the round cap survives the flip ---------------------------------------


def test_the_round_cap_is_not_gated_on_the_flag(monkeypatch):
    """Turning scoping off must not turn the loop guard off with it."""
    import inspect

    src = inspect.getsource(graph_mod.build_orchestrator_tools)
    assert "_previous_turn_asked_question" in src
    assert "dashboard_scoping_questions" not in src


def test_the_cap_still_fires_with_the_flag_off(monkeypatch):
    import json

    monkeypatch.setattr(settings, "dashboard_scoping_questions", False, raising=False)
    monkeypatch.setattr(settings, "orchestrator_lean_tools", False, raising=False)
    for name in (
        "build_skill_tools", "build_profile_tools", "build_soul_tools",
        "build_dashboard_tools", "build_memory_tools",
    ):
        monkeypatch.setattr(graph_mod, name, lambda *a, **k: [])
    monkeypatch.setattr(graph_mod, "_build_legacy_tools", lambda *a, **k: [])
    monkeypatch.setattr(graph_mod, "_previous_turn_asked_question", lambda *a, **k: True)

    tools = graph_mod.build_orchestrator_tools(_ctx(), db_session_factory=lambda: None)
    ask = next(t for t in tools if t.name == "ask_user_question")
    payload = json.dumps([{
        "question": "q?", "header": "h",
        "options": [{"label": "a", "description": "d"}, {"label": "b", "description": "d"}],
    }])
    result = json.loads(asyncio.run(ask.ainvoke({"questions": payload})))
    assert "already asked" in result["error"].lower()
