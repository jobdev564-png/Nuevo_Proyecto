import pytest
from src.taskcontrol.services.user_service import UserService
from src.taskcontrol.services.task_service import (
    TaskService,
    TaskNotFoundError,
    TaskAlreadyDeletedError,
    TaskDeletedError,
    InvalidStateTransitionError,
)
from src.taskcontrol.models.audit import AuditLog


@pytest.fixture
def test_user_id(app):
    with app.app_context():
        user = UserService.register_user("softdel@example.com", "Password123!")
        return user.id


@pytest.fixture
def second_user_id(app):
    with app.app_context():
        user = UserService.register_user("softdel2@example.com", "Password123!")
        return user.id


def _audit_count(action, entity_id):
    return AuditLog.query.filter_by(action=action, entity_id=entity_id).count()


def test_delete_task_marks_deleted_and_audits(app, test_user_id):
    """Eliminación lógica: marca, preserva fila y audita TASK_DELETED (FR-002/FR-006)."""
    with app.app_context():
        task = TaskService.create_task(user_id=test_user_id, title="Tarea a depurar")
        task_id = task.id

        deleted = TaskService.delete_task(user_id=test_user_id, task_id=task_id)

        assert deleted.is_deleted is True
        assert deleted.deleted_at is not None

        # La fila persiste físicamente con su historial
        from src.taskcontrol.models.task import Task
        row = Task.query.filter_by(id=task_id).first()
        assert row is not None
        assert row.is_deleted is True

        audit = AuditLog.query.filter_by(action="TASK_DELETED", entity_id=task_id).first()
        assert audit is not None
        assert audit.actor_id == test_user_id
        assert audit.timestamp is not None


def test_deleted_task_excluded_from_listing(app, test_user_id):
    """Las eliminadas no aparecen en get_user_tasks ni en conteos (FR-003/SC-001)."""
    with app.app_context():
        keep = TaskService.create_task(user_id=test_user_id, title="Viva")
        drop = TaskService.create_task(user_id=test_user_id, title="A eliminar")
        TaskService.delete_task(user_id=test_user_id, task_id=drop.id)

        tasks = TaskService.get_user_tasks(user_id=test_user_id)
        ids = [t.id for t in tasks]
        assert keep.id in ids
        assert drop.id not in ids

        pending = TaskService.get_user_tasks(user_id=test_user_id, status="pending")
        assert all(t.id != drop.id for t in pending)


def test_double_delete_rejected_without_new_audit(app, test_user_id):
    """Segunda eliminación: error controlado, sin mutación ni doble auditoría (FR-004)."""
    with app.app_context():
        task = TaskService.create_task(user_id=test_user_id, title="Doble")
        TaskService.delete_task(user_id=test_user_id, task_id=task.id)
        assert _audit_count("TASK_DELETED", task.id) == 1

        with pytest.raises((TaskAlreadyDeletedError, TaskNotFoundError)):
            TaskService.delete_task(user_id=test_user_id, task_id=task.id)

        assert _audit_count("TASK_DELETED", task.id) == 1


def test_delete_other_user_task_rejected(app, test_user_id, second_user_id):
    """Eliminar tarea ajena: rechazo sin alterar la tarea (FR-021/SC-007)."""
    with app.app_context():
        task = TaskService.create_task(user_id=test_user_id, title="Ajena")
        with pytest.raises(TaskNotFoundError):
            TaskService.delete_task(user_id=second_user_id, task_id=task.id)

        from src.taskcontrol.models.task import Task
        row = Task.query.filter_by(id=task.id).first()
        assert row.is_deleted is False


def test_edit_status_blocked_on_deleted(app, test_user_id):
    """Edición y cambio ordinario bloqueados sobre eliminadas (FR-005)."""
    with app.app_context():
        task = TaskService.create_task(user_id=test_user_id, title="Bloqueada")
        TaskService.delete_task(user_id=test_user_id, task_id=task.id)

        with pytest.raises((TaskDeletedError, TaskNotFoundError)):
            TaskService.update_task_details(
                user_id=test_user_id, task_id=task.id, title="Editada"
            )
        with pytest.raises((TaskDeletedError, TaskNotFoundError, InvalidStateTransitionError)):
            TaskService.update_task_status(
                user_id=test_user_id, task_id=task.id, new_status="in_progress"
            )
        with pytest.raises((TaskDeletedError, TaskNotFoundError)):
            TaskService.get_task_by_id(user_id=test_user_id, task_id=task.id)
