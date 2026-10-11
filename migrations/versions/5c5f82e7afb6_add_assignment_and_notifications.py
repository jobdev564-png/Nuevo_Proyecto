"""add_assignment_and_notifications

Revision ID: 5c5f82e7afb6
Revises: c3d4e5f6a7b8
Create Date: 2026-10-11 11:45:58.849732

HU-10/HU-11: Task.created_by informativo + tabla notifications.
Aditiva y reversible (Principio VI). Incluye backfill
created_by = user_id para filas preexistentes.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5c5f82e7afb6'
down_revision = 'c3d4e5f6a7b8'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('notifications',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('task_id', sa.Integer(), nullable=False),
    sa.Column('assigned_by', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('is_read', sa.Boolean(), nullable=False,
              server_default=sa.false()),
    sa.Column('read_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['assigned_by'], ['users.id'],
                            name='fk_notifications_assigned_by'),
    sa.ForeignKeyConstraint(['task_id'], ['tasks.id'],
                            name='fk_notifications_task_id'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE',
                            name='fk_notifications_user_id'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('notifications', schema=None) as batch_op:
        batch_op.create_index('ix_notifications_task_id', ['task_id'],
                              unique=False)
        batch_op.create_index('ix_notifications_user_id', ['user_id'],
                              unique=False)
        batch_op.create_index('ix_notifications_user_read_created',
                              ['user_id', 'is_read', 'created_at'],
                              unique=False)

    # 1. Columna NULL para no romper filas existentes
    with op.batch_alter_table('tasks', schema=None) as batch_op:
        batch_op.add_column(sa.Column('created_by', sa.Integer(),
                                      nullable=True))
    # 2. Backfill: el creador original de tareas previas es su responsable
    op.execute('UPDATE tasks SET created_by = user_id '
               'WHERE created_by IS NULL')
    # 3. NOT NULL + FK con nombre (reversible en downgrade)
    with op.batch_alter_table('tasks', schema=None) as batch_op:
        batch_op.alter_column('created_by', existing_type=sa.Integer(),
                              nullable=False)
        batch_op.create_foreign_key('fk_tasks_created_by', 'users',
                                    ['created_by'], ['id'])


def downgrade():
    with op.batch_alter_table('tasks', schema=None) as batch_op:
        batch_op.drop_constraint('fk_tasks_created_by', type_='foreignkey')
        batch_op.drop_column('created_by')

    with op.batch_alter_table('notifications', schema=None) as batch_op:
        batch_op.drop_index('ix_notifications_user_read_created')
        batch_op.drop_index('ix_notifications_user_id')
        batch_op.drop_index('ix_notifications_task_id')

    op.drop_table('notifications')
