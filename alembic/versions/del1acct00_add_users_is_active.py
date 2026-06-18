"""Add is_active to users (account-deletion tombstone flag).

False marks a self-serve-deleted account whose email was masked to
bingo-<ts>@<original_domain>. The active-user filters (login guard in
auth/dependencies.py, admin list_users) exclude these rows. Existing rows
backfill to true via server_default.

Revision ID: del1acct00
Revises: mrgheads_f1x_p1in
Create Date: 2026-06-16 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "del1acct00"
down_revision = "mrgheads_f1x_p1in"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "users",
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )


def downgrade():
    op.drop_column("users", "is_active")
