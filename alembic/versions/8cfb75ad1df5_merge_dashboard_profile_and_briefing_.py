"""merge dashboard_profile and briefing_shares heads

Revision ID: 8cfb75ad1df5
Revises: d4shpr0f1le1, f1a2b3c4d5e6
Create Date: 2026-07-21 00:01:16.478839

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8cfb75ad1df5'
down_revision = ('d4shpr0f1le1', 'f1a2b3c4d5e6')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
