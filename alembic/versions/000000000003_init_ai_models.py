"""init ai models

Revision ID: 000000000003
Revises: 000000000002
Create Date: 2025-08-15 00:00:00.000000

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '000000000003'
down_revision = '000000000002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'ai_model',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('tenant_id', sa.String(length=64), nullable=False),
        sa.Column('owner_id', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('type', sa.String(length=64), nullable=False),
        sa.Column('category', sa.String(length=32), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('tags', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True),
        sa.Column('is_enabled', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('created_by', sa.String(length=64), nullable=False),
        sa.Column('updated_by', sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'name', name='uq_ai_model_tenant_name'),
    )
    op.create_index('ix_ai_model_tenant_enabled', 'ai_model', ['tenant_id', 'is_enabled'], unique=False)
    op.create_index('ix_ai_model_tenant_type', 'ai_model', ['tenant_id', 'type'], unique=False)
    op.create_index(op.f('ix_ai_model_tenant_id'), 'ai_model', ['tenant_id'], unique=False)

    op.create_table(
        'ai_model_config',
        sa.Column('ai_model_id', sa.String(length=36), nullable=False),
        sa.Column('config_encrypted', sa.LargeBinary(), nullable=False),
        sa.Column('config_schema_version', sa.String(length=32), nullable=True),
        sa.Column('redaction_map', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['ai_model_id'], ['ai_model.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('ai_model_id'),
    )


def downgrade() -> None:
    op.drop_table('ai_model_config')
    op.drop_index(op.f('ix_ai_model_tenant_id'), table_name='ai_model')
    op.drop_index('ix_ai_model_tenant_type', table_name='ai_model')
    op.drop_index('ix_ai_model_tenant_enabled', table_name='ai_model')
    op.drop_table('ai_model')



