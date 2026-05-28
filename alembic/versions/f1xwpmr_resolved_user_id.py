"""Fix widgets_pending_manual_rewrite.resolved_by_user_id type (Integer -> String(36) FK)

The column was created as Integer, but resolve_entry/bulk_resolve assign User.id
(a String(36) UUID), causing psycopg2 InvalidTextRepresentation 500 on every resolve.
Re-type the column to String(36) and add the FK to users.id.

Revision ID: f1xwpmr_resolved_user_id
Revises: mrgfinal2head
Create Date: 2026-05-26

"""

from alembic import op
import sqlalchemy as sa

revision = 'f1xwpmr_resolved_user_id'
down_revision = 'mrgfinal2head'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "widgets_pending_manual_rewrite",
        "resolved_by_user_id",
        type_=sa.String(36),
        existing_nullable=True,
        postgresql_using="resolved_by_user_id::varchar",
    )
    op.create_foreign_key(
        "fk_wpmr_resolved_by_user_id_users",
        "widgets_pending_manual_rewrite",
        "users",
        ["resolved_by_user_id"],
        ["id"],
    )


def downgrade():
    op.drop_constraint(
        "fk_wpmr_resolved_by_user_id_users",
        "widgets_pending_manual_rewrite",
        type_="foreignkey",
    )
    op.alter_column(
        "widgets_pending_manual_rewrite",
        "resolved_by_user_id",
        type_=sa.Integer(),
        existing_nullable=True,
        postgresql_using="resolved_by_user_id::integer",
    )
