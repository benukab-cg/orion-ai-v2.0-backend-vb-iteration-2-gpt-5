"""init datasets

Revision ID: 000000000002
Revises: f9c0cc3f5321
Create Date: 2025-08-13 13:00:00.000000

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '000000000002'
down_revision = 'f9c0cc3f5321'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'dataset',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('tenant_id', sa.String(length=64), nullable=False),
        sa.Column('owner_id', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('category', sa.String(length=32), nullable=False),
        sa.Column('data_source_id', sa.String(length=36), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('tags', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True),
        sa.Column('is_enabled', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('created_by', sa.String(length=64), nullable=False),
        sa.Column('updated_by', sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(['data_source_id'], ['data_source.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'name', name='uq_dataset_tenant_name'),
    )
    op.create_index('ix_dataset_tenant_category', 'dataset', ['tenant_id', 'category'], unique=False)
    op.create_index(op.f('ix_dataset_tenant_id'), 'dataset', ['tenant_id'], unique=False)

    op.create_table(
        'dataset_config',
        sa.Column('dataset_id', sa.String(length=36), nullable=False),
        sa.Column('config_json', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
        sa.Column('config_schema_version', sa.String(length=32), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['dataset_id'], ['dataset.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('dataset_id'),
    )

    op.create_table(
        'dataset_cached_schema',
        sa.Column('dataset_id', sa.String(length=36), nullable=False),
        sa.Column('category', sa.String(length=32), nullable=False),
        sa.Column('schema_json', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
        sa.Column('schema_version', sa.String(length=32), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['dataset_id'], ['dataset.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('dataset_id'),
    )

    op.create_table(
        'dataset_metadata_profile',
        sa.Column('dataset_id', sa.String(length=36), nullable=False),
        sa.Column('fields', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['dataset_id'], ['dataset.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('dataset_id'),
    )

    op.create_table(
        'dataset_rls_policy',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('dataset_id', sa.String(length=36), nullable=False),
        sa.Column('principal_type', sa.String(length=16), nullable=False),
        sa.Column('principal_id', sa.String(length=64), nullable=True),
        sa.Column('actions', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True),
        sa.Column('effect', sa.String(length=8), nullable=False),
        sa.Column('condition', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True),
        sa.Column('sql_filter', sa.Text(), nullable=True),
        sa.Column('vector_filter', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True),
        sa.Column('blob_key_constraint', sa.String(length=512), nullable=True),
        sa.Column('priority', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['dataset_id'], ['dataset.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('dataset_rls_policy')
    op.drop_table('dataset_metadata_profile')
    op.drop_table('dataset_cached_schema')
    op.drop_table('dataset_config')
    op.drop_index(op.f('ix_dataset_tenant_id'), table_name='dataset')
    op.drop_index('ix_dataset_tenant_category', table_name='dataset')
    op.drop_table('dataset')


