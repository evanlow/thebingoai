"""Tests for the onboarding connection-scoping path.

Covers the two pieces that pin the orchestrator to a single connection when the
onboarding first-question flow scopes a turn:

  1. build_orchestrator_context() sets AgentContext.target_connection_id only when
     exactly one connection is in scope (heartbeat_context.py).
  2. ProfileRenderer.render() emits the "Primary connection to use" prompt hint
     only when target_connection_id is set (profile_renderer.py).
"""
from types import SimpleNamespace

import pytest

from backend.models.database_connection import DatabaseConnection
from backend.services.heartbeat_context import build_orchestrator_context
from backend.agents.profile_renderer import ProfileRenderer, RuntimeContext


def _make_conn(db, user, name="conn"):
    """Seed a minimal DatabaseConnection owned by `user`.

    Sets the encrypted-password column directly so the test does not depend on a
    Fernet key — the scoping path only reads id/name/db_type/database.
    """
    c = DatabaseConnection(
        user_id=user.id,
        name=name,
        db_type="postgres",
        host="localhost",
        port=5432,
        database="db",
        username="u",
    )
    c._encrypted_password = "enc"
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


# ── build_orchestrator_context → target_connection_id ──────────────────────

@pytest.mark.asyncio
async def test_single_connection_sets_target(db_session, sample_user):
    conn = _make_conn(db_session, sample_user)

    ctx = await build_orchestrator_context(
        db=db_session, user=sample_user, query="", connection_ids=[conn.id],
    )

    assert ctx.agent_context.target_connection_id == conn.id


@pytest.mark.asyncio
async def test_multiple_connections_leave_target_none(db_session, sample_user):
    c1 = _make_conn(db_session, sample_user, name="a")
    c2 = _make_conn(db_session, sample_user, name="b")

    ctx = await build_orchestrator_context(
        db=db_session, user=sample_user, query="", connection_ids=[c1.id, c2.id],
    )

    assert ctx.agent_context.target_connection_id is None


@pytest.mark.asyncio
async def test_no_scope_leaves_target_none(db_session, sample_user):
    # User owns 2 connections; no explicit scope → all-connections path, no target.
    _make_conn(db_session, sample_user, name="a")
    _make_conn(db_session, sample_user, name="b")

    ctx = await build_orchestrator_context(
        db=db_session, user=sample_user, query="", connection_ids=None,
    )

    assert ctx.agent_context.target_connection_id is None


# ── ProfileRenderer.render → "Primary connection to use" hint ──────────────

def _profile():
    """Minimal profile stand-in: only `identity` set, all other sections None."""
    return SimpleNamespace(
        bootstrap=None,
        identity="You are Bingo.",
        soul=None,
        user_context=None,
        guardrails=None,
        agents=None,
        tools=None,
        heartbeat=None,
    )


def test_render_includes_primary_connection_hint_when_target_set():
    ctx = RuntimeContext(available_connections=[5], target_connection_id=5)

    out = ProfileRenderer.render(_profile(), ctx)

    assert "Primary connection to use: 5" in out


def test_render_omits_hint_when_target_none():
    ctx = RuntimeContext(available_connections=[5], target_connection_id=None)

    out = ProfileRenderer.render(_profile(), ctx)

    assert "Primary connection to use" not in out
