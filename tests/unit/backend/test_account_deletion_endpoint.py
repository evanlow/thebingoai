"""Endpoint + login-guard tests for self-serve account deletion.

Covers the newly added wiring beyond `tombstone_account`:
  - login guard in auth/dependencies._resolve_local_user (tombstoned → 403)
  - DELETE /auth/account handler success path (SSO returns new_email → tombstone)
  - handler failure path (SSO returns None → 502, local row untouched)
"""
import backend.models  # noqa: F401 — register all mappers
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import sessionmaker

from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from backend.database.base import Base
from backend.models.user import User
from backend.models.database_connection import DatabaseConnection
from backend.models.heartbeat_job import HeartbeatJob
from backend.models.custom_agent import CustomAgent
from backend.models.dashboard import Dashboard
from backend.models.pipeline import Pipeline
from backend.models.transforms import DbtModel

import backend.api.auth as auth_api
from backend.api.auth import delete_account
from backend.auth.dependencies import _resolve_local_user
from backend.schemas.auth import DeleteAccountRequest


@compiles(JSONB, "sqlite")
def _jsonb_as_json_sqlite(element, compiler, **kw):  # pragma: no cover
    return "JSON"


@pytest.fixture
def db():
    # StaticPool + check_same_thread=False: one shared connection so tables are
    # visible from the run_in_threadpool worker thread (delete_account success path).
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine, tables=[
        User.__table__,
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


class _SsoUser:
    def __init__(self, _id, email):
        self.id = _id
        self.email = email


# ---- login guard --------------------------------------------------------

def test_login_guard_blocks_tombstoned_user(db):
    db.add(User(id="u1", email="bingo-1718450000@gmail.com", sso_id="sid1",
                auth_provider="sso", is_active=False))
    db.commit()

    sso_user = _SsoUser("sid1", "bingo-1718450000@gmail.com")
    with pytest.raises(HTTPException) as exc:
        _resolve_local_user(MagicMock(), db, sso_user)
    assert exc.value.status_code == 403


def test_login_guard_allows_active_user(db, monkeypatch):
    # Disable governance so the active-user path doesn't reach into org tables
    # we don't create here — we're only asserting the is_active guard doesn't fire.
    import backend.auth.dependencies as deps
    monkeypatch.setattr(deps.settings, "enable_governance", False)

    db.add(User(id="u2", email="alice@gmail.com", sso_id="sid2",
                auth_provider="sso", is_active=True))
    db.commit()

    sso_user = _SsoUser("sid2", "alice@gmail.com")
    user = _resolve_local_user(MagicMock(), db, sso_user)
    assert user.id == "u2"
    assert user.is_active is True


# ---- endpoint -----------------------------------------------------------

def _creds():
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials="tok")


@pytest.mark.asyncio
async def test_delete_account_success(db, monkeypatch):
    user = User(id="u3", email="bob@gmail.com", sso_id="sid3",
                auth_provider="sso", is_active=True)
    db.add(user)
    db.commit()

    async def fake_sso(access_token, refresh_token=None):
        return {"new_email": "bingo-1718450000@gmail.com"}
    monkeypatch.setattr(auth_api, "sso_delete_account", fake_sso)

    result = await delete_account(
        body=DeleteAccountRequest(refresh_token=None),
        credentials=_creds(), current_user=user, db=db,
    )
    assert result["email"] == "bingo-1718450000@gmail.com"

    refreshed = db.query(User).filter_by(id="u3").one()
    assert refreshed.email == "bingo-1718450000@gmail.com"
    assert refreshed.is_active is False


@pytest.mark.asyncio
async def test_delete_account_sso_failure_leaves_row_intact(db, monkeypatch):
    user = User(id="u4", email="carol@gmail.com", sso_id="sid4",
                auth_provider="sso", is_active=True)
    db.add(user)
    db.commit()

    async def fake_sso(access_token, refresh_token=None):
        return None
    monkeypatch.setattr(auth_api, "sso_delete_account", fake_sso)

    with pytest.raises(HTTPException) as exc:
        await delete_account(
            body=DeleteAccountRequest(refresh_token=None),
            credentials=_creds(), current_user=user, db=db,
        )
    assert exc.value.status_code == 502

    refreshed = db.query(User).filter_by(id="u4").one()
    assert refreshed.email == "carol@gmail.com"
    assert refreshed.is_active is True
