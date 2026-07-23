"""Unit tests for backend/services/share_links.py.

Uses BriefingShare as the concrete model — the only share model today. The
module itself is model-agnostic; these tests pin the generic contract:
token returned once, only the hash at rest, rotate-on-re-enable, and
recovery when a concurrent first-enable wins the INSERT race.
"""

import uuid
from unittest.mock import patch

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from backend.models.briefing import Briefing
from backend.models.briefing_share import BriefingShare
from backend.services.share_links import (
    hash_token,
    mint_token,
    resolve_by_token,
    upsert_share,
)


def _briefing(db_session, sample_dashboard, sample_user):
    b = Briefing(
        user_id=sample_user.id,
        dashboard_id=sample_dashboard.id,
        source="manual",
        status="ready",
        payload={"widget_snapshots": {"w1": {}}},
    )
    db_session.add(b)
    db_session.commit()
    db_session.refresh(b)
    return b


def _row_factory(briefing, user):
    def make_row():
        return BriefingShare(
            id=str(uuid.uuid4()),
            briefing_id=briefing.id,
            created_by_user_id=user.id,
            widgets_frozen={},
        )

    return make_row


def test_mint_token_is_long_and_urlsafe():
    t = mint_token()
    assert len(t) > 30
    assert all(c.isalnum() or c in "-_" for c in t)


def test_upsert_creates_row_and_stores_only_the_hash(
    db_session, sample_dashboard, sample_user
):
    b = _briefing(db_session, sample_dashboard, sample_user)

    token = upsert_share(
        db_session,
        BriefingShare,
        [BriefingShare.briefing_id == b.id],
        _row_factory(b, sample_user),
        lambda row: None,
    )

    row = resolve_by_token(db_session, BriefingShare, token)
    assert row is not None
    assert row.briefing_id == b.id
    assert row.token_hash == hash_token(token)
    # The raw token must appear nowhere on the row.
    assert token not in row.token_hash


def test_upsert_rotates_token_and_calls_refresh(
    db_session, sample_dashboard, sample_user
):
    b = _briefing(db_session, sample_dashboard, sample_user)
    filters = [BriefingShare.briefing_id == b.id]
    make_row = _row_factory(b, sample_user)

    first = upsert_share(db_session, BriefingShare, filters, make_row, lambda r: None)

    refreshed = {"n": 0}

    def refresh(row):
        refreshed["n"] += 1
        row.widgets_frozen = {"refreshed": True}

    second = upsert_share(db_session, BriefingShare, filters, make_row, refresh)

    assert first != second
    # Old link dies immediately on rotation.
    assert resolve_by_token(db_session, BriefingShare, first) is None
    row = resolve_by_token(db_session, BriefingShare, second)
    assert row is not None
    assert refreshed["n"] == 1
    assert row.widgets_frozen == {"refreshed": True}
    assert db_session.query(BriefingShare).filter(*filters).count() == 1


def test_upsert_recovers_from_lost_insert_race(
    db_session, test_engine, sample_dashboard, sample_user
):
    """Two concurrent first-time enables both see no row and both INSERT.
    Simulate this session losing: a second session commits the winning row
    right as this session's commit runs, so it raises IntegrityError. The
    helper must roll back, re-query the winner's row, and rotate the token
    onto it — never 500, never two rows."""
    b = _briefing(db_session, sample_dashboard, sample_user)
    filters = [BriefingShare.briefing_id == b.id]

    original_commit = db_session.commit
    calls = {"n": 0}

    def flaky_commit():
        calls["n"] += 1
        if calls["n"] == 1:
            other = sessionmaker(bind=test_engine)()
            try:
                other.add(
                    BriefingShare(
                        id=str(uuid.uuid4()),
                        briefing_id=b.id,
                        created_by_user_id=sample_user.id,
                        token_hash=hash_token("winner-token"),
                        widgets_frozen={},
                    )
                )
                other.commit()
            finally:
                other.close()
            raise IntegrityError(
                "INSERT INTO briefing_shares ...",
                {},
                Exception("duplicate key value violates unique constraint"),
            )
        return original_commit()

    with patch.object(db_session, "commit", side_effect=flaky_commit):
        token = upsert_share(
            db_session, BriefingShare, filters, _row_factory(b, sample_user), lambda r: None
        )

    rows = db_session.query(BriefingShare).filter(*filters).all()
    assert len(rows) == 1
    assert rows[0].token_hash == hash_token(token)


def test_resolve_unknown_token_returns_none(db_session):
    assert resolve_by_token(db_session, BriefingShare, "no-such-token") is None


def test_upsert_raises_runtime_error_when_row_vanishes_after_race(
    db_session, sample_dashboard, sample_user
):
    """IntegrityError on commit but NO winner row exists on re-query (e.g. the
    winner was revoked in the same window). The helper must raise RuntimeError
    — the caller maps it to HTTP 500 — and leave no row behind."""
    b = _briefing(db_session, sample_dashboard, sample_user)
    filters = [BriefingShare.briefing_id == b.id]

    original_commit = db_session.commit
    calls = {"n": 0}

    def flaky_commit():
        calls["n"] += 1
        if calls["n"] == 1:
            # No winner row inserted — after rollback the re-query finds nothing.
            raise IntegrityError(
                "INSERT INTO briefing_shares ...",
                {},
                Exception("duplicate key value violates unique constraint"),
            )
        return original_commit()

    with patch.object(db_session, "commit", side_effect=flaky_commit):
        with pytest.raises(RuntimeError):
            upsert_share(
                db_session, BriefingShare, filters, _row_factory(b, sample_user), lambda r: None
            )

    assert db_session.query(BriefingShare).filter(*filters).count() == 0
