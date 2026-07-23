from sqlalchemy import Column, BigInteger, String, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB
from backend.database.base import Base


class BriefingShare(Base):
    """Public share link for a briefing. One row per shared briefing.

    The raw token is never stored — only sha256(token). Revoking is a row
    delete; re-enabling mints a fresh token, so an old link stays dead.

    The public view is frozen at share time, not read live: `widgets_frozen`
    and `dashboard_name` are captured from the `dashboards` table when the
    link is minted (or rotated). resolve_share must never query `dashboards`
    itself — that is what keeps an old link's content immutable even if the
    dashboard is later edited or renamed.
    """

    __tablename__ = "briefing_shares"

    id = Column(String, primary_key=True)
    briefing_id = Column(
        BigInteger,
        ForeignKey("briefings.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    token_hash = Column(String(64), nullable=False, unique=True, index=True)
    created_by_user_id = Column(String, ForeignKey("users.id"), nullable=False)
    # {widget_id: strip_widget(widget)} — captured at share time, never re-read.
    widgets_frozen = Column(JSONB, nullable=False)
    # Frozen dashboard title at share time; a later rename must not change it.
    dashboard_name = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
