"""Tests for backend.services.data_plane_service.get_default_plane."""
import uuid

import pytest

from backend.data_plane.local_filesystem import LocalFilesystemDataPlane
from backend.data_plane.scope import OwnerScope
from backend.models.data_plane import DataPlaneModel
from backend.models.organization import Organization
from backend.models.team import Team
from backend.models.user import User
from backend.services.data_plane_service import _scope_chain, get_default_plane


@pytest.fixture(autouse=True)
def _clear_local_plane_cache():
    """The plane cache is a module global — reset it around each test for isolation."""
    import backend.services.data_plane_service as svc
    svc._local_plane_cache.clear()
    yield
    svc._local_plane_cache.clear()


@pytest.fixture
def org(db_session):
    o = Organization(id=str(uuid.uuid4()), name=f"org-{uuid.uuid4()}")
    db_session.add(o)
    db_session.commit()
    return o


@pytest.fixture
def org_user(db_session, org):
    u = User(
        id=str(uuid.uuid4()),
        email=f"u-{uuid.uuid4()}@example.com",
        auth_provider="sso",
        org_id=org.id,
    )
    db_session.add(u)
    db_session.commit()
    return u


@pytest.fixture
def org_team(db_session, org):
    t = Team(id=str(uuid.uuid4()), name=f"team-{uuid.uuid4()}", org_id=org.id)
    db_session.add(t)
    db_session.commit()
    return t


def _make_plane(db, scope_kind, scope_id, plane_type="local_filesystem", is_default=True, config=None):
    row = DataPlaneModel(
        id=str(uuid.uuid4()),
        owner_scope_kind=scope_kind,
        owner_scope_id=scope_id,
        type=plane_type,
        config=config or {"root_path": f"/tmp/plane-{uuid.uuid4()}"},
        is_default=is_default,
    )
    db.add(row)
    db.commit()
    return row


def test_scope_chain_user_with_org(db_session, org_user, org):
    chain = _scope_chain(OwnerScope("user", org_user.id), db_session)
    assert chain == [OwnerScope("user", org_user.id), OwnerScope("org", org.id)]


def test_scope_chain_team_with_org(db_session, org_team, org):
    chain = _scope_chain(OwnerScope("team", org_team.id), db_session)
    assert chain == [OwnerScope("team", org_team.id), OwnerScope("org", org.id)]


def test_scope_chain_orphan_user(db_session):
    """User without org_id has only itself in the chain."""
    u = User(id=str(uuid.uuid4()), email=f"orphan-{uuid.uuid4()}@example.com", auth_provider="sso")
    db_session.add(u)
    db_session.commit()
    assert _scope_chain(OwnerScope("user", u.id), db_session) == [OwnerScope("user", u.id)]


def test_scope_chain_org_terminal(db_session, org):
    assert _scope_chain(OwnerScope("org", org.id), db_session) == [OwnerScope("org", org.id)]


def test_get_default_plane_org_hit(db_session, org):
    _make_plane(db_session, "org", org.id)
    plane = get_default_plane(OwnerScope("org", org.id), db_session)
    assert isinstance(plane, LocalFilesystemDataPlane)


def test_user_falls_back_to_org_plane(db_session, org_user, org):
    """User scope without a user-level plane row should use the org plane."""
    org_row = _make_plane(db_session, "org", org.id, config={"root_path": "/tmp/org-plane"})

    plane = get_default_plane(OwnerScope("user", org_user.id), db_session)

    assert isinstance(plane, LocalFilesystemDataPlane)
    assert plane.root_path == org_row.config["root_path"]


def test_team_falls_back_to_org_plane(db_session, org_team, org):
    org_row = _make_plane(db_session, "org", org.id, config={"root_path": "/tmp/org-team-fallback"})

    plane = get_default_plane(OwnerScope("team", org_team.id), db_session)

    assert isinstance(plane, LocalFilesystemDataPlane)
    assert plane.root_path == org_row.config["root_path"]


def test_user_plane_wins_over_org(db_session, org_user, org):
    """When both user and org planes exist, user-scope wins."""
    _make_plane(db_session, "org", org.id, config={"root_path": "/tmp/org-loser"})
    user_row = _make_plane(db_session, "user", org_user.id, config={"root_path": "/tmp/user-winner"})

    plane = get_default_plane(OwnerScope("user", org_user.id), db_session)

    assert plane.root_path == user_row.config["root_path"]


def test_no_rows_falls_back_to_local(db_session, org_user):
    plane = get_default_plane(OwnerScope("user", org_user.id), db_session)
    assert isinstance(plane, LocalFilesystemDataPlane)


def test_non_default_row_ignored(db_session, org_user, org):
    """is_default=False rows must be skipped even at exact scope match."""
    _make_plane(db_session, "user", org_user.id, is_default=False, config={"root_path": "/tmp/skipped"})
    org_row = _make_plane(db_session, "org", org.id, config={"root_path": "/tmp/org-wins"})

    plane = get_default_plane(OwnerScope("user", org_user.id), db_session)

    assert plane.root_path == org_row.config["root_path"]


# ── LocalFilesystemDataPlane instance caching ──────────────────────────────

def test_instantiate_caches_plane_by_root(db_session, org):
    """Two resolutions of the same DB-backed local plane return the SAME instance."""
    _make_plane(db_session, "org", org.id, config={"root_path": "/tmp/cache-me"})
    first = get_default_plane(OwnerScope("org", org.id), db_session)
    second = get_default_plane(OwnerScope("org", org.id), db_session)
    assert first is second  # cached, not a fresh DuckDB connection each call


def test_no_row_fallback_caches_plane_by_root(db_session, org_user):
    """The no-row local fallback also returns a cached instance across calls."""
    first = get_default_plane(OwnerScope("user", org_user.id), db_session)
    second = get_default_plane(OwnerScope("user", org_user.id), db_session)
    assert first is second


def test_cache_separates_distinct_roots(db_session):
    """Different root_paths must map to different cached instances."""
    import uuid as _uuid
    from backend.models.organization import Organization

    o1 = Organization(id=str(_uuid.uuid4()), name=f"org-{_uuid.uuid4()}")
    o2 = Organization(id=str(_uuid.uuid4()), name=f"org-{_uuid.uuid4()}")
    db_session.add_all([o1, o2])
    db_session.commit()
    _make_plane(db_session, "org", o1.id, config={"root_path": "/tmp/root-a"})
    _make_plane(db_session, "org", o2.id, config={"root_path": "/tmp/root-b"})

    plane_a = get_default_plane(OwnerScope("org", o1.id), db_session)
    plane_b = get_default_plane(OwnerScope("org", o2.id), db_session)
    assert plane_a is not plane_b
