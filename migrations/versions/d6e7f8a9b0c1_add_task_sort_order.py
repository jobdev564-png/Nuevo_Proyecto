"""add_task_sort_order: orden persistente por usuario (HU-16)

Revision ID: d6e7f8a9b0c1
Revises: 5c5f82e7afb6
Create Date: 2026-10-11

Incremento 5 (HU-16, Principio VI):
1. Añade columna `tasks.sort_order` (Integer, NOT NULL, DEFAULT 0).
2. Backfill determinista por usuario según orden de creación
   (`created_at`, desempate `id`) con valores densos 0..N-1 (R-05).
Todo via batch_alter_table para compatibilidad con SQLite. Reversible.
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd6e7f8a9b0c1'
down_revision = '5c5f82e7afb6'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('tasks', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('sort_order', sa.Integer(), nullable=False,
                      server_default='0')
        )

    # Backfill denso 0..N-1 por usuario (orden de creación).
    conn = op.get_bind()
    user_ids = [
        row[0]
        for row in conn.execute(sa.text("SELECT DISTINCT user_id FROM tasks"))
    ]
    for user_id in user_ids:
        rows = conn.execute(
            sa.text(
                "SELECT id FROM tasks WHERE user_id = :u "
                "ORDER BY created_at, id"
            ),
            {"u": user_id},
        ).fetchall()
        for position, (task_id,) in enumerate(rows):
            conn.execute(
                sa.text("UPDATE tasks SET sort_order = :p WHERE id = :i"),
                {"p": position, "i": task_id},
            )


def downgrade():
    with op.batch_alter_table('tasks', schema=None) as batch_op:
        batch_op.drop_column('sort_order')
