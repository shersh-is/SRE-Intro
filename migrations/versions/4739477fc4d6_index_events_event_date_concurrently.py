"""index events.event_date concurrently

Revision ID: 4739477fc4d6
Revises: b26c23c0fb15
Create Date: 2026-07-18 02:05:15.509536

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4739477fc4d6'
down_revision: Union[str, Sequence[str], None] = 'b26c23c0fb15'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.get_context().autocommit_block():
        op.create_index(
            "ix_events_event_date",
            "events",
            ["event_date"],
            unique=False,
            postgresql_concurrently=True,
            if_not_exists=True,
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.get_context().autocommit_block():
        op.drop_index(
            "ix_events_event_date",
            table_name="events",
            postgresql_concurrently=True,
            if_exists=True,
        )
