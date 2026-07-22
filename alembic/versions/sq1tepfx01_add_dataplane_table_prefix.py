"""Add dataplane_table_prefix to migration_journal.

Physical DataPlane tables written by a SQLite migration are namespaced
`sqlite_<connection_id>_<table>` so two uploads by the same owner that both
contain e.g. `orders` don't overwrite each other. The prefix is recorded here so
the connector can scope the owner's table list to one connection.

NULL means the connection was migrated before prefixing existed and its tables
carry bare names.

Revision ID: sq1tepfx01
Revises: 8cfb75ad1df5
"""
from alembic import op
import sqlalchemy as sa

revision = "sq1tepfx01"
down_revision = "8cfb75ad1df5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "migration_journal",
        sa.Column("dataplane_table_prefix", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("migration_journal", "dataplane_table_prefix")
