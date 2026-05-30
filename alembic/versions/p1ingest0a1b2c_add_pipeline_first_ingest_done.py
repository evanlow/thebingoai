"""add pipelines.first_ingest_done + merge floating heads

Adds a boolean tracking whether the bootstrap (first) ingest run for a
Pipeline has completed successfully. Read by the dashboard / chat plane-
redirect paths (Phase 2) to gate the "one live source query as bootstrap
fallback" policy described in the connector-DataPlane plan.

Also merges four pre-existing heads ('m1e2r3g4e5h6', '6aa6739712fc',
'f685d85122bd', 'p6lin0a1b2c3d4') into a single linear tip so subsequent
migrations have a unique parent.

Revision ID: p1ingest0a1b2c
Revises: m1e2r3g4e5h6, 6aa6739712fc, f685d85122bd, p6lin0a1b2c3d4
Create Date: 2026-05-28
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "p1ingest0a1b2c"
down_revision = (
    "m1e2r3g4e5h6",
    "6aa6739712fc",
    "f685d85122bd",
    "p6lin0a1b2c3d4",
)
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "pipelines",
        sa.Column(
            "first_ingest_done",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("pipelines", "first_ingest_done")
