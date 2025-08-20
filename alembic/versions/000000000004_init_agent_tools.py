"""init agent tools

Revision ID: 000000000004
Revises: 000000000003
Create Date: 2025-08-20 00:00:00.000000

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '000000000004'
down_revision = '000000000003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'agent_tool',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('tenant_id', sa.String(length=64), nullable=False),
        sa.Column('owner_id', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('kind', sa.String(length=64), nullable=False),
        sa.Column('provider', sa.String(length=64), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('tags', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True),
        sa.Column('is_enabled', sa.Boolean(), nullable=False),
        sa.Column('bindings', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('created_by', sa.String(length=64), nullable=False),
        sa.Column('updated_by', sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'name', name='uq_agent_tool_tenant_name'),
    )
    op.create_index('ix_agent_tool_tenant_enabled', 'agent_tool', ['tenant_id', 'is_enabled'], unique=False)
    op.create_index('ix_agent_tool_tenant_kind', 'agent_tool', ['tenant_id', 'kind'], unique=False)
    op.create_index(op.f('ix_agent_tool_tenant_id'), 'agent_tool', ['tenant_id'], unique=False)

    op.create_table(
        'agent_tool_config',
        sa.Column('tool_id', sa.String(length=36), nullable=False),
        sa.Column('config_json', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
        sa.Column('config_schema_version', sa.String(length=32), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['tool_id'], ['agent_tool.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('tool_id'),
    )


def downgrade() -> None:
    op.drop_table('agent_tool_config')
    op.drop_index(op.f('ix_agent_tool_tenant_id'), table_name='agent_tool')
    op.drop_index('ix_agent_tool_tenant_kind', table_name='agent_tool')
    op.drop_index('ix_agent_tool_tenant_enabled', table_name='agent_tool')
    op.drop_table('agent_tool')


