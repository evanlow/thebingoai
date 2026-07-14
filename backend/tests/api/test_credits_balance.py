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
    # sample_user has no org_id → pool not consulted, org_exhausted False.
    # The daily cap is gone, so a no-org user is unlimited; balance_scope says so
    # explicitly and the frontend hides the (now meaningless) number.
    data = authenticated_client.get("/api/credits/balance").json()
    assert data["org_exhausted"] is False
    assert data["remaining"] == data["daily_limit"]
    assert data["balance_scope"] == "unlimited"


def test_drained_org_pool_clamps_remaining_to_zero(authenticated_client, db_session, sample_user):
    _attach_org(db_session, sample_user, balance=0)
    data = authenticated_client.get("/api/credits/balance").json()
    assert data["org_exhausted"] is True
    assert data["remaining"] == 0
    assert data["daily_limit"] > 0  # n unchanged → "0 of n"


def test_funded_org_pool_remaining_is_workspace_total(authenticated_client, db_session, sample_user):
    # Daily limit removed: remaining now reflects the workspace pool total,
    # not the per-user daily figure.
    _attach_org(db_session, sample_user, balance=500)
    data = authenticated_client.get("/api/credits/balance").json()
    assert data["org_exhausted"] is False
    assert data["remaining"] == 500
    assert data["org_total"] == 500
    assert data["balance_scope"] == "workspace"


def test_used_today_does_not_reduce_workspace_remaining(
    authenticated_client, db_session, sample_user
):
    # The per-user daily counter no longer gates spending, so recording usage
    # today must not shrink the workspace-backed `remaining`.
    from datetime import datetime
    from sqlalchemy import text

    _attach_org(db_session, sample_user, balance=300)
    db_session.execute(
        text(
            "INSERT INTO credit_usage (user_id, title, credits_used, date, created_at) "
            "VALUES (:uid, 't', 50, :today, :now)"
        ),
        {"uid": sample_user.id, "today": datetime.utcnow().date(), "now": datetime.utcnow()},
    )
    db_session.commit()
    data = authenticated_client.get("/api/credits/balance").json()
    assert data["remaining"] == 300  # unchanged by the 50 used today


def test_balance_includes_org_breakdown(authenticated_client, db_session, sample_user):
    import uuid
    from backend.models.organization import Organization
    org = Organization(id=str(uuid.uuid4()), name=f"o-{uuid.uuid4()}",
                       credit_balance=130, topup_balance=30)  # recurring derived = 100
    db_session.add(org)
    sample_user.org_id = org.id
    db_session.add(sample_user)
    db_session.commit()
    data = authenticated_client.get("/api/credits/balance").json()
    assert data["org_recurring"] == 100
    assert data["org_topup"] == 30
    assert data["org_total"] == 130
    assert data["org_exhausted"] is False
