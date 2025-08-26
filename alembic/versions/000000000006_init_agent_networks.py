"""init agent networks tables

Revision ID: 000000000006
Revises: 000000000005
Create Date: 2025-08-21 00:30:00.000000

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '000000000006'
down_revision = '000000000005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'agent_network',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('tenant_id', sa.String(length=64), nullable=False),
        sa.Column('owner_id', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('slug', sa.String(length=128), nullable=False),
        sa.Column('type', sa.String(length=64), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('tags', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('version', sa.String(length=32), nullable=False),
        sa.Column('status', sa.String(length=16), nullable=False, server_default=sa.text("'draft'")),
        sa.Column('spec_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('is_enabled', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('created_by', sa.String(length=64), nullable=False),
        sa.Column('updated_by', sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'slug', 'version', name='uq_agent_network_slug_version')
    )
    op.create_index('ix_agent_network_tenant', 'agent_network', ['tenant_id'], unique=False)
    op.create_index('ix_agent_network_status', 'agent_network', ['tenant_id', 'status'], unique=False)
    op.create_index('ix_agent_network_enabled', 'agent_network', ['tenant_id', 'is_enabled'], unique=False)

    op.create_table(
        'agent_network_interface',
        sa.Column('network_id', sa.String(length=36), nullable=False),
        sa.Column('version', sa.String(length=32), nullable=False),
        sa.Column('inputs_schema', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('outputs_schema', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('streaming', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('capabilities', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(['network_id'], ['agent_network.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('network_id')
    )

    op.create_table(
        'agent_network_node',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('network_id', sa.String(length=36), nullable=False),
        sa.Column('node_key', sa.String(length=64), nullable=False),
        sa.Column('agent_id', sa.String(length=36), nullable=True),
        sa.Column('child_network_id', sa.String(length=36), nullable=True),
        sa.Column('child_network_version', sa.String(length=32), nullable=True),
        sa.Column('role', sa.String(length=32), nullable=True),
        sa.Column('config_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(['agent_id'], ['agent.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['child_network_id'], ['agent_network.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['network_id'], ['agent_network.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('network_id', 'node_key', name='uq_network_node_key')
    )
    op.create_index('ix_node_network', 'agent_network_node', ['network_id'], unique=False)

    op.create_table(
        'agent_network_edge',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('network_id', sa.String(length=36), nullable=False),
        sa.Column('source_node_key', sa.String(length=64), nullable=False),
        sa.Column('target_node_key', sa.String(length=64), nullable=False),
        sa.Column('condition', sa.String(length=256), nullable=True),
        sa.ForeignKeyConstraint(['network_id'], ['agent_network.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_edge_network', 'agent_network_edge', ['network_id'], unique=False)

    op.create_table(
        'agent_network_dependency',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('parent_network_id', sa.String(length=36), nullable=False),
        sa.Column('child_network_id', sa.String(length=36), nullable=False),
        sa.Column('child_version_range', sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(['parent_network_id'], ['agent_network.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['child_network_id'], ['agent_network.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('parent_network_id', 'child_network_id', name='uq_network_dependency_pair')
    )
    op.create_index('ix_dependency_parent', 'agent_network_dependency', ['parent_network_id'], unique=False)
    op.create_index('ix_dependency_child', 'agent_network_dependency', ['child_network_id'], unique=False)

    op.create_table(
        'agent_network_run',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('network_id', sa.String(length=36), nullable=True),
        sa.Column('run_id', sa.String(length=64), nullable=False),
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column('input_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('output_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('events_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('error_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('checkpoint', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['network_id'], ['agent_network.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('agent_network_run')
    op.drop_index('ix_dependency_child', table_name='agent_network_dependency')
    op.drop_index('ix_dependency_parent', table_name='agent_network_dependency')
    op.drop_table('agent_network_dependency')
    op.drop_index('ix_edge_network', table_name='agent_network_edge')
    op.drop_table('agent_network_edge')
    op.drop_index('ix_node_network', table_name='agent_network_node')
    op.drop_table('agent_network_node')
    op.drop_table('agent_network_interface')
    op.drop_index('ix_agent_network_enabled', table_name='agent_network')
    op.drop_index('ix_agent_network_status', table_name='agent_network')
    op.drop_index('ix_agent_network_tenant', table_name='agent_network')
    op.drop_table('agent_network')


