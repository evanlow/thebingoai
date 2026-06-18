"""GET /api/credits/balance — org-pool exhaustion clamp.

When the user's workspace (org) credit pool is drained, the spend gate blocks
regardless of the daily quota, so the balance endpoint surfaces remaining=0 and
org_exhausted=True instead of a misleading daily count.
"""
import uuid

from backend.models.organization import Organization


def _attach_org(db, user, *, balance: int) -> None:
    org = Organization(id=str(uuid.uuid4()), name=f"org-{uuid.uuid4()}", credit_balance=balance)
    db.add(org)
    user.org_id = org.id
    db.add(user)
    db.commit()


def test_no_org_reports_daily_only(authenticated_client):
    # sample_user has no org_id → pool not consulted, org_exhausted False
    data = authenticated_client.get("/api/credits/balance").json()
    assert data["org_exhausted"] is False
    assert data["remaining"] == data["daily_limit"]


def test_drained_org_pool_clamps_remaining_to_zero(authenticated_client, db_session, sample_user):
    _attach_org(db_session, sample_user, balance=0)
    data = authenticated_client.get("/api/credits/balance").json()
    assert data["org_exhausted"] is True
    assert data["remaining"] == 0
    assert data["daily_limit"] > 0  # n unchanged → "0 of n"


def test_funded_org_pool_not_exhausted(authenticated_client, db_session, sample_user):
    _attach_org(db_session, sample_user, balance=500)
    data = authenticated_client.get("/api/credits/balance").json()
    assert data["org_exhausted"] is False
    assert data["remaining"] == data["daily_limit"]
