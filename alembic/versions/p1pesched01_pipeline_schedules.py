"""pipeline_schedules: one pipeline per connection, multiple schedules

Revision ID: p1pesched01
Revises: f1x2p1in3r4e
Create Date: 2026-06-23

Additive. Adds the `pipeline_schedules` table (cadence buckets, each owning a
disjoint subset of a connection's tables via the `tables` JSON), a
`pipeline_runs.schedule_id` FK, makes `pipelines.target_table` nullable (new-model
rows carry per-table targets in their schedules), and a partial unique index so
new-model pipelines are one-per-connection (legacy rows with cron set are exempt).
Legacy pipelines are untouched.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "p1pesched01"
down_revision = "f1x2p1in3r4e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pipeline_schedules",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("pipeline_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("cron", sa.String(length=64), nullable=True),
        sa.Column("timezone", sa.String(length=64), nullable=False, server_default="UTC"),
        sa.Column("tables", JSONB(), nullable=False, server_default="[]"),
        sa.Column("next_run_at", sa.DateTime(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["pipeline_id"], ["pipelines.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_pipeline_schedule_enabled_next_run_at",
        "pipeline_schedules", ["enabled", "next_run_at"],
    )
    op.create_index(
        "ix_pipeline_schedule_pipeline", "pipeline_schedules", ["pipeline_id"],
    )

    op.add_column(
        "pipeline_runs",
        sa.Column("schedule_id", sa.String(length=36), nullable=True),
    )
    op.create_foreign_key(
        "fk_pipeline_run_schedule", "pipeline_runs", "pipeline_schedules",
        ["schedule_id"], ["id"], ondelete="SET NULL",
    )

    # New-model rows leave target_table null (per-table targets live in schedules).
    op.alter_column("pipelines", "target_table", existing_type=sa.String(length=255), nullable=True)

    # One new-model pipeline per connection per scope. Partial: legacy rows
    # (cron set) are exempt so existing many-per-connection data stays valid.
    op.create_index(
        "uq_new_pipeline_per_connection",
        "pipelines",
        ["owner_scope_kind", "owner_scope_id", "source_connection_id"],
        unique=True,
        postgresql_where=sa.text("cron IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_new_pipeline_per_connection", table_name="pipelines")
    op.alter_column("pipelines", "target_table", existing_type=sa.String(length=255), nullable=False)
    op.drop_constraint("fk_pipeline_run_schedule", "pipeline_runs", type_="foreignkey")
    op.drop_column("pipeline_runs", "schedule_id")
    op.drop_index("ix_pipeline_schedule_pipeline", table_name="pipeline_schedules")
    op.drop_index("ix_pipeline_schedule_enabled_next_run_at", table_name="pipeline_schedules")
    op.drop_table("pipeline_schedules")
