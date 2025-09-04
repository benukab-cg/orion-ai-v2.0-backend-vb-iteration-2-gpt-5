"""init chatbots tables

Revision ID: 000000000007
Revises: 000000000006
Create Date: 2025-09-03 00:00:00.000000

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '000000000007'
down_revision = '000000000006'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'chatbot',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('tenant_id', sa.String(length=64), nullable=False),
        sa.Column('owner_id', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('slug', sa.String(length=128), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('visibility', sa.String(length=32), nullable=True),
        sa.Column('is_enabled', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('agent_network_id', sa.String(length=36), nullable=False),
        sa.Column('agent_network_version', sa.String(length=32), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('created_by', sa.String(length=64), nullable=False),
        sa.Column('updated_by', sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(['agent_network_id'], ['agent_network.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'name', name='uq_chatbot_tenant_name'),
        sa.UniqueConstraint('tenant_id', 'slug', name='uq_chatbot_tenant_slug')
    )
    op.create_index('ix_chatbot_tenant_enabled', 'chatbot', ['tenant_id', 'is_enabled'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_chatbot_tenant_enabled', table_name='chatbot')
    op.drop_table('chatbot')


