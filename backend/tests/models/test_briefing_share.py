import uuid

from backend.models.briefing import Briefing
from backend.models.briefing_share import BriefingShare


def test_briefing_share_persists_and_enforces_one_per_briefing(db_session, sample_dashboard, sample_user):
    b = Briefing(
        user_id=sample_user.id,
        dashboard_id=sample_dashboard.id,
        source="manual",
        status="ready",
        payload={"headline": "h"},
    )
    db_session.add(b)
    db_session.commit()

    share = BriefingShare(
        id=str(uuid.uuid4()),
        briefing_id=b.id,
        token_hash="a" * 64,
        created_by_user_id=sample_user.id,
        widgets_frozen={},
    )
    db_session.add(share)
    db_session.commit()
    db_session.refresh(share)

    assert share.created_at is not None

    # briefing_id is UNIQUE — one link per briefing (the toggle model).
    dupe = BriefingShare(
        id=str(uuid.uuid4()),
        briefing_id=b.id,
        token_hash="b" * 64,
        created_by_user_id=sample_user.id,
        widgets_frozen={},
    )
    db_session.add(dupe)
    import pytest
    from sqlalchemy.exc import IntegrityError
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
