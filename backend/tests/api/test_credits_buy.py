"""POST /api/credits/buy — self-serve top-up (stub, gated behind SELF_SERVE_TOPUP_ENABLED)."""
import uuid

import pytest

from backend.models.organization import Organization


def _attach_org(db, user, **kw):
    org = Organization(id=str(uuid.uuid4()), name=f"o-{uuid.uuid4()}", **kw)
    db.add(org)
    user.org_id = org.id
    db.add(user)
    db.commit()
    return org


@pytest.fixture
def _enable_self_serve(monkeypatch):
    monkeypatch.setenv("SELF_SERVE_TOPUP_ENABLED", "true")


def test_buy_disabled_by_default_403(authenticated_client, db_session, sample_user):
    # No env var set → stub must refuse so it can't mint free credits.
    _attach_org(db_session, sample_user, credit_balance=0, topup_balance=0)
    res = authenticated_client.post("/api/credits/buy", json={"package": "10k"})
    assert res.status_code == 403


def test_buy_10k_adds_to_topup(_enable_self_serve, authenticated_client, db_session, sample_user):
    org = _attach_org(db_session, sample_user, credit_balance=0, topup_balance=0)
    res = authenticated_client.post("/api/credits/buy", json={"package": "10k"})
    assert res.status_code == 200
    body = res.json()
    assert body["org_topup"] == 10000
    assert body["org_total"] == 10000
    db_session.refresh(org)
    assert org.topup_balance == 10000
    assert org.credit_balance == 10000


def test_buy_unknown_package_400(_enable_self_serve, authenticated_client, db_session, sample_user):
    _attach_org(db_session, sample_user, credit_balance=0, topup_balance=0)
    res = authenticated_client.post("/api/credits/buy", json={"package": "999k"})
    assert res.status_code == 400


class TestSelfServeFlag:
    """Direct coverage of the gate helper — off by default, truthy parsing."""

    def test_unset_is_disabled(self, monkeypatch):
        from backend.api.credits import _self_serve_topup_enabled
        monkeypatch.delenv("SELF_SERVE_TOPUP_ENABLED", raising=False)
        assert _self_serve_topup_enabled() is False

    @pytest.mark.parametrize("val", ["true", "TRUE", "1", "on", "yes", " on "])
    def test_truthy_enables(self, monkeypatch, val):
        from backend.api.credits import _self_serve_topup_enabled
        monkeypatch.setenv("SELF_SERVE_TOPUP_ENABLED", val)
        assert _self_serve_topup_enabled() is True

    @pytest.mark.parametrize("val", ["false", "0", "no", "off", ""])
    def test_falsy_stays_disabled(self, monkeypatch, val):
        from backend.api.credits import _self_serve_topup_enabled
        monkeypatch.setenv("SELF_SERVE_TOPUP_ENABLED", val)
        assert _self_serve_topup_enabled() is False
