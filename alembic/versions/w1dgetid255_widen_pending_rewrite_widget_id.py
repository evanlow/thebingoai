"""Widen widgets_pending_manual_rewrite.widget_id to 255 chars

Revision ID: w1dgetid255
Revises: p1pesched01
Create Date: 2026-07-04

Widget ids are LLM-chosen and can exceed 36 chars (e.g.
`chart_price_distribution_by_room_type`), which made the lineage
parse-failure batch insert fail with StringDataRightTruncation and roll
back the whole batch on every build_graph run.
"""
from alembic import op
import sqlalchemy as sa

revision = "w1dgetid255"
down_revision = "p1pesched01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "widgets_pending_manual_rewrite",
        "widget_id",
        type_=sa.String(length=255),
        existing_type=sa.String(length=36),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "widgets_pending_manual_rewrite",
        "widget_id",
        type_=sa.String(length=36),
        existing_type=sa.String(length=255),
        existing_nullable=False,
    )
