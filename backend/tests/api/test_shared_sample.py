"""Shared-sample hardening tests (PR #144 review follow-ups).

Covers: the sample is unreachable through the dataset-cancellation endpoint,
read paths resolve it for any user via `readable_connection_clause`, and
`ensure_shared_sample` retires legacy per-user sample rows and stays
idempotent under the session-level advisory lock.
"""
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from backend.models.database_connection import DatabaseConnection
from backend.services import seed


def _ensure_samples_org(db):
    from backend.models.organization import Organization
    from backend.models.user import User

    if db.get(Organization, seed.SAMPLES_ORG_ID) is None:
        db.add(Organization(id=seed.SAMPLES_ORG_ID, name="Bingo Samples"))
        db.commit()
    if db.get(User, seed.SAMPLES_USER_ID) is None:
        db.add(User(
            id=seed.SAMPLES_USER_ID,
            email=seed.SAMPLES_USER_EMAIL,
            auth_provider="system",
            org_id=seed.SAMPLES_ORG_ID,
        ))
        db.commit()


def _make_connection(db, *, user_id, marker=None, shared=False, name="conn"):
    conn = DatabaseConnection(
        user_id=user_id,
        org_id=seed.SAMPLES_ORG_ID if shared else None,
        owner_scope_kind="org" if shared else "user",
        owner_scope_id=seed.SAMPLES_ORG_ID if shared else user_id,
        name=name,
        db_type="sqlite",
        host="internal",
        port=0,
        database="sqlite",
        username="sqlite",
        source_filename=marker,
        dataset_table_name=seed.SAMPLE_DB_PATH,
    )
    conn.password = "sqlite"
    conn.ssl_ca_cert = None
    db.add(conn)
    db.commit()
    db.refresh(conn)
    return conn


@pytest.fixture
def shared_sample(db_session):
    _ensure_samples_org(db_session)
    return _make_connection(
        db_session,
        user_id=seed.SAMPLES_USER_ID,
        marker=seed.SAMPLE_SOURCE_MARKER,
        shared=True,
        name=seed.SAMPLE_CONNECTION_NAME,
    )


# ── cancel_dataset must never delete the shared sample ─────────────────────

def test_cancel_dataset_cannot_reach_shared_sample(authenticated_client, db_session, shared_sample):
    resp = authenticated_client.delete(f"/api/chat/files/connection:{shared_sample.id}/dataset")
    assert resp.status_code == 404
    assert db_session.get(DatabaseConnection, shared_sample.id) is not None


def test_cancel_dataset_rejects_sample_even_when_owned(authenticated_client, db_session, sample_user):
    # Defense-in-depth guard: a row that is both owned and sample-scoped
    # still must not be deletable.
    _ensure_samples_org(db_session)
    conn = _make_connection(
        db_session, user_id=sample_user.id, marker=seed.SAMPLE_SOURCE_MARKER, shared=True,
    )
    resp = authenticated_client.delete(f"/api/chat/files/connection:{conn.id}/dataset")
    assert resp.status_code == 403
    assert db_session.get(DatabaseConnection, conn.id) is not None


# ── readable_connection_clause ──────────────────────────────────────────────

def test_readable_clause_scopes_reads(db_session, sample_user, other_user, shared_sample):
    own = _make_connection(db_session, user_id=sample_user.id, name="own")
    foreign = _make_connection(db_session, user_id=other_user.id, name="foreign")

    ids = {
        r.id for r in db_session.query(DatabaseConnection.id)
        .filter(seed.readable_connection_clause(sample_user.id)).all()
    }
    assert shared_sample.id in ids
    assert own.id in ids
    assert foreign.id not in ids


def test_execute_query_resolves_shared_sample_for_non_owner(monkeypatch, db_session, shared_sample):
    import backend.agents.data_agent.tools as tools
    from backend.agents.context import AgentContext
    from backend.connectors.base import QueryResult

    ctx = AgentContext(user_id=str(uuid.uuid4()), available_connections=[shared_sample.id])
    qr = QueryResult(columns=["c"], rows=[(1,)], row_count=1, execution_time_ms=1.0)

    monkeypatch.setattr("backend.agents.data_agent.tools.SessionLocal", lambda: db_session)
    monkeypatch.setattr(
        "backend.agents.data_agent.tools._serve_query_via_dataplane",
        lambda conn, sql, db: qr,
    )
    monkeypatch.setattr("backend.agents.data_agent.tools.store_query_result", MagicMock())
    monkeypatch.setattr("backend.agents.data_agent.tools.publish_query_result", MagicMock())

    tools_list = tools.build_data_agent_tools(ctx)
    exec_tool = next(t for t in tools_list if t.name == "execute_query")
    out = exec_tool.invoke({"connection_id": shared_sample.id, "sql": "SELECT 1"})

    assert "error" not in out
    assert out["row_count"] == 1


# ── ensure_shared_sample provisioning ───────────────────────────────────────

def _patch_provisioning(monkeypatch):
    monkeypatch.setattr(seed.os.path, "isfile", lambda p: True)
    monkeypatch.setattr(
        "backend.services.data_plane_service.get_plane_for_connection",
        lambda c: (MagicMock(), MagicMock()),
    )
    monkeypatch.setattr(
        "backend.migration.substrate.migrate_connection",
        lambda cid, db=None, **kw: SimpleNamespace(
            status="migrated", new_dataplane_table="airbnb", rows_migrated=0,
            error_message=None, legacy_blob_path=None,
        ),
    )


def test_ensure_shared_sample_retires_legacy_per_user_rows(monkeypatch, db_session, sample_user):
    from backend.models.dashboard import Dashboard

    _ensure_samples_org(db_session)
    legacy = _make_connection(
        db_session, user_id=sample_user.id, marker=seed.SAMPLE_SOURCE_MARKER,
        name=seed.SAMPLE_CONNECTION_NAME,
    )
    dash = Dashboard(
        user_id=sample_user.id,
        title="legacy sample dash",
        widgets=[{"id": "w1", "dataSource": {"connectionId": legacy.id}}],
    )
    db_session.add(dash)
    db_session.commit()

    _patch_provisioning(monkeypatch)
    seed.ensure_shared_sample(db_session)

    canonical = db_session.query(DatabaseConnection).filter(
        seed.shared_sample_clause(),
        DatabaseConnection.source_filename == seed.SAMPLE_SOURCE_MARKER,
    ).one()
    assert db_session.get(DatabaseConnection, legacy.id) is None
    db_session.refresh(dash)
    assert dash.widgets[0]["dataSource"]["connectionId"] == canonical.id


def test_ensure_shared_sample_retires_legacy_row_with_team_policy(monkeypatch, db_session, sample_user):
    from backend.models.team import Team
    from backend.models.team_connection_policy import TeamConnectionPolicy

    _ensure_samples_org(db_session)
    legacy = _make_connection(
        db_session, user_id=sample_user.id, marker=seed.SAMPLE_SOURCE_MARKER,
        name=seed.SAMPLE_CONNECTION_NAME,
    )
    team = Team(org_id=seed.SAMPLES_ORG_ID, name="legacy-policy-team")
    db_session.add(team)
    db_session.commit()
    db_session.add(TeamConnectionPolicy(team_id=team.id, connection_id=legacy.id))
    db_session.commit()

    _patch_provisioning(monkeypatch)
    seed.ensure_shared_sample(db_session)

    assert db_session.get(DatabaseConnection, legacy.id) is None
    assert db_session.query(TeamConnectionPolicy).filter(
        TeamConnectionPolicy.connection_id == legacy.id
    ).count() == 0


def test_ensure_shared_sample_idempotent(monkeypatch, db_session):
    _patch_provisioning(monkeypatch)
    seed.ensure_shared_sample(db_session)
    seed.ensure_shared_sample(db_session)

    rows = db_session.query(DatabaseConnection).filter(
        seed.shared_sample_clause(),
        DatabaseConnection.source_filename == seed.SAMPLE_SOURCE_MARKER,
    ).all()
    assert len(rows) == 1
