"""Org-level credit pool helpers.

Phase 4 of multi-user-org. Each chat turn debits both:

  - the per-user daily credit balance (legacy, owned by token_tracking_service),
  - and the per-org credit balance (this module).

Either exhausted → block the turn. Both succeed → record + commit atomically.

The org pool defaults to 5000 credits per org (set in alembic migration
h0i1j2k3l4m5_org_credits_and_role_rename); BingoAdmin tops it up via the
forthcoming Phase 5 admin UI.
"""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def lookup_user_org_id(db: Session, user_id: str) -> Optional[str]:
    """Return the user's `org_id` or None when unset / missing.

    Wrapped in a defensive try/except so community deployments that lack the
    organizations FK column (pre-Phase-0) still work.
    """
    try:
        row = db.execute(
            text("SELECT org_id FROM users WHERE id = :uid"),
            {"uid": str(user_id)},
        ).fetchone()
    except Exception:
        return None
    if row is None:
        return None
    return row[0]


def check_org_pool(db: Session, org_id: str) -> Optional[int]:
    """Read-only check of the org credit balance.

    Returns the current balance, or None when the column / row is missing
    (community deployments without Phase 0 schema applied).
    """
    try:
        row = db.execute(
            text("SELECT credit_balance FROM organizations WHERE id = :org"),
            {"org": str(org_id)},
        ).fetchone()
    except Exception:
        return None
    return int(row[0]) if row is not None else None


def spend_org_pool(db: Session, org_id: str, amount: int) -> Optional[int]:
    """Atomically spend `amount` from the org pool, draining recurring first.

    Recurring is derived (credit_balance - topup_balance). The spend reduces the
    total; topup_balance only drops once the spend exceeds the derived recurring,
    so top-up survives until recurring is exhausted. Gate is on the total
    (credit_balance >= amount): all-or-nothing. Postgres evaluates SET against the
    pre-UPDATE row. Returns the new total, or None if the column is missing
    (pre-Phase-0 community schema) or the total was insufficient. Callers pass
    amount >= 1. Caller owns the transaction.
    """
    try:
        result = db.execute(
            text(
                "UPDATE organizations "
                "SET topup_balance = CASE WHEN (credit_balance - topup_balance) >= :amt "
                "        THEN topup_balance "
                "        ELSE topup_balance - (:amt - (credit_balance - topup_balance)) END, "
                "    credit_balance = credit_balance - :amt "
                "WHERE id = :org AND credit_balance >= :amt "
                "RETURNING credit_balance"
            ),
            {"amt": int(amount), "org": str(org_id)},
        )
    except Exception:
        return None
    row = result.fetchone()
    if row is None:
        return None
    return int(row[0])


def debit_org_pool_clamped(db: Session, org_id: str, amount: int) -> Optional[int]:
    """Post-hoc per-turn debit — recurring-first, clamped at zero.

    Unlike spend_org_pool this has no ``credit_balance >= :amt`` gate: the turn
    already ran (called per-turn from the enterprise bingo-admin plugin's
    CreditContextManager._exit), so we drain what's left rather than refuse. The
    pre-flight org-pool check in _check_credits is what blocks a turn on an
    already-empty pool. Clamps the spend to the current balance so the pool never
    goes negative. Returns the new total, or None if the column is missing
    (pre-Phase-0 community schema) or the UPDATE failed. Caller owns the txn.
    """
    # LEAST(:amt, credit_balance) clamps the debit to what's left so the pool
    # never goes negative; recurring (credit_balance - topup_balance) drains
    # before topup, matching spend_org_pool / the retired daily task.
    try:
        result = db.execute(
            text(
                "UPDATE organizations "
                "SET topup_balance = CASE "
                "        WHEN (credit_balance - topup_balance) >= LEAST(:amt, credit_balance) "
                "            THEN topup_balance "
                "            ELSE topup_balance - (LEAST(:amt, credit_balance) - (credit_balance - topup_balance)) END, "
                "    credit_balance = credit_balance - LEAST(:amt, credit_balance) "
                "WHERE id = :org "
                "RETURNING credit_balance"
            ),
            {"amt": int(amount), "org": str(org_id)},
        )
    except Exception:
        return None
    row = result.fetchone()
    if row is None:
        return None
    return int(row[0])


def read_org_pool_breakdown(db: Session, org_id: str) -> Optional[dict]:
    """Return {recurring, topup, total} or None when the columns are missing.
    recurring is derived: total - topup."""
    try:
        row = db.execute(
            text("SELECT credit_balance, topup_balance FROM organizations WHERE id = :org"),
            {"org": str(org_id)},
        ).fetchone()
    except Exception:
        return None
    if row is None:
        return None
    total, topup = int(row[0]), int(row[1])
    return {"recurring": total - topup, "topup": topup, "total": total}


def try_decrement_org_pool(db: Session, org_id: str, amount: int = 1) -> Optional[int]:
    """Per-turn community debit — recurring-first. Thin wrapper over spend_org_pool
    for back-compat with token_tracking_service._record."""
    return spend_org_pool(db, org_id, amount)
