from datetime import datetime, timezone
from src.taskcontrol.extensions import db
from src.taskcontrol.models.notification import Notification


class NotificationNotFoundError(Exception):
    """Notificación inexistente o de otro usuario (HU-11)."""
    pass


class NotificationService:
    """Lógica de negocio de notificaciones internas (Principio II).

    Historial persistente: marcar como leída jamás elimina filas.
    """

    @classmethod
    def list_for_user(cls, user_id: int, unread_only: bool = False):
        """Notificaciones del destinatario, recientes primero."""
        query = Notification.query.filter_by(user_id=user_id).order_by(
            Notification.created_at.desc(), Notification.id.desc()
        )
        if unread_only:
            query = query.filter_by(is_read=False)
        return query.all()

    @classmethod
    def unread_count(cls, user_id: int) -> int:
        """Número de notificaciones pendientes del usuario."""
        return Notification.query.filter_by(
            user_id=user_id, is_read=False
        ).count()

    @classmethod
    def _get_owned(cls, user_id: int, notification_id: int) -> Notification:
        note = Notification.query.filter_by(
            id=notification_id, user_id=user_id
        ).first()
        if note is None:
            raise NotificationNotFoundError("Notificación no encontrada")
        return note

    @classmethod
    def mark_read(cls, user_id: int, notification_id: int) -> Notification:
        """Marca una notificación como leída (idempotente, persiste)."""
        note = cls._get_owned(user_id, notification_id)
        if not note.is_read:
            note.is_read = True
            note.read_at = datetime.now(timezone.utc)
            db.session.commit()
        return note

    @classmethod
    def mark_all_read(cls, user_id: int) -> int:
        """Marca todas las pendientes del usuario; retorna marked_count."""
        pending = Notification.query.filter_by(
            user_id=user_id, is_read=False
        ).all()
        now = datetime.now(timezone.utc)
        for note in pending:
            note.is_read = True
            note.read_at = now
        db.session.commit()
        return len(pending)

    @classmethod
    def list_detailed(cls, user_id: int, unread_only: bool = False):
        """Items enriquecidos solo-lectura: título y correo del asignador."""
        from src.taskcontrol.models.task import Task
        from src.taskcontrol.models.user import User

        items = []
        for note in cls.list_for_user(
            user_id=user_id, unread_only=unread_only
        ):
            task = db.session.get(Task, note.task_id)
            assignor = db.session.get(User, note.assigned_by)
            items.append(
                {
                    "id": note.id,
                    "task_id": note.task_id,
                    "task_title": task.title if task else None,
                    "assigned_by": note.assigned_by,
                    "assigned_by_email": assignor.email
                    if assignor
                    else None,
                    "created_at": note.created_at.isoformat()
                    if note.created_at
                    else None,
                    "is_read": note.is_read,
                    "read_at": note.read_at.isoformat()
                    if note.read_at
                    else None,
                }
            )
        return items
