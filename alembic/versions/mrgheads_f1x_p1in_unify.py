"""merge f1xwpmr_resolved_user_id and p1ingest0a1b2c heads

Revision ID: mrgheads_f1x_p1in
Revises: f1xwpmr_resolved_user_id, p1ingest0a1b2c
Create Date: 2026-05-29

"""

from alembic import op
import sqlalchemy as sa

revision = 'mrgheads_f1x_p1in'
down_revision = ('f1xwpmr_resolved_user_id', 'p1ingest0a1b2c')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
