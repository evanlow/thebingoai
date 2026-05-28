"""Add timezone column to schedule-bearing tables.

Revision ID: b3d4e5f6a7c8
Revises: a2c3d4e5f6b7
Create Date: 2026-05-18

Adds an IANA timezone string (e.g. ``Asia/Singapore``) to ``heartbeat_jobs``,
``dashboards``, and ``pipelines``. The dispatcher and API endpoints evaluate
the row's ``cron_expression`` in this timezone, so users see schedules fire
at their intended local wall-clock time.

Existing rows default to ``'UTC'`` so behavior is unchanged until they are
re-saved with a real timezone.
"""

from alembic import op
import sqlalchemy as sa


revision = "b3d4e5f6a7c8"
down_revision = "a2c3d4e5f6b7"
branch_labels = None
depends_on = None


_TABLES = ("heartbeat_jobs", "dashboards", "pipelines")


def upgrade() -> None:
    for table in _TABLES:
        op.add_column(
            table,
            sa.Column(
                "timezone",
                sa.String(length=64),
                nullable=False,
                server_default="UTC",
            ),
        )


def downgrade() -> None:
    for table in _TABLES:
        op.drop_column(table, "timezone")
