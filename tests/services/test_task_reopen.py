import pytest
from src.taskcontrol.services.user_service import UserService
from src.taskcontrol.services.task_service import (
    TaskService,
    TaskNotFoundError,
    TaskDeletedError,
    InvalidStateTransitionError,
)
from src.taskcontrol.models.audit import AuditLog


@pytest.fixture
def test_user_id(app):
    with app.app_context():
        user = UserService.register_user("reopen@example.com", "Password123!")
        return user.id


@pytest.fixture
def second_user_id(app):
    with app.app_context():
        user = UserService.register_user("reopen2@example.com", "Password123!")
        return user.id


def _complete(app, user_id, task_id):
    with app.app_context():
        return TaskService.update_task_status(
            user_id=user_id, task_id=task_id, new_status="completed"
        )


def test_reopen_completed_returns_pending_with_distinct_audit(app, test_user_id):
    """completed→pending vía reopen_task + TASK_REOPENED (FR-007/FR-008/FR-009)."""
    with app.app_context():
        task = TaskService.create_task(user_id=test_user_id, title="Reabrir")
        TaskService.update_task_status(
            user_id=test_user_id, task_id=task.id, new_status="completed"
        )

        reopened = TaskService.reopen_task(user_id=test_user_id, task_id=task.id)

        assert reopened.status == "pending"
        audit = AuditLog.query.filter_by(
            action="TASK_REOPENED", entity_id=task.id
        ).first()
        assert audit is not None
        assert audit.actor_id == test_user_id
        # Distinguible de creación y cambio ordinario
        assert AuditLog.query.filter_by(
            action="TASK_CREATED", entity_id=task.id
        ).count() == 1
        assert (
            AuditLog.query.filter_by(action="STATUS_CHANGED", entity_id=task.id).count()
            >= 1
        )


def test_reopen_non_completed_rejected(app, test_user_id):
    """Reapertura sobre pending/in_progress → INVALID_STATE_TRANSITION (FR-010)."""
    with app.app_context():
        pending = TaskService.create_task(user_id=test_user_id, title="Pendiente")
        with pytest.raises(InvalidStateTransitionError):
            TaskService.reopen_task(user_id=test_user_id, task_id=pending.id)

        prog = TaskService.create_task(user_id=test_user_id, title="Progreso")
        TaskService.update_task_status(
            user_id=test_user_id, task_id=prog.id, new_status="in_progress"
        )
        with pytest.raises(InvalidStateTransitionError):
            TaskService.reopen_task(user_id=test_user_id, task_id=prog.id)


def test_reopen_deleted_rejected(app, test_user_id):
    """Reapertura sobre eliminada → bloqueo (FR-010)."""
    with app.app_context():
        task = TaskService.create_task(user_id=test_user_id, title="Eliminada")
        TaskService.update_task_status(
            user_id=test_user_id, task_id=task.id, new_status="completed"
        )
        TaskService.delete_task(user_id=test_user_id, task_id=task.id)

        with pytest.raises((TaskDeletedError, TaskNotFoundError)):
            TaskService.reopen_task(user_id=test_user_id, task_id=task.id)


def test_reopen_other_user_rejected(app, test_user_id, second_user_id):
    """Reapertura ajena → 403/404 sin alterar estado (FR-021/SC-007)."""
    with app.app_context():
        task = TaskService.create_task(user_id=test_user_id, title="Ajena")
        TaskService.update_task_status(
            user_id=test_user_id, task_id=task.id, new_status="completed"
        )
        with pytest.raises(TaskNotFoundError):
            TaskService.reopen_task(user_id=second_user_id, task_id=task.id)


def test_status_endpoint_still_blocked_completed_to_pending(app, test_user_id):
    """update_task_status(completed→pending) sigue 400 (contrato Inc.1 intacto)."""
    with app.app_context():
        task = TaskService.create_task(user_id=test_user_id, title="Bloqueada")
        TaskService.update_task_status(
            user_id=test_user_id, task_id=task.id, new_status="completed"
        )
        with pytest.raises(InvalidStateTransitionError):
            TaskService.update_task_status(
                user_id=test_user_id, task_id=task.id, new_status="pending"
            )


def test_second_concurrent_reopen_rejected_without_duplicate_audit(app, test_user_id):
    """Segunda reapertura concurrente → 400 sin duplicar TASK_REOPENED."""
    with app.app_context():
        task = TaskService.create_task(user_id=test_user_id, title="Concurrente")
        TaskService.update_task_status(
            user_id=test_user_id, task_id=task.id, new_status="completed"
        )
        TaskService.reopen_task(user_id=test_user_id, task_id=task.id)
        with pytest.raises(InvalidStateTransitionError):
            TaskService.reopen_task(user_id=test_user_id, task_id=task.id)

        assert (
            AuditLog.query.filter_by(action="TASK_REOPENED", entity_id=task.id).count()
            == 1
        )
