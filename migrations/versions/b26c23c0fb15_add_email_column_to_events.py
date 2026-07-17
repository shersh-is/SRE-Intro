"""add email column to events

Revision ID: b26c23c0fb15
Revises: 9dec944598d2
Create Date: 2026-07-10 18:57:41.414451

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b26c23c0fb15'
down_revision: Union[str, Sequence[str], None] = '9dec944598d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Adding a nullable column is a metadata-only change in PostgreSQL 11+ —
    # no table rewrite, no blocking lock on SELECT/INSERT. Safe under load.
    op.add_column('events', sa.Column('email', sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column('events', 'email')
