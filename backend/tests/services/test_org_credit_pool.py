"""Phase 4 of multi-user-org: org credit pool consumption.

Exercises ``backend.services.org_credit_pool`` against a real Postgres engine
(seeded by ``conftest.test_engine``) so the atomic UPDATE ... RETURNING path
matches production semantics, then verifies CreditContextManager honours both
the per-user daily cap and the org pool.
"""
from __future__ import annotations

import uuid

import pytest

from backend.models.organization import Organization
from backend.models.user import User
from backend.services.org_credit_pool import (
    check_org_pool,
    lookup_user_org_id,
    try_decrement_org_pool,
)
from backend.services.token_tracking_service import (
    CreditContextManager,
    InsufficientCreditsError,
)


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

    def test_try_decrement_org_pool_returns_new_balance(self, db_session):
        org = _mk_org(db_session, balance=10)
        assert try_decrement_org_pool(db_session, org.id, amount=3) == 7
        assert check_org_pool(db_session, org.id) == 7

    def test_try_decrement_returns_none_when_exhausted(self, db_session):
        org = _mk_org(db_session, balance=0)
        assert try_decrement_org_pool(db_session, org.id) is None
        # Untouched.
        assert check_org_pool(db_session, org.id) == 0


class TestCreditContextManagerOrgPool:

    def test_under_both_caps_succeeds(self, db_session):
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
        assert check_org_pool(db_session, org.id) == 4

    def test_org_pool_exhausted_blocks_with_org_pool_reason(self, db_session):
        org = _mk_org(db_session, balance=0)
        user = _mk_user(db_session, org_id=org.id)
        mgr = CreditContextManager(
            db=db_session,
            user_id=user.id,
            title="t",
            provider_name="anthropic",
            conversation_id=None,
        )
        with pytest.raises(InsufficientCreditsError) as ex:
            mgr._check()
        assert ex.value.reason == "org_pool"

    def test_daily_cap_removed_does_not_block(self, db_session):
        # Daily limit removed: even a 0 daily_limit row must not block while the
        # org pool has credit. Spending is gated solely on the workspace pool.
        org = _mk_org(db_session, balance=100)
        user = _mk_user(db_session, org_id=org.id)
        from sqlalchemy import text
        from datetime import datetime
        db_session.execute(
            text(
                "INSERT INTO user_credit_balances (user_id, daily_limit, created_at) "
                "VALUES (:uid, 0, :now)"
            ),
            {"uid": user.id, "now": datetime.utcnow()},
        )
        db_session.commit()

        mgr = CreditContextManager(
            db=db_session,
            user_id=user.id,
            title="t",
            provider_name="anthropic",
            conversation_id=None,
        )
        # No raise — the per-user daily cap is gone; org pool (100) still funds it.
        mgr._check()
        mgr._record()
        assert check_org_pool(db_session, org.id) == 99

    def test_user_without_org_skips_pool_check(self, db_session):
        # Community / legacy user. Pool branch must be inert.
        user = _mk_user(db_session, org_id=None)
        mgr = CreditContextManager(
            db=db_session,
            user_id=user.id,
            title="t",
            provider_name="anthropic",
            conversation_id=None,
        )
        # No exception — pool branch skipped.
        mgr._check()
        mgr._record()


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
