"""Tests bloqueantes del servicio de notificaciones (HU-11, FR-009–FR-013).

TDD (Principio IV): deben FALLAR antes de implementar
NotificationService y pasar después. La creación vía assign_task (US1)
ya está cubierta en test_task_assignment_service.py.
"""
import pytest
from src.taskcontrol.services.user_service import UserService
from src.taskcontrol.services.task_service import TaskService
from src.taskcontrol.services.notification_service import (
    NotificationService,
    NotificationNotFoundError,
)
from src.taskcontrol.models.notification import Notification


@pytest.fixture
def user_a_id(app):
    with app.app_context():
        return UserService.register_user("na@ejemplo.com", "Password123!").id


@pytest.fixture
def user_b_id(app):
    with app.app_context():
        return UserService.register_user("nb@ejemplo.com", "Password123!").id


@pytest.fixture
def user_c_id(app):
    with app.app_context():
        return UserService.register_user("nc@ejemplo.com", "Password123!").id


def _assign(app, actor_id, email, title="Informe"):
    with app.app_context():
        task = TaskService.create_task(user_id=actor_id, title=title)
        TaskService.assign_task(
            actor_id=actor_id, task_id=task.id, raw_email=email
        )
        return task.id


def test_list_returns_only_recipient_notifications(
    app, user_a_id, user_b_id, user_c_id
):
    """Solo el destinatario lista sus notificaciones (aislamiento)."""
    _assign(app, user_a_id, "nb@ejemplo.com", "T1")
    _assign(app, user_a_id, "nc@ejemplo.com", "T2")
    with app.app_context():
        notes_b = NotificationService.list_for_user(user_id=user_b_id)
        assert len(notes_b) == 1
        assert notes_b[0].user_id == user_b_id
        assert NotificationService.list_for_user(
            user_id=user_a_id
        ) == []


def test_unread_count_tracks_pending(app, user_a_id, user_b_id):
    """unread_count refleja pendientes y cae al marcar como leída."""
    _assign(app, user_a_id, "nb@ejemplo.com")
    with app.app_context():
        assert NotificationService.unread_count(user_id=user_b_id) == 1
        note = NotificationService.list_for_user(user_id=user_b_id)[0]
        NotificationService.mark_read(
            user_id=user_b_id, notification_id=note.id
        )
        assert NotificationService.unread_count(user_id=user_b_id) == 0


def test_mark_read_persists_history_as_read(app, user_a_id, user_b_id):
    """Marcar como leída persiste la fila en estado leída (no elimina)."""
    _assign(app, user_a_id, "nb@ejemplo.com")
    with app.app_context():
        note = NotificationService.list_for_user(user_id=user_b_id)[0]
        updated = NotificationService.mark_read(
            user_id=user_b_id, notification_id=note.id
        )
        assert updated.is_read is True
        assert updated.read_at is not None
        history = NotificationService.list_for_user(user_id=user_b_id)
        assert len(history) == 1
        assert history[0].is_read is True
        assert Notification.query.count() == 1


def test_mark_read_idempotent(app, user_a_id, user_b_id):
    """Marcar una notificación ya leída responde sin mutar ni duplicar."""
    _assign(app, user_a_id, "nb@ejemplo.com")
    with app.app_context():
        note = NotificationService.list_for_user(user_id=user_b_id)[0]
        first = NotificationService.mark_read(
            user_id=user_b_id, notification_id=note.id
        )
        second = NotificationService.mark_read(
            user_id=user_b_id, notification_id=note.id
        )
        assert second.is_read is True
        assert Notification.query.count() == 1
        assert first.read_at == second.read_at


def test_mark_all_read_marks_batch_and_returns_count(
    app, user_a_id, user_b_id
):
    """mark_all_read marca pendientes en lote y retorna marked_count."""
    _assign(app, user_a_id, "nb@ejemplo.com", "T1")
    _assign(app, user_a_id, "nb@ejemplo.com", "T2")
    with app.app_context():
        assert NotificationService.mark_all_read(
            user_id=user_b_id
        ) == 2
        assert NotificationService.unread_count(user_id=user_b_id) == 0
        assert len(NotificationService.list_for_user(
            user_id=user_b_id)) == 2
        # Segunda llamada idempotente: nada pendiente
        assert NotificationService.mark_all_read(
            user_id=user_b_id
        ) == 0


def test_mark_foreign_notification_raises_not_found(
    app, user_a_id, user_b_id, user_c_id
):
    """Leer notificación ajena → 404 sin distinguir existencia."""
    _assign(app, user_a_id, "nb@ejemplo.com")
    with app.app_context():
        note = NotificationService.list_for_user(user_id=user_b_id)[0]
        with pytest.raises(NotificationNotFoundError):
            NotificationService.mark_read(
                user_id=user_c_id, notification_id=note.id
            )
        assert NotificationService.unread_count(user_id=user_b_id) == 1


def test_mark_nonexistent_notification_raises_not_found(app, user_b_id):
    """Notificación inexistente → NotificationNotFoundError."""
    with app.app_context():
        with pytest.raises(NotificationNotFoundError):
            NotificationService.mark_read(
                user_id=user_b_id, notification_id=999999
            )


def test_orphan_notification_survives_task_soft_delete(
    app, user_a_id, user_b_id
):
    """Si la tarea se elimina tras notificar, el aviso persiste."""
    task_id = _assign(app, user_a_id, "nb@ejemplo.com")
    with app.app_context():
        TaskService.delete_task(user_id=user_b_id, task_id=task_id)
        notes = NotificationService.list_for_user(user_id=user_b_id)
        assert len(notes) == 1
        assert notes[0].task_id == task_id


def test_failed_assignment_creates_no_notification(app, user_a_id):
    """Intentos fallidos no generan notificaciones (FR-013)."""
    from src.taskcontrol.services.task_service import UserNotFoundError
    with app.app_context():
        task = TaskService.create_task(user_id=user_a_id, title="T")
        with pytest.raises(UserNotFoundError):
            TaskService.assign_task(
                actor_id=user_a_id, task_id=task.id,
                raw_email="nadie@ejemplo.com",
            )
        assert NotificationService.unread_count(user_id=user_a_id) == 0
        assert Notification.query.count() == 0
