"""init agents tables

Revision ID: 000000000005
Revises: 000000000004
Create Date: 2025-08-21 00:00:00.000000

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '000000000005'
down_revision = '000000000004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'agent',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('tenant_id', sa.String(length=64), nullable=False),
        sa.Column('owner_id', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('type', sa.String(length=64), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('tags', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('ai_model_id', sa.String(length=36), nullable=False),
        sa.Column('is_enabled', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('bindings', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('created_by', sa.String(length=64), nullable=False),
        sa.Column('updated_by', sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(['ai_model_id'], ['ai_model.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'name', name='uq_agent_tenant_name')
    )
    op.create_index('ix_agent_tenant_type', 'agent', ['tenant_id', 'type'], unique=False)
    op.create_index('ix_agent_tenant_enabled', 'agent', ['tenant_id', 'is_enabled'], unique=False)

    op.create_table(
        'agent_config',
        sa.Column('agent_id', sa.String(length=36), nullable=False),
        sa.Column('config_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('config_schema_version', sa.String(length=32), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['agent_id'], ['agent.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('agent_id')
    )


def downgrade() -> None:
    op.drop_table('agent_config')
    op.drop_index('ix_agent_tenant_enabled', table_name='agent')
    op.drop_index('ix_agent_tenant_type', table_name='agent')
    op.drop_table('agent')


