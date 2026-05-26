"""merge m1e2r3g4e5h6 and merge_dd9e_sch1ma heads

Revision ID: mrgfinal2head
Revises: ('m1e2r3g4e5h6', 'merge_dd9e_sch1ma')
Create Date: 2026-05-26

"""

from alembic import op
import sqlalchemy as sa

revision = 'mrgfinal2head'
down_revision = ('m1e2r3g4e5h6', 'merge_dd9e_sch1ma')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
