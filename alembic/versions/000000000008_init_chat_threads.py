"""init chat threads and messages tables

Revision ID: 000000000008
Revises: 000000000007
Create Date: 2025-09-04 00:00:00.000000

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '000000000008'
down_revision = '000000000007'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'chat_thread',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('tenant_id', sa.String(length=64), nullable=False),
        sa.Column('chatbot_id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=64), nullable=False),
        sa.Column('title', sa.String(length=256), nullable=True),
        sa.Column('status', sa.String(length=16), nullable=False, server_default=sa.text("'active'")),
        sa.Column('tags', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('last_message_at', sa.DateTime(), nullable=True),
        sa.Column('token_usage', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('last_run_id', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['chatbot_id'], ['chatbot.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_thread_chatbot_user', 'chat_thread', ['chatbot_id', 'user_id'], unique=False)
    op.create_index('ix_thread_status', 'chat_thread', ['status'], unique=False)
    op.create_index('ix_thread_last_message_at', 'chat_thread', ['last_message_at'], unique=False)

    op.create_table(
        'chat_message',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('tenant_id', sa.String(length=64), nullable=False),
        sa.Column('thread_id', sa.String(length=36), nullable=False),
        sa.Column('role', sa.String(length=16), nullable=False),
        sa.Column('content_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('citations_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('attachments_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('run_id', sa.String(length=64), nullable=True),
        sa.Column('token_counts_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('latency_ms', sa.String(length=16), nullable=True),
        sa.Column('error_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['thread_id'], ['chat_thread.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_message_thread_created', 'chat_message', ['thread_id', 'created_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_message_thread_created', table_name='chat_message')
    op.drop_table('chat_message')
    op.drop_index('ix_thread_last_message_at', table_name='chat_thread')
    op.drop_index('ix_thread_status', table_name='chat_thread')
    op.drop_index('ix_thread_chatbot_user', table_name='chat_thread')
    op.drop_table('chat_thread')


