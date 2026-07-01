"""Unit tests for account-deletion teardown (tombstone_account).

Verifies the selective teardown: the user row is KEPT (renamed + flagged
is_active=False), and every credit-consuming / scheduled resource is DISABLED
(flag flipped, row kept) rather than deleted. File-based connections, static
agents, and the dashboards themselves are left untouched.
"""
import backend.models  # noqa: F401 — register all mappers for relationship resolution

import pytest
from sqlalchemy import create_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import sessionmaker

from backend.database.base import Base
from backend.models.user import User
from backend.models.organization import Organization
from backend.models.database_connection import DatabaseConnection
from backend.models.heartbeat_job import HeartbeatJob
from backend.models.custom_agent import CustomAgent
from backend.models.dashboard import Dashboard
from backend.models.pipeline import Pipeline
from backend.models.transforms import DbtModel
from backend.services.account_deletion import tombstone_account


# Render Postgres JSONB columns as JSON so the tables build on SQLite.
@compiles(JSONB, "sqlite")
def _jsonb_as_json_sqlite(element, compiler, **kw):  # pragma: no cover - test shim
    return "JSON"


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[
        User.__table__,
        Organization.__table__,
        DatabaseConnection.__table__,
        HeartbeatJob.__table__,
        CustomAgent.__table__,
        Dashboard.__table__,
        Pipeline.__table__,
        DbtModel.__table__,
    ])
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def _make_connection(user_id, db_type, name):
    return DatabaseConnection(
        user_id=user_id, name=name, db_type=db_type,
        host="h", port=5432, database="d", username="u",
        _encrypted_password="x",
    )


def test_tombstone_account_disables_not_deletes(db):
    user = User(id="u1", email="alice@gmail.com", auth_provider="sso", is_active=True)
    db.add(user)

    pg = _make_connection("u1", "postgres", "prod-pg")       # live → disabled
    ds = _make_connection("u1", "dataset", "uploaded.csv")   # file-based → untouched
    db.add_all([pg, ds])

    pipeline = Pipeline(
        owner_scope_kind="user", owner_scope_id="u1",
        source_connection_id=1, target_table="t", name="sync",
        cron="0 * * * *", pipeline_fingerprint="fp1",
        enabled=True, created_by_user_id="u1",
    )
    transform = DbtModel(
        owner_scope_kind="user", owner_scope_id="u1",
        name="rollup", sql="select 1", cron="0 * * * *",
        enabled=True, created_by_user_id="u1",
    )
    hb = HeartbeatJob(
        user_id="u1", name="daily", prompt="p",
        schedule_type="cron", schedule_value="0 9 * * *", cron_expression="0 9 * * *",
        is_active=True,
    )
    auto_agent = CustomAgent(
        user_id="u1", team_id="t1", name="watcher", system_prompt="s",
        tool_keys=[], is_autonomous=True, is_active=True,
    )
    static_agent = CustomAgent(
        user_id="u1", team_id="t1", name="helper", system_prompt="s",
        tool_keys=[], is_autonomous=False, is_active=True,
    )
    dash = Dashboard(
        user_id="u1", title="Sales", widgets=[],
        schedule_type="cron", schedule_value="1h",
        cron_expression="0 * * * *", schedule_active=True,
    )
    db.add_all([pipeline, transform, hb, auto_agent, static_agent, dash])
    db.commit()

    pg_id, ds_id, dash_id = pg.id, ds.id, dash.id
    pipeline_id, transform_id = pipeline.id, transform.id
    hb_id, auto_id, static_id = hb.id, auto_agent.id, static_agent.id

    tombstone_account(db, user, "bingo-1718450000@gmail.com")

    # User row kept, email masked, flagged inactive.
    refreshed = db.query(User).filter_by(id="u1").one()
    assert refreshed.email == "bingo-1718450000@gmail.com"
    assert refreshed.is_active is False

    # Live DB connection kept but disabled; file-based connection untouched.
    assert db.query(DatabaseConnection).filter_by(id=pg_id).one().is_active is False
    assert db.query(DatabaseConnection).filter_by(id=ds_id).one().is_active is True

    # Scheduled / credit-consuming resources kept but disabled.
    assert db.query(Pipeline).filter_by(id=pipeline_id).one().enabled is False
    assert db.query(DbtModel).filter_by(id=transform_id).one().enabled is False
    assert db.query(HeartbeatJob).filter_by(id=hb_id).one().is_active is False
    assert db.query(CustomAgent).filter_by(id=auto_id).one().is_active is False

    # Static agent left enabled.
    assert db.query(CustomAgent).filter_by(id=static_id).one().is_active is True

    # Dashboard kept; only its refresh schedule disabled.
    kept = db.query(Dashboard).filter_by(id=dash_id).one()
    assert kept.schedule_active is False
    assert kept.next_run_at is None


def test_tombstone_account_rejects_empty_email(db):
    user = User(id="u2", email="bob@gmail.com", auth_provider="sso", is_active=True)
    db.add(user)
    db.commit()

    with pytest.raises(ValueError):
        tombstone_account(db, user, "")


def test_tombstone_frees_per_user_org_name(db):
    # per_user_org_signup names the org after the email. Deletion must free that
    # UNIQUE name too, else re-registering the same email collides.
    org = Organization(id="org-1", name="carol@gmail.com")
    db.add(org)
    db.flush()
    user = User(id="u3", email="carol@gmail.com", auth_provider="sso",
                is_active=True, org_id="org-1")
    db.add(user)
    db.commit()

    tombstone_account(db, user, "bingo-1718450000@gmail.com")

    assert db.query(Organization).filter_by(id="org-1").one().name == "bingo-1718450000@gmail.com"


def test_tombstone_leaves_shared_org_untouched(db):
    # A shared org NOT named after the email (community DEFAULT_ORG) is left alone.
    org = Organization(id="org-shared", name="default")
    db.add(org)
    db.flush()
    user = User(id="u4", email="dave@gmail.com", auth_provider="sso",
                is_active=True, org_id="org-shared")
    db.add(user)
    db.commit()

    tombstone_account(db, user, "bingo-1718450001@gmail.com")

    assert db.query(Organization).filter_by(id="org-shared").one().name == "default"
