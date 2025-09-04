"""add tenant_id to chat_thread

Revision ID: 000000000009
Revises: 000000000008
Create Date: 2025-09-04 01:00:00.000000

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '000000000009'
down_revision = '000000000008'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add tenant_id as nullable first to avoid failing on existing rows
    op.add_column('chat_thread', sa.Column('tenant_id', sa.String(length=64), nullable=True))
    op.create_index('ix_chat_thread_tenant', 'chat_thread', ['tenant_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_chat_thread_tenant', table_name='chat_thread')
    op.drop_column('chat_thread', 'tenant_id')


