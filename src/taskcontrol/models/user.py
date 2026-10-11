from datetime import datetime, timezone
from src.taskcontrol.extensions import db


class User(db.Model):
    """Modelo de Usuario (HU-12, HU-13)."""

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    # Relación 1 a N con Task como responsable actual (HU-10: user_id muta
    # en cada asignación; foreign_keys explícito porque Task tiene dos FK a users)
    tasks = db.relationship(
        "Task",
        backref="user",
        lazy=True,
        cascade="all, delete-orphan",
        foreign_keys="Task.user_id",
    )
    # Tareas creadas por el usuario (informativo, HU-10: created_by inmutable)
    created_tasks = db.relationship(
        "Task", lazy=True, foreign_keys="Task.created_by"
    )
    # Notificaciones recibidas (HU-11)
    notifications = db.relationship(
        "Notification",
        backref="recipient",
        lazy=True,
        cascade="all, delete-orphan",
        foreign_keys="Notification.user_id",
    )

    def to_dict(self):
        return {
            "id": self.id,
            "email": self.email,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
