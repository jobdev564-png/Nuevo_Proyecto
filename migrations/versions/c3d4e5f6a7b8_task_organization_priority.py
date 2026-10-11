"""task_organization_priority: categories + priority + category_id

Revision ID: c3d4e5f6a7b8
Revises: b7c2d9e4f1a5
Create Date: 2026-10-11

Incremento 3 (HU-07/HU-08/HU-09, Principio VI):
1. Crea tabla `categories` (owner-only, UniqueConstraint user_id+name).
2. Extiende `tasks` con `priority` (NOT NULL, server_default='medium' para
   backfill determinista de tareas preexistentes) y `category_id`
   (nullable, FK ON DELETE SET NULL, indexado).
Todo via batch_alter_table para compatibilidad con SQLite. Reversible.
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c3d4e5f6a7b8'
down_revision = 'b7c2d9e4f1a5'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Tabla categories (HU-08)
    op.create_table(
        'categories',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=50), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'name', name='uq_user_category_name'),
    )
    op.create_index('ix_categories_user_id', 'categories', ['user_id'], unique=False)

    # 2. Extensión de tasks (HU-07 prioridad + HU-08 pertenencia)
    with op.batch_alter_table('tasks', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('priority', sa.String(length=10), nullable=False,
                      server_default='medium')
        )
        batch_op.add_column(sa.Column('category_id', sa.Integer(), nullable=True))
        batch_op.create_index('ix_tasks_category_id', ['category_id'], unique=False)
        batch_op.create_foreign_key(
            'fk_tasks_category_id_categories',
            'categories',
            ['category_id'],
            ['id'],
            ondelete='SET NULL',
        )


def downgrade():
    with op.batch_alter_table('tasks', schema=None) as batch_op:
        batch_op.drop_constraint('fk_tasks_category_id_categories', type_='foreignkey')
        batch_op.drop_index('ix_tasks_category_id')
        batch_op.drop_column('category_id')
        batch_op.drop_column('priority')

    op.drop_index('ix_categories_user_id', table_name='categories')
    op.drop_table('categories')
