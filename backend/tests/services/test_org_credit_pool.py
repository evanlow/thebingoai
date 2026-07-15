"""Org credit pool consumption.

Exercises ``backend.services.org_credit_pool`` against a real Postgres engine
(seeded by ``conftest.test_engine``) so the atomic UPDATE ... RETURNING path
matches production semantics, then verifies the community CreditContextManager
stays stats-only (never gates on or debits the pool — enterprise's job).
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from backend.models.organization import Organization
from backend.models.user import User
from backend.services.org_credit_pool import (
    check_org_pool,
    lookup_user_org_id,
)
from backend.services.token_tracking_service import CreditContextManager


def _mk_org(db, *, balance: int = 5000) -> Organization:
    o = Organization(
        id=str(uuid.uuid4()),
        name=f"acme-{uuid.uuid4()}",
        credit_balance=balance,
    )
    db.add(o)
    db.commit()
    return o


def _mk_user(db, *, org_id: str | None) -> User:
    u = User(
        id=str(uuid.uuid4()),
        email=f"u-{uuid.uuid4()}@example.com",
        auth_provider="sso",
        org_id=org_id,
    )
    db.add(u)
    db.commit()
    return u


class TestOrgCreditPoolHelpers:

    def test_lookup_user_org_id(self, db_session):
        org = _mk_org(db_session)
        user = _mk_user(db_session, org_id=org.id)
        assert lookup_user_org_id(db_session, user.id) == org.id

    def test_check_org_pool_returns_balance(self, db_session):
        org = _mk_org(db_session, balance=42)
        assert check_org_pool(db_session, org.id) == 42


@pytest.fixture
def credit_usage_table(test_engine):
    # credit_usage is created by alembic, not by a community ORM model, so the
    # models-only test schema lacks it. Minimal DDL matching _record()'s INSERT.
    with test_engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE IF NOT EXISTS credit_usage ("
            "id SERIAL PRIMARY KEY, user_id VARCHAR, conversation_id VARCHAR, "
            "title VARCHAR, credits_used INTEGER, input_tokens INTEGER, "
            "output_tokens INTEGER, date DATE, created_at TIMESTAMP)"
        ))
    yield


class TestCreditContextManagerOrgPool:
    """Community manager is stats-only: self-hosted deployments pay their LLM
    provider directly (own API keys), so it must never gate on or debit the org
    pool — that's the enterprise bingo_admin manager's job."""

    def test_community_never_touches_org_pool(self, db_session, credit_usage_table):
        org = _mk_org(db_session, balance=5)
        user = _mk_user(db_session, org_id=org.id)
        mgr = CreditContextManager(
            db=db_session,
            user_id=user.id,
            title="t",
            provider_name="anthropic",
            conversation_id=None,
        )
        mgr._check()
        mgr._record()
        assert check_org_pool(db_session, org.id) == 5  # untouched

    def test_exhausted_org_pool_does_not_block_community(self, db_session, credit_usage_table):
        # Self-hosted users must never hit a paywall — even block_on_insufficient
        # (passed by every call site) is a no-op in the community manager.
        org = _mk_org(db_session, balance=0)
        user = _mk_user(db_session, org_id=org.id)
        mgr = CreditContextManager(
            db=db_session,
            user_id=user.id,
            title="t",
            provider_name="anthropic",
            conversation_id=None,
            block_on_insufficient=True,
        )
        mgr._check()  # no raise
        mgr._record()  # records the stats row, still no pool touch
        assert check_org_pool(db_session, org.id) == 0

    def test_user_without_org_records_stats_row(self, db_session, credit_usage_table):
        # Community / legacy user with no org — record path stays functional.
        user = _mk_user(db_session, org_id=None)
        mgr = CreditContextManager(
            db=db_session,
            user_id=user.id,
            title="t",
            provider_name="anthropic",
            conversation_id=None,
        )
        mgr._check()
        mgr._record()
        from sqlalchemy import text
        n = db_session.execute(
            text("SELECT count(*) FROM credit_usage WHERE user_id = :uid"),
            {"uid": user.id},
        ).scalar()
        assert n == 1


class TestSpendOrgPool:
    def _org(self, db, *, recurring, topup):
        import uuid
        from backend.models.organization import Organization
        # recurring is derived; seed via credit_balance(total) + topup_balance
        org = Organization(
            id=str(uuid.uuid4()), name=f"o-{uuid.uuid4()}",
            credit_balance=recurring + topup, topup_balance=topup,
        )
        db.add(org); db.commit()
        return org

    def test_spend_drains_recurring_first(self, db_session):
        from backend.services.org_credit_pool import spend_org_pool, read_org_pool_breakdown
        org = self._org(db_session, recurring=10, topup=5)
        assert spend_org_pool(db_session, org.id, 3) == 12  # new total
        assert read_org_pool_breakdown(db_session, org.id) == {"recurring": 7, "topup": 5, "total": 12}

    def test_spend_spills_into_topup(self, db_session):
        from backend.services.org_credit_pool import spend_org_pool, read_org_pool_breakdown
        org = self._org(db_session, recurring=2, topup=5)
        assert spend_org_pool(db_session, org.id, 4) == 3
        assert read_org_pool_breakdown(db_session, org.id) == {"recurring": 0, "topup": 3, "total": 3}

    def test_spend_blocks_when_total_insufficient(self, db_session):
        from backend.services.org_credit_pool import spend_org_pool, read_org_pool_breakdown
        org = self._org(db_session, recurring=1, topup=1)
        assert spend_org_pool(db_session, org.id, 3) is None
        assert read_org_pool_breakdown(db_session, org.id) == {"recurring": 1, "topup": 1, "total": 2}


class TestDebitOrgPoolClamped:
    """Per-turn post-hoc debit: recurring-first, clamped at zero (never refuses)."""

    def _org(self, db, *, recurring, topup):
        import uuid
        from backend.models.organization import Organization
        org = Organization(
            id=str(uuid.uuid4()), name=f"o-{uuid.uuid4()}",
            credit_balance=recurring + topup, topup_balance=topup,
        )
        db.add(org); db.commit()
        return org

    def test_drains_recurring_first(self, db_session):
        from backend.services.org_credit_pool import debit_org_pool_clamped, read_org_pool_breakdown
        org = self._org(db_session, recurring=10, topup=5)
        assert debit_org_pool_clamped(db_session, org.id, 3) == 12
        assert read_org_pool_breakdown(db_session, org.id) == {"recurring": 7, "topup": 5, "total": 12}

    def test_spills_into_topup(self, db_session):
        from backend.services.org_credit_pool import debit_org_pool_clamped, read_org_pool_breakdown
        org = self._org(db_session, recurring=2, topup=5)
        assert debit_org_pool_clamped(db_session, org.id, 4) == 3
        assert read_org_pool_breakdown(db_session, org.id) == {"recurring": 0, "topup": 3, "total": 3}

    def test_clamps_at_zero_on_overage(self, db_session):
        # Unlike spend_org_pool this never refuses: it drains to zero even when
        # the debit exceeds the balance (the turn already ran).
        from backend.services.org_credit_pool import debit_org_pool_clamped, read_org_pool_breakdown
        org = self._org(db_session, recurring=1, topup=1)
        assert debit_org_pool_clamped(db_session, org.id, 5) == 0
        assert read_org_pool_breakdown(db_session, org.id) == {"recurring": 0, "topup": 0, "total": 0}

    def test_db_error_rolls_back_and_returns_none(self):
        # A failed UPDATE aborts the PG transaction; without a rollback the
        # caller's subsequent commit/persist on the same session would fail. The
        # helper must roll back (unpoison the session) and return None, not
        # silently leave the txn aborted.
        from unittest.mock import MagicMock
        from backend.services.org_credit_pool import debit_org_pool_clamped
        db = MagicMock()
        db.execute.side_effect = Exception("statement failed")
        assert debit_org_pool_clamped(db, "org-1", 5) is None
        db.rollback.assert_called_once()

    def test_missing_org_returns_none_without_rollback(self):
        # No row matched (bad org_id) — the transaction is intact, so no rollback
        # is issued; distinct from the DB-error path above.
        from unittest.mock import MagicMock
        from backend.services.org_credit_pool import debit_org_pool_clamped
        db = MagicMock()
        db.execute.return_value.fetchone.return_value = None
        assert debit_org_pool_clamped(db, "missing", 5) is None
        db.rollback.assert_not_called()
