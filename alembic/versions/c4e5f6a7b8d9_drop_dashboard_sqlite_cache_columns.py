"""Drop legacy SQLite-on-DO-Spaces dashboard cache columns + merge open heads.

Removes cache_key, cache_built_at, cache_status from dashboards. These were
the metadata for the pre-DataPlane SQLite cache, now replaced by per-widget
Parquet tables on the Org's DataPlane (`_dash_{dashboard_id}__{widget_id}`).

Doubles as a merge migration: unifies the three open heads that existed on
the dev branch (b3d4e5f6a7c8 / c3d4e5f6a7b8 / aa2c3d4e5f6a) so subsequent
migrations have a single lineage to chain off of.

Revision ID: c4e5f6a7b8d9
Revises: b3d4e5f6a7c8, c3d4e5f6a7b8, aa2c3d4e5f6a
Create Date: 2026-05-18
"""
from alembic import op
import sqlalchemy as sa


revision = "c4e5f6a7b8d9"
down_revision = ("b3d4e5f6a7c8", "c3d4e5f6a7b8", "aa2c3d4e5f6a")
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("dashboards") as batch_op:
        batch_op.drop_column("cache_key")
        batch_op.drop_column("cache_built_at")
        batch_op.drop_column("cache_status")


def downgrade() -> None:
    with op.batch_alter_table("dashboards") as batch_op:
        batch_op.add_column(sa.Column("cache_key", sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column("cache_built_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("cache_status", sa.String(length=20), nullable=True))
