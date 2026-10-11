from datetime import datetime, timezone
from src.taskcontrol.extensions import db


class Task(db.Model):
    """Modelo de Tarea (HU-01 a HU-04)."""

    __tablename__ = "tasks"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False, index=True
    )
    # Creador original informativo (HU-10): se fija en create_task() y jamás muta.
    # La visibilidad y los permisos derivan exclusivamente de user_id.
    created_by = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False
    )
    creator = db.relationship(
        "User", foreign_keys=[created_by], overlaps="created_tasks"
    )
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=True)
    due_date = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(20), nullable=False, default="pending")
    # Orden manual persistente del propietario (HU-16, Inc.5): denso 0..N-1
    # dentro de cada vista; las tareas nuevas van al final (max+1).
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    priority = db.Column(
        db.String(10), nullable=False, default="medium", server_default="medium"
    )
    category_id = db.Column(
        db.Integer,
        db.ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    category = db.relationship(
        "Category", backref=db.backref("tasks", lazy="dynamic")
    )
    is_deleted = db.Column(db.Boolean, nullable=False, default=False, index=True)
    deleted_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def to_dict(self):
        assigned = (
            self.created_by is not None and self.created_by != self.user_id
        )
        return {
            "id": self.id,
            "user_id": self.user_id,
            "created_by": self.created_by,
            "assigned": assigned,
            "assigned_by_email": self.assigned_by_email if assigned else None,
            "title": self.title,
            "description": self.description,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "status": self.status,
            "sort_order": self.sort_order,
            "priority": self.priority,
            "category_id": self.category_id,
            "category_name": self.category.name if self.category else None,
            "is_overdue": self.is_overdue,
            "is_deleted": self.is_deleted,
            "deleted_at": self.deleted_at.isoformat() if self.deleted_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @property
    def assigned_by_email(self) -> str | None:
        """Correo del último asignador (HU-10, etiqueta "Asignada a mí").

        Fuente: la notificación más reciente de esta tarea; si no existe
        (filas históricas), el correo del creador original.
        """
        from src.taskcontrol.extensions import db
        from src.taskcontrol.models.notification import Notification
        from src.taskcontrol.models.user import User

        note = (
            Notification.query.filter_by(task_id=self.id)
            .order_by(Notification.id.desc())
            .first()
        )
        if note is not None:
            assignor = db.session.get(User, note.assigned_by)
            if assignor is not None:
                return assignor.email
        if self.creator is not None:
            return self.creator.email
        return None

    @property
    def is_overdue(self) -> bool:
        """Indicador de vencida calculado SOLO en backend (HU-09, FR-016/17).

        True si y solo si: tiene due_date, due_date < fecha UTC del servidor,
        estado distinto de 'completed' y no eliminada. Nunca persistido.
        """
        if self.status == "completed" or getattr(self, "is_deleted", False):
            return False
        if not self.due_date:
            return False
        return self.due_date < datetime.now(timezone.utc).date()
