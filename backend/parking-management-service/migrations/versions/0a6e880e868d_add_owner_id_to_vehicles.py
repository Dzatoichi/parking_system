"""add_owner_id_to_vehicles

Revision ID: 0a6e880e868d
Revises: 54ccc166d30c
Create Date: 2026-05-07 16:26:01.241607

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0a6e880e868d'
down_revision: Union[str, Sequence[str], None] = '54ccc166d30c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Добавляем колонку owner_id
    op.add_column(
        'vehicles_table',
        sa.Column('owner_id', sa.Integer(), nullable=False, server_default='1')
    )
    op.create_index('ix_vehicles_table_owner_id', 'vehicles_table', ['owner_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_vehicles_table_owner_id', table_name='vehicles_table')
    op.drop_column('vehicles_table', 'owner_id')
