"""add tenant_id to chat_message

Revision ID: 000000000010
Revises: 000000000009
Create Date: 2025-09-04 01:10:00.000000

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '000000000010'
down_revision = '000000000009'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('chat_message', sa.Column('tenant_id', sa.String(length=64), nullable=True))
    op.create_index('ix_chat_message_tenant', 'chat_message', ['tenant_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_chat_message_tenant', table_name='chat_message')
    op.drop_column('chat_message', 'tenant_id')


