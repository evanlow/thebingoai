"""org recurring + topup credit split

Revision ID: f1x2p1in3r4e
Revises: del1acct00
Create Date: 2026-06-18

Adds topup_balance, recurring_allotment, recurring_resets_at to organizations.
credit_balance stays the total; recurring is derived (credit_balance - topup_balance).
Backfill: existing balance is treated as recurring → topup starts 0 (no column
write needed; the derive formula yields recurring = credit_balance). allotment
mirrors the current balance; resets_at NULL (armed only when an org is marked paid).
"""
from alembic import op
import sqlalchemy as sa

revision = "f1x2p1in3r4e"
down_revision = "del1acct00"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("organizations", sa.Column("topup_balance", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("organizations", sa.Column("recurring_allotment", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("organizations", sa.Column("recurring_resets_at", sa.DateTime(timezone=True), nullable=True))
    op.execute("UPDATE organizations SET recurring_allotment = credit_balance")


def downgrade() -> None:
    op.drop_column("organizations", "recurring_resets_at")
    op.drop_column("organizations", "recurring_allotment")
    op.drop_column("organizations", "topup_balance")
