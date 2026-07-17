import hashlib
import uuid
from unittest.mock import patch

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from backend.api.briefing_shares import _hash
from backend.models.briefing import Briefing
from backend.models.briefing_share import BriefingShare

READY_PAYLOAD = {
    "headline": "Revenue up 12%",
    "deck": "A short deck.",
    "kpis": [],
    "sections": [{"heading": "One", "prose": "p", "widget_id": "chart_1"}],
    "key_takeaways": ["a", "b", "c"],
    "widget_snapshots": {"chart_1": {"type": "line", "data": [1, 2, 3]}},
}


def _briefing(db_session, dashboard, user, **kw):
    b = Briefing(
        user_id=user.id,
        dashboard_id=dashboard.id,
        source="manual",
        status=kw.pop("status", "ready"),
        payload=kw.pop("payload", dict(READY_PAYLOAD)),
        **kw,
    )
    db_session.add(b)
    db_session.commit()
    db_session.refresh(b)
    return b


def test_create_share_returns_token_once_and_stores_only_the_hash(
    authenticated_client, db_session, sample_dashboard, sample_user
):
    b = _briefing(db_session, sample_dashboard, sample_user)

    resp = authenticated_client.post(f"/api/briefings/{b.id}/share")
    assert resp.status_code == 201
    body = resp.json()
    token = body["token"]
    assert token and len(token) > 30
    # No server-built URL: the browser knows its own origin. Guards against
    # silently reintroducing a BINGO_FRONTEND_URL-derived link.
    assert "url" not in body

    row = db_session.query(BriefingShare).filter(BriefingShare.briefing_id == b.id).one()
    # The raw token must appear NOWHERE on the row.
    assert token not in str(row.token_hash)
    assert row.token_hash != token
    assert len(row.token_hash) == 64


def test_create_share_is_idempotent_and_rotates_the_token(
    authenticated_client, db_session, sample_dashboard, sample_user
):
    b = _briefing(db_session, sample_dashboard, sample_user)

    first = authenticated_client.post(f"/api/briefings/{b.id}/share").json()["token"]
    second = authenticated_client.post(f"/api/briefings/{b.id}/share").json()["token"]

    assert first != second
    assert db_session.query(BriefingShare).filter(BriefingShare.briefing_id == b.id).count() == 1


def test_create_share_recovers_when_it_loses_the_concurrent_insert_race(
    authenticated_client, db_session, test_engine, sample_dashboard, sample_user
):
    """Two simultaneous first-time enables both see share is None and both try
    to INSERT. Simulate this session losing the race: a concurrent request
    commits the winning row (via a separate session/connection, just like a
    real concurrent request would) right as this session's own commit is
    attempted, so its commit raises IntegrityError on the briefing_id UNIQUE
    constraint. The endpoint must catch it, roll back, re-query the winner's
    row, and rotate the token onto it instead of 500ing."""
    b = _briefing(db_session, sample_dashboard, sample_user)

    original_commit = db_session.commit
    calls = {"n": 0}

    def flaky_commit():
        calls["n"] += 1
        if calls["n"] == 1:
            other_session = sessionmaker(bind=test_engine)()
            try:
                other_session.add(
                    BriefingShare(
                        id=str(uuid.uuid4()),
                        briefing_id=b.id,
                        created_by_user_id=sample_user.id,
                        token_hash=hashlib.sha256(b"winner-token").hexdigest(),
                        widgets_frozen={},
                    )
                )
                other_session.commit()
            finally:
                other_session.close()
            raise IntegrityError(
                "INSERT INTO briefing_shares ...", {}, Exception("duplicate key value violates unique constraint")
            )
        return original_commit()

    with patch.object(db_session, "commit", side_effect=flaky_commit):
        resp = authenticated_client.post(f"/api/briefings/{b.id}/share")

    assert resp.status_code == 201
    token = resp.json()["token"]

    rows = db_session.query(BriefingShare).filter(BriefingShare.briefing_id == b.id).all()
    assert len(rows) == 1
    assert rows[0].token_hash == hashlib.sha256(token.encode("utf-8")).hexdigest()


def test_create_share_400_without_widget_snapshots(
    authenticated_client, db_session, sample_dashboard, sample_user
):
    payload = dict(READY_PAYLOAD)
    payload.pop("widget_snapshots")
    b = _briefing(db_session, sample_dashboard, sample_user, payload=payload)

    resp = authenticated_client.post(f"/api/briefings/{b.id}/share")
    assert resp.status_code == 400
    assert "snapshot" in resp.json()["detail"].lower()


@pytest.mark.parametrize("falsy_snapshots", [{}, None, []])
def test_create_share_400_when_widget_snapshots_present_but_falsy(
    authenticated_client, db_session, sample_dashboard, sample_user, falsy_snapshots
):
    payload = dict(READY_PAYLOAD)
    payload["widget_snapshots"] = falsy_snapshots
    b = _briefing(db_session, sample_dashboard, sample_user, payload=payload)

    resp = authenticated_client.post(f"/api/briefings/{b.id}/share")
    assert resp.status_code == 400
    assert "snapshot" in resp.json()["detail"].lower()


def test_text_only_briefing_shares_and_resolves_without_snapshots(
    anonymous_client, authenticated_client, db_session, sample_dashboard, sample_user
):
    """Generation only writes widget_snapshots when a section references a
    widget, so a text-only briefing legitimately has none. It embeds nothing,
    so there is no live-SQL-fallback risk — the snapshot guard must not block
    it at mint time, and the resolve-time re-check must not 404 it."""
    payload = dict(READY_PAYLOAD)
    payload["sections"] = [{"heading": "One", "prose": "p", "widget_id": None}]
    payload.pop("widget_snapshots")
    b = _briefing(db_session, sample_dashboard, sample_user, payload=payload)

    resp = authenticated_client.post(f"/api/briefings/{b.id}/share")
    assert resp.status_code == 201
    token = resp.json()["token"]

    resp = anonymous_client.post("/api/public/briefings/resolve", json={"token": token})
    assert resp.status_code == 200
    body = resp.json()
    assert body["headline"] == "Revenue up 12%"
    assert body["widget_snapshots"] == {}
    assert body["widgets"] == {}


def test_create_share_still_400_when_widgets_referenced_but_snapshots_missing(
    authenticated_client, db_session, sample_dashboard, sample_user
):
    """The inverse of the text-only case: sections DO reference a widget but
    snapshots are gone — the fail-closed guard must still refuse, or the
    public page would render an embed with no frozen data behind it."""
    payload = dict(READY_PAYLOAD)
    payload["widget_snapshots"] = {}
    b = _briefing(db_session, sample_dashboard, sample_user, payload=payload)

    resp = authenticated_client.post(f"/api/briefings/{b.id}/share")
    assert resp.status_code == 400
    assert "snapshot" in resp.json()["detail"].lower()


def test_create_share_400_when_not_ready(
    authenticated_client, db_session, sample_dashboard, sample_user
):
    b = _briefing(db_session, sample_dashboard, sample_user, status="generating", payload=None)
    resp = authenticated_client.post(f"/api/briefings/{b.id}/share")
    assert resp.status_code == 400


def test_create_share_404_when_not_owner(
    authenticated_client, db_session, sample_dashboard, other_user
):
    b = _briefing(db_session, sample_dashboard, other_user)
    resp = authenticated_client.post(f"/api/briefings/{b.id}/share")
    # 404, not 403 — do not confirm the briefing exists to a stranger.
    assert resp.status_code == 404


def test_delete_share_is_idempotent(
    authenticated_client, db_session, sample_dashboard, sample_user
):
    b = _briefing(db_session, sample_dashboard, sample_user)
    authenticated_client.post(f"/api/briefings/{b.id}/share")

    assert authenticated_client.delete(f"/api/briefings/{b.id}/share").status_code == 204
    assert db_session.query(BriefingShare).filter(BriefingShare.briefing_id == b.id).count() == 0
    # Deleting again must not explode.
    assert authenticated_client.delete(f"/api/briefings/{b.id}/share").status_code == 204


def _make_shared(authenticated_client, db_session, dashboard, user):
    """Create a ready briefing whose dashboard holds a SQL-bearing widget, share it."""
    dashboard.widgets = [
        {
            "id": "chart_1",
            "title": "Revenue",
            "widget": {"config": {"type": "line"}},
            "dataSource": {"sql": "SELECT secret FROM revenue", "connectionId": "conn-abc"},
            "sources": [{"table": "revenue"}],
        }
    ]
    db_session.add(dashboard)
    db_session.commit()

    b = _briefing(db_session, dashboard, user)
    token = authenticated_client.post(f"/api/briefings/{b.id}/share").json()["token"]
    return b, token


def test_public_resolve_returns_payload(
    anonymous_client, authenticated_client, db_session, sample_dashboard, sample_user
):
    b, token = _make_shared(authenticated_client, db_session, sample_dashboard, sample_user)

    resp = anonymous_client.post("/api/public/briefings/resolve", json={"token": token})
    assert resp.status_code == 200
    body = resp.json()
    assert body["headline"] == "Revenue up 12%"
    assert body["key_takeaways"] == ["a", "b", "c"]
    assert body["widget_snapshots"]["chart_1"]["data"] == [1, 2, 3]
    # Widget shape is inlined so the page never calls the authed widget endpoint.
    assert body["widgets"]["chart_1"]["widget"]["config"]["type"] == "line"


def test_public_resolve_leaks_nothing(
    anonymous_client, authenticated_client, db_session, sample_dashboard, sample_user
):
    """The money test. Assert against raw serialized JSON so that a field added
    to the response later trips this rather than sliding through."""
    b, token = _make_shared(authenticated_client, db_session, sample_dashboard, sample_user)

    raw = anonymous_client.post("/api/public/briefings/resolve", json={"token": token}).text

    assert "SELECT secret FROM revenue" not in raw
    assert "conn-abc" not in raw
    assert "connectionId" not in raw
    assert "dataSource" not in raw
    assert "sources" not in raw
    assert sample_user.id not in raw
    assert "user_id" not in raw
    assert "dashboard_id" not in raw


def test_public_resolve_strips_nested_sql_from_widgets_without_a_snapshot(
    anonymous_client, authenticated_client, db_session, sample_dashboard, sample_user
):
    """FilterWidget-style widgets have no top-level dataSource — their SQL and
    connectionId live nested at widget.config.controls[].optionsSource, which
    strip_widget's shallow top-level allowlist does not touch. resolve_share
    must only inline a widget that has a corresponding widget_snapshots entry;
    render_widget_snapshots (backend/api/widget_data.py) can never produce one
    for a widget lacking a top-level dataSource, so gating on `wid in snapshots`
    excludes the filter widget even though strip_widget alone would not."""
    sample_dashboard.widgets = [
        {
            "id": "filter_1",
            "title": "Region filter",
            "widget": {
                "config": {
                    "type": "filter",
                    "controls": [
                        {
                            "type": "dropdown",
                            "label": "Region",
                            "key": "region",
                            "column": "region",
                            "optionsSource": {
                                "connectionId": "conn-nested-secret",
                                "sql": "SELECT DISTINCT region FROM secret_regions",
                            },
                        }
                    ],
                }
            },
            # Deliberately no top-level "dataSource" key.
        }
    ]
    db_session.add(sample_dashboard)
    db_session.commit()

    payload = dict(READY_PAYLOAD)
    payload["sections"] = [{"heading": "Filters", "prose": "p", "widget_id": "filter_1"}]
    # widget_snapshots (inherited from READY_PAYLOAD) has only "chart_1" — never
    # "filter_1", matching reality: a filter widget can't get a snapshot.
    b = _briefing(db_session, sample_dashboard, sample_user, payload=payload)
    token = authenticated_client.post(f"/api/briefings/{b.id}/share").json()["token"]

    resp = anonymous_client.post("/api/public/briefings/resolve", json={"token": token})
    assert resp.status_code == 200
    raw = resp.text
    assert "SELECT DISTINCT region FROM secret_regions" not in raw
    assert "conn-nested-secret" not in raw
    assert "optionsSource" not in raw
    assert "filter_1" not in resp.json()["widgets"]


def test_get_share_status_reflects_lifecycle(
    authenticated_client, db_session, sample_dashboard, sample_user
):
    """GET /share is what lets the page hydrate after a reload instead of
    showing 'Share to web' on an already-shared briefing — where a click
    would silently rotate the token and kill the distributed link."""
    b = _briefing(db_session, sample_dashboard, sample_user)

    assert authenticated_client.get(f"/api/briefings/{b.id}/share").json() == {"active": False}

    authenticated_client.post(f"/api/briefings/{b.id}/share")
    body = authenticated_client.get(f"/api/briefings/{b.id}/share").json()
    assert body == {"active": True}
    # Status only — the raw token is hashed at rest and must not reappear here.
    assert "token" not in body and "url" not in body

    authenticated_client.delete(f"/api/briefings/{b.id}/share")
    assert authenticated_client.get(f"/api/briefings/{b.id}/share").json() == {"active": False}


def test_get_share_status_404_when_not_owner(
    authenticated_client, db_session, sample_dashboard, other_user
):
    b = _briefing(db_session, sample_dashboard, other_user)
    # 404, not 403 — do not confirm the briefing exists to a stranger.
    assert authenticated_client.get(f"/api/briefings/{b.id}/share").status_code == 404


def test_public_resolve_404_not_500_when_payload_fails_validation(
    anonymous_client, authenticated_client, db_session, sample_dashboard, sample_user
):
    """A present-but-invalid field (deck=None) passes the mint-time guard and
    the payload[...] key lookups, then fails pydantic — a ValidationError, not
    a KeyError. It must still be the generic 404: a 500 would tell an attacker
    the token was valid, since unknown tokens 404."""
    b, token = _make_shared(authenticated_client, db_session, sample_dashboard, sample_user)

    b.payload = {**b.payload, "deck": None}
    db_session.add(b)
    db_session.commit()

    resp = anonymous_client.post("/api/public/briefings/resolve", json={"token": token})
    assert resp.status_code == 404
    assert resp.json()["detail"] == "This link isn't available"


def test_public_resolve_scrubs_nested_secrets_even_on_snapshotted_widgets(
    anonymous_client, authenticated_client, db_session, sample_dashboard, sample_user
):
    """The `wid in snapshots` gate only keeps nested secrets out because
    filter-style widgets happen to never get snapshots. strip_widget must not
    rely on that coincidence: a widget that BOTH has a snapshot AND nests
    sql/connectionId inside the retained `widget` subtree must come out clean."""
    sample_dashboard.widgets = [
        {
            "id": "chart_1",
            "title": "Revenue",
            "widget": {
                "config": {
                    "type": "line",
                    "rows": ["safe-row"],
                    "controls": [
                        {
                            "type": "dropdown",
                            "label": "Region",
                            "optionsSource": {
                                "connectionId": "conn-nested-secret",
                                "sql": "SELECT DISTINCT region FROM secret_regions",
                            },
                        }
                    ],
                }
            },
            "dataSource": {
                "connectionId": "conn-abc",
                "sql": "SELECT revenue FROM t",
                "mapping": {"x": "date", "y": "revenue"},
            },
        }
    ]
    db_session.add(sample_dashboard)
    db_session.commit()

    b = _briefing(db_session, sample_dashboard, sample_user)
    token = authenticated_client.post(f"/api/briefings/{b.id}/share").json()["token"]

    resp = anonymous_client.post("/api/public/briefings/resolve", json={"token": token})
    assert resp.status_code == 200
    raw = resp.text
    assert "SELECT DISTINCT region FROM secret_regions" not in raw
    assert "conn-nested-secret" not in raw
    assert "optionsSource" not in raw
    # Non-secret nested keys survive the scrub — this is stripping, not dropping.
    config = resp.json()["widgets"]["chart_1"]["widget"]["config"]
    assert config["rows"] == ["safe-row"]
    assert config["controls"][0]["label"] == "Region"


def test_public_resolve_404_when_widget_snapshots_missing_after_share(
    anonymous_client, authenticated_client, db_session, sample_dashboard, sample_user
):
    """The POST /share guard only proves widget_snapshots existed on the
    request that created the share. If the briefing's payload is later
    mutated (hand-edit, legacy row, whatever) to drop widget_snapshots, the
    public GET must not silently degrade to widget_snapshots={} — that is the
    exact signal the frontend uses to fall back to a live SQL refresh, the one
    thing this endpoint exists to prevent. It must 404 instead."""
    b, token = _make_shared(authenticated_client, db_session, sample_dashboard, sample_user)

    assert anonymous_client.post("/api/public/briefings/resolve", json={"token": token}).status_code == 200

    b.payload = {**b.payload, "widget_snapshots": None}
    db_session.add(b)
    db_session.commit()

    resp = anonymous_client.post("/api/public/briefings/resolve", json={"token": token})
    assert resp.status_code == 404


def test_public_resolve_needs_no_auth_header_at_all(
    anonymous_client, db_session, sample_dashboard, sample_user
):
    """Fails loudly if someone later bolts a global auth dependency onto the app.

    Deliberately does NOT depend on authenticated_client: fixture setup follows
    signature order, so if that fixture were present its
    `app.dependency_overrides[get_current_user] = lambda: sample_user` override
    would be live while the anonymous request runs — masking exactly the bug
    this test exists to catch. The share row is built directly in the DB so no
    authed request is ever made in this test.
    """
    token = "no-auth-needed-token"
    share = BriefingShare(
        id=str(uuid.uuid4()),
        briefing_id=_briefing(db_session, sample_dashboard, sample_user).id,
        created_by_user_id=sample_user.id,
        token_hash=_hash(token),
        widgets_frozen={},
    )
    db_session.add(share)
    db_session.commit()

    assert "Authorization" not in anonymous_client.headers
    assert anonymous_client.post("/api/public/briefings/resolve", json={"token": token}).status_code == 200


def test_public_resolve_404_for_unknown_token(anonymous_client):
    assert anonymous_client.post("/api/public/briefings/resolve", json={"token": "not-a-real-token"}).status_code == 404


def test_public_resolve_404_after_revoke(
    anonymous_client, authenticated_client, db_session, sample_dashboard, sample_user
):
    b, token = _make_shared(authenticated_client, db_session, sample_dashboard, sample_user)
    assert anonymous_client.post("/api/public/briefings/resolve", json={"token": token}).status_code == 200

    authenticated_client.delete(f"/api/briefings/{b.id}/share")
    assert anonymous_client.post("/api/public/briefings/resolve", json={"token": token}).status_code == 404


def test_public_resolve_serves_frozen_view_not_live_dashboard(
    anonymous_client, authenticated_client, db_session, sample_dashboard, sample_user
):
    """A briefing is an immutable snapshot; that is the entire reason the
    anonymous endpoint is safe. But widget.config is NOT immutable — the
    frontend merges refreshed result rows into it and saves. resolve_share
    must never read the live `dashboards` table: the public view is frozen
    onto the share row at share time and must stay frozen even after the
    dashboard is later edited or renamed."""
    sample_dashboard.widgets = [
        {
            "id": "chart_1",
            "title": "Revenue",
            "widget": {"config": {"type": "line", "rows": ["original-row"]}},
            # Realistic top-level dataSource: render_widget_snapshots (widget_data.py)
            # only produces a widget_snapshots entry for a widget carrying
            # connectionId + sql + mapping here, and that is precisely the
            # invariant the `wid in snapshots` security gate rests on. The
            # stripped output below must still exclude this key.
            "dataSource": {
                "connectionId": "conn-abc",
                "sql": "SELECT revenue FROM t",
                "mapping": {"x": "date", "y": "revenue"},
            },
        }
    ]
    db_session.add(sample_dashboard)
    db_session.commit()

    b = _briefing(db_session, sample_dashboard, sample_user)
    token = authenticated_client.post(f"/api/briefings/{b.id}/share").json()["token"]

    # Mutate the dashboard AFTER sharing: a refreshed widget row landing in
    # config, plus a rename. Neither must reach the already-minted link.
    sample_dashboard.widgets = [
        {
            "id": "chart_1",
            "title": "Revenue",
            "widget": {"config": {"type": "line", "rows": ["LEAKED_AFTER_SHARE"]}},
        }
    ]
    sample_dashboard.title = "Renamed After Share"
    db_session.add(sample_dashboard)
    db_session.commit()

    resp = anonymous_client.post("/api/public/briefings/resolve", json={"token": token})
    assert resp.status_code == 200
    raw = resp.text
    body = resp.json()

    assert "LEAKED_AFTER_SHARE" not in raw
    assert body["widgets"]["chart_1"]["widget"]["config"]["rows"] == ["original-row"]
    assert body["dashboard_name"] == "Test dashboard"
    assert "Renamed After Share" not in raw
    # The frozen widget carries a top-level dataSource (realistic per
    # render_widget_snapshots' invariant); strip_widget must still drop it.
    assert "dataSource" not in body["widgets"]["chart_1"]
    assert "conn-abc" not in raw
    assert "SELECT revenue FROM t" not in raw


def test_rotating_the_token_kills_the_old_link(
    anonymous_client, authenticated_client, db_session, sample_dashboard, sample_user
):
    b, old = _make_shared(authenticated_client, db_session, sample_dashboard, sample_user)
    new = authenticated_client.post(f"/api/briefings/{b.id}/share").json()["token"]

    assert new != old
    assert anonymous_client.post("/api/public/briefings/resolve", json={"token": old}).status_code == 404
    assert anonymous_client.post("/api/public/briefings/resolve", json={"token": new}).status_code == 200


def test_public_resolve_applies_redaction_policy_retroactively_to_frozen_widgets(
    anonymous_client, db_session, sample_dashboard, sample_user
):
    """widgets_frozen freezes DATA, not the redaction POLICY. A row minted
    before _PUBLIC_WIDGET_KEYS excluded some leaky key (or minted before
    strip_widget existed at all) must not keep serving the wider shape
    forever — resolve_share re-applies strip_widget and the `wid in
    snapshots` gate at READ time, over the already-frozen data, so tightening
    the allowlist protects every already-minted link without a re-share.

    Bypasses create_share/_freeze entirely and inserts the BriefingShare row
    directly, simulating exactly that legacy/pre-tightening shape.
    """
    b = _briefing(db_session, sample_dashboard, sample_user)
    token = "legacy-wide-share-token"
    share = BriefingShare(
        id=str(uuid.uuid4()),
        briefing_id=b.id,
        created_by_user_id=sample_user.id,
        token_hash=_hash(token),
        # Simulates a row frozen before a leaky key was excluded from the
        # allowlist: carries a non-allowlisted "dataSource" key alongside the
        # allowlisted ones. READY_PAYLOAD's widget_snapshots has "chart_1",
        # so this widget passes the `wid in snapshots` gate.
        widgets_frozen={
            "chart_1": {
                "id": "chart_1",
                "title": "Revenue",
                "widget": {"config": {"type": "line"}},
                "dataSource": {"sql": "SELECT leaked FROM t", "connectionId": "conn-x"},
            }
        },
    )
    db_session.add(share)
    db_session.commit()

    resp = anonymous_client.post("/api/public/briefings/resolve", json={"token": token})
    assert resp.status_code == 200
    raw = resp.text
    body = resp.json()

    assert "SELECT leaked FROM t" not in raw
    assert "conn-x" not in raw
    assert "dataSource" not in raw
    assert "dataSource" not in body["widgets"]["chart_1"]
    # Confirm the allowlisted keys still made it through — proves this is
    # stripping, not just dropping the whole widget.
    assert body["widgets"]["chart_1"]["title"] == "Revenue"
