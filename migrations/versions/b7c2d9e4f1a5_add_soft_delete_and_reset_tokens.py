"""add_soft_delete_and_reset_tokens

Revision ID: b7c2d9e4f1a5
Revises: ec2fa45c2f9b
Create Date: 2026-10-11

Aditiva y reversible (Principio VI): soft delete en tasks + tabla
password_reset_tokens. Backfill de filas existentes por SERVER_DEFAULT.
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b7c2d9e4f1a5'
down_revision = 'ec2fa45c2f9b'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Columnas de soft delete en tasks (HU-05)
    with op.batch_alter_table('tasks', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('is_deleted', sa.Boolean(), nullable=False,
                      server_default='0')
        )
        batch_op.add_column(sa.Column('deleted_at', sa.DateTime(), nullable=True))
        batch_op.create_index('ix_tasks_is_deleted', ['is_deleted'], unique=False)

    # 2. Tabla de tokens de restablecimiento (HU-14)
    op.create_table(
        'password_reset_tokens',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('token_hash', sa.String(length=255), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('used_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token_hash'),
    )
    with op.batch_alter_table('password_reset_tokens', schema=None) as batch_op:
        batch_op.create_index('ix_password_reset_tokens_user_id', ['user_id'], unique=False)
        batch_op.create_index('ix_password_reset_tokens_token_hash', ['token_hash'], unique=True)


def downgrade():
    with op.batch_alter_table('password_reset_tokens', schema=None) as batch_op:
        batch_op.drop_index('ix_password_reset_tokens_token_hash')
        batch_op.drop_index('ix_password_reset_tokens_user_id')

    op.drop_table('password_reset_tokens')

    with op.batch_alter_table('tasks', schema=None) as batch_op:
        batch_op.drop_index('ix_tasks_is_deleted')
        batch_op.drop_column('deleted_at')
        batch_op.drop_column('is_deleted')
