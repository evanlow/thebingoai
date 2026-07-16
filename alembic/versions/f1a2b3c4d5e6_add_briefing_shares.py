"""Add briefing_shares table (public share links for briefings)

Revision ID: f1a2b3c4d5e6
Revises: s1emantic0a1b
Create Date: 2026-07-16 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "f1a2b3c4d5e6"
down_revision = "s1emantic0a1b"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "briefing_shares",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "briefing_id",
            sa.BigInteger(),
            sa.ForeignKey("briefings.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("created_by_user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("widgets_frozen", JSONB(), nullable=False),
        sa.Column("dashboard_name", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("briefing_shares_token_hash_idx", "briefing_shares", ["token_hash"], unique=True)


def downgrade():
    op.drop_index("briefing_shares_token_hash_idx", table_name="briefing_shares")
    op.drop_table("briefing_shares")
