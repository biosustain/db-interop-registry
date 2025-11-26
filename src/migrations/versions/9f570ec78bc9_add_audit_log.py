"""Add audit_log table for tracking ingestion events
Revision ID: 9f570ec78bc9
Revises: 9f53da407469
Create Date: 2025-09-04 11:30:00.000000

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '9f570ec78bc9'
down_revision = '9f53da407469'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'audit_log',
        sa.Column('event_id', sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column('event_time', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('uid', sa.String(length=255), nullable=False),
        sa.Column('event_type', sa.String(length=255), nullable=False),
    )
    op.create_index(op.f('ix_audit_log_event_id'), 'audit_log', ['event_id'], unique=False)
    op.create_index(op.f('ix_audit_log_uid'), 'audit_log', ['uid'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_audit_log_uid'), table_name='audit_log')
    op.drop_index(op.f('ix_audit_log_event_id'), table_name='audit_log')
    op.drop_table('audit_log')
