from datetime import datetime, timezone
from src.taskcontrol.extensions import db


class Notification(db.Model):
    """Aviso interno de asignación de tarea (HU-11).

    Historial persistente: marcar como leída jamás elimina la fila
    (``is_read=True, read_at=now``). Sin borrado ni caducidad.
    """

    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    task_id = db.Column(
        db.Integer, db.ForeignKey("tasks.id"), nullable=False, index=True
    )
    assigned_by = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False
    )
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    is_read = db.Column(db.Boolean, nullable=False, default=False)
    read_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "task_id": self.task_id,
            "assigned_by": self.assigned_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "is_read": self.is_read,
            "read_at": self.read_at.isoformat() if self.read_at else None,
        }
