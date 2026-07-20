"""Shared-sample hardening tests (PR #144 review follow-ups).

Covers: the sample is unreachable through the dataset-cancellation endpoint,
read paths resolve it for any user via `readable_connection_clause`, and
`ensure_shared_sample` retires legacy per-user sample rows and stays
idempotent under the session-level advisory lock.

Also pins the security-critical access paths opened up by the shared sample —
POST /api/chat, the two websocket helpers, POST /connections/{id}/query, and
the read-only mutation guard. Each has a positive case (any user reaches the
sample) and a negative case (a foreign connection stays unreachable), so a
predicate that widens or narrows fails here.
"""
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from backend.auth.dependencies import get_current_user
from backend.database.session import get_db
from backend.main import app
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


# ── POST /api/chat connection validation ────────────────────────────────────

@pytest.fixture
def chat_client(db_session, sample_user):
    """`authenticated_client` plus the detached-read session chat.py depends on.

    chat.py is the only module using `get_detached_read_db`, which binds to the
    production engine — without this override the handler reads a different
    database than the fixtures write to and every lookup misses.
    """
    from backend.database.session import get_detached_read_db

    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: sample_user
    app.dependency_overrides[get_detached_read_db] = lambda: db_session
    try:
        with TestClient(app) as client:
            client.headers.update({"Authorization": "Bearer test-token"})
            yield client
    finally:
        app.dependency_overrides.clear()


def _patch_orchestrator(monkeypatch):
    """Stub the orchestrator so a chat request stops at the access check.

    Returns the list the handler passed on as `connection_ids`, so a test can
    assert the sample survived validation rather than only that nothing 403'd.
    """
    from backend.services.heartbeat_context import OrchestratorInvocationContext
    from backend.agents.context import AgentContext

    forwarded = []

    async def _ctx(**kwargs):
        forwarded.append(kwargs.get("connection_ids"))
        return OrchestratorInvocationContext(
            agent_context=AgentContext(user_id="u", available_connections=[]),
        )

    async def _run(**kwargs):
        return {"message": "ok", "metadata": {}, "success": True}

    monkeypatch.setattr(
        "backend.services.heartbeat_context.build_orchestrator_context", _ctx,
    )
    monkeypatch.setattr("backend.agents.run_orchestrator", _run)
    monkeypatch.setattr(
        "backend.agents.profile_llm.resolve_published_llm",
        lambda profile: (None, None, None),
    )
    monkeypatch.setattr(
        "backend.services.token_tracking_service.TokenTrackingService.track_usage",
        MagicMock(),
    )
    return forwarded


def test_chat_accepts_shared_sample_connection(monkeypatch, chat_client, shared_sample):
    forwarded = _patch_orchestrator(monkeypatch)
    resp = chat_client.post(
        "/api/chat", json={"message": "hi", "connection_ids": [shared_sample.id]},
    )
    assert resp.status_code == 200
    assert forwarded == [[shared_sample.id]]


def test_chat_rejects_foreign_connection(monkeypatch, chat_client, db_session, other_user):
    _patch_orchestrator(monkeypatch)
    foreign = _make_connection(db_session, user_id=other_user.id, name="foreign")

    resp = chat_client.post(
        "/api/chat", json={"message": "hi", "connection_ids": [foreign.id]},
    )
    assert resp.status_code == 403


# ── websocket chat helpers ──────────────────────────────────────────────────

class _Collector:
    """Stand-in for the websocket `send` callable."""

    def __init__(self):
        self.frames = []

    async def __call__(self, frame):
        self.frames.append(frame)


@pytest.mark.asyncio
async def test_ws_resolve_conversation_accepts_shared_sample(db_session, sample_user, shared_sample):
    from backend.api.websocket import _resolve_conversation

    send = _Collector()
    conversation, _ = await _resolve_conversation(
        db_session, sample_user, None, [shared_sample.id], send, "req-1",
    )
    assert conversation is not None
    assert send.frames == []


@pytest.mark.asyncio
async def test_ws_resolve_conversation_rejects_foreign_connection(
    db_session, sample_user, other_user,
):
    from backend.api.websocket import _resolve_conversation

    foreign = _make_connection(db_session, user_id=other_user.id, name="foreign")
    send = _Collector()
    conversation, _ = await _resolve_conversation(
        db_session, sample_user, None, [foreign.id], send, "req-1",
    )
    assert conversation is None
    assert send.frames[-1]["type"] == "chat.error"


def test_ws_dataset_file_content_resolves_shared_sample(db_session, sample_user, shared_sample):
    from backend.api.websocket import _build_dataset_file_content

    out = _build_dataset_file_content(db_session, sample_user, shared_sample.id)
    assert out is not None
    assert out["file_id"] == f"connection:{shared_sample.id}"


def test_ws_dataset_file_content_rejects_foreign_connection(db_session, sample_user, other_user):
    from backend.api.websocket import _build_dataset_file_content

    foreign = _make_connection(db_session, user_id=other_user.id, name="foreign")
    assert _build_dataset_file_content(db_session, sample_user, foreign.id) is None


# ── POST /api/connections/{id}/query ────────────────────────────────────────

def _patch_connector(monkeypatch):
    from backend.connectors.base import QueryResult

    connector = MagicMock()
    connector.execute_query.return_value = QueryResult(
        columns=["n"], rows=[(1,)], row_count=1, execution_time_ms=1.0,
    )
    monkeypatch.setattr(
        "backend.connectors.factory.get_connector_for_connection", lambda c: connector,
    )
    return connector


def test_sql_query_reaches_shared_sample_by_id(monkeypatch, authenticated_client, shared_sample):
    _patch_connector(monkeypatch)
    resp = authenticated_client.post(
        f"/api/connections/{shared_sample.id}/query", json={"sql": "SELECT 1"},
    )
    assert resp.status_code == 200
    assert resp.json()["row_count"] == 1


def test_sql_query_reaches_shared_sample_by_uuid(monkeypatch, authenticated_client, shared_sample):
    # The uuid branch builds its filter separately from the numeric-id branch.
    _patch_connector(monkeypatch)
    resp = authenticated_client.post(
        f"/api/connections/{shared_sample.uuid}/query", json={"sql": "SELECT 1"},
    )
    assert resp.status_code == 200


def test_sql_query_rejects_foreign_connection(
    monkeypatch, authenticated_client, db_session, other_user,
):
    _patch_connector(monkeypatch)
    foreign = _make_connection(db_session, user_id=other_user.id, name="foreign")

    resp = authenticated_client.post(
        f"/api/connections/{foreign.id}/query", json={"sql": "SELECT 1"},
    )
    assert resp.status_code == 404


# ── the shared sample is read-only ──────────────────────────────────────────

# The generic governance check also answers 403 for a non-owner, so asserting
# the status alone would still pass with the sample guard deleted. Pin the
# detail string — only the sample guard produces it.
READ_ONLY_DETAIL = "The shared sample connection is read-only"


def test_update_connection_rejects_shared_sample(authenticated_client, db_session, shared_sample):
    resp = authenticated_client.put(
        f"/api/connections/{shared_sample.id}", json={"name": "renamed"},
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == READ_ONLY_DETAIL
    db_session.refresh(shared_sample)
    assert shared_sample.name == seed.SAMPLE_CONNECTION_NAME


def test_delete_connection_rejects_shared_sample(authenticated_client, db_session, shared_sample):
    resp = authenticated_client.delete(f"/api/connections/{shared_sample.id}")
    assert resp.status_code == 403
    assert resp.json()["detail"] == READ_ONLY_DETAIL
    assert db_session.get(DatabaseConnection, shared_sample.id) is not None


def test_delete_connection_rejects_shared_sample_for_org_user(
    db_session, sample_user, shared_sample,
):
    # `_find_connection` takes a different branch when the caller has an org_id;
    # the sample must stay visible there and still be refused for mutation.
    from backend.models.organization import Organization

    org_id = str(uuid.uuid4())
    db_session.add(Organization(id=org_id, name="acme"))
    db_session.commit()
    sample_user.org_id = org_id
    db_session.commit()

    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: sample_user
    try:
        with TestClient(app) as client:
            client.headers.update({"Authorization": "Bearer test-token"})
            resp = client.delete(f"/api/connections/{shared_sample.id}")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 403
    assert resp.json()["detail"] == READ_ONLY_DETAIL
    assert db_session.get(DatabaseConnection, shared_sample.id) is not None


# ── GET /api/connections lists the shared sample ────────────────────────────

def _list_ids(client):
    resp = client.get("/api/connections")
    assert resp.status_code == 200
    return {c["id"] for c in resp.json()}


def test_list_connections_includes_shared_sample_for_no_org_user(
    authenticated_client, db_session, sample_user, other_user, shared_sample,
):
    """No-org branch: own connections + the sample, and nothing foreign."""
    own = _make_connection(db_session, user_id=sample_user.id, name="own")
    foreign = _make_connection(db_session, user_id=other_user.id, name="foreign")

    ids = _list_ids(authenticated_client)

    assert shared_sample.id in ids
    assert own.id in ids
    assert foreign.id not in ids


def test_list_connections_includes_shared_sample_for_org_user(
    db_session, sample_user, other_user, shared_sample,
):
    """Org branch is a separate three-way predicate — the sample must survive
    there too, alongside org-mate visibility, without exposing other orgs."""
    from backend.models.organization import Organization

    org_id = str(uuid.uuid4())
    outside_org_id = str(uuid.uuid4())
    # organizations.name is unique and other tests in this module seed orgs too
    # — derive the names from the ids so runs never collide.
    db_session.add_all([
        Organization(id=org_id, name=f"home-{org_id}"),
        Organization(id=outside_org_id, name=f"outside-{outside_org_id}"),
    ])
    db_session.commit()
    sample_user.org_id = org_id
    other_user.org_id = outside_org_id
    db_session.commit()

    mate = _make_connection(db_session, user_id=sample_user.id, name="mate")
    outsider = _make_connection(db_session, user_id=other_user.id, name="outsider")

    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: sample_user
    try:
        with TestClient(app) as client:
            client.headers.update({"Authorization": "Bearer test-token"})
            ids = _list_ids(client)
    finally:
        app.dependency_overrides.clear()

    assert shared_sample.id in ids
    assert mate.id in ids
    assert outsider.id not in ids
