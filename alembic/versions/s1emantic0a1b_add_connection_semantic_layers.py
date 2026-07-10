"""Add connection_semantic_layers table (per-connection glossary / relationships / definitions).

Stores human-curated meaning for a connection's data, kept SEPARATE from
`database_connections.data_context` (which is rebuilt on every profiling run) so
edits survive re-profiling. Overlaid at read time by services.semantic_layer.

Revision ID: s1emantic0a1b
Revises: w1dgetid255
Create Date: 2026-07-10
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "s1emantic0a1b"
down_revision = "w1dgetid255"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "connection_semantic_layers",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("connection_id", sa.Integer(), nullable=False),
        sa.Column(
            "glossary",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "relationships",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "definitions",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["connection_id"], ["database_connections.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint("connection_id", name="uq_connection_semantic_layers_connection_id"),
    )


def downgrade() -> None:
    op.drop_table("connection_semantic_layers")
