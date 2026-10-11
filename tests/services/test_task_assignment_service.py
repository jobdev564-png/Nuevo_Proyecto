"""Tests bloqueantes de asignación de tareas (HU-10, FR-001–FR-008).

TDD (Principio IV): estos tests deben FALLAR antes de implementar
TaskService.assign_task() y pasar después. Cubren transferencia,
rechazos sin efectos, auditoría TASK_ASSIGNED, atomicidad y filtro origin.
"""
import pytest
from src.taskcontrol.services.user_service import UserService
from src.taskcontrol.services.task_service import (
    TaskService,
    TaskValidationError,
    TaskNotFoundError,
)
from src.taskcontrol.models.audit import AuditLog
from src.taskcontrol.models.notification import Notification


@pytest.fixture
def user_a_id(app):
    with app.app_context():
        return UserService.register_user("a@ejemplo.com", "Password123!").id


@pytest.fixture
def user_b_id(app):
    with app.app_context():
        return UserService.register_user("b@ejemplo.com", "Password123!").id


@pytest.fixture
def user_c_id(app):
    with app.app_context():
        return UserService.register_user("c@ejemplo.com", "Password123!").id


def _make_task(app, owner_id, title="Preparar informe"):
    with app.app_context():
        return TaskService.create_task(user_id=owner_id, title=title).id


def test_assign_transfers_ownership_and_keeps_creator(
    app, user_a_id, user_b_id
):
    """Asignación exitosa transfiere user_id; created_by jamás muta."""
    task_id = _make_task(app, user_a_id)
    with app.app_context():
        task = TaskService.assign_task(
            actor_id=user_a_id, task_id=task_id, raw_email="b@ejemplo.com"
        )
        assert task.user_id == user_b_id
        assert task.created_by == user_a_id


def test_assignee_lists_task_assignor_no_longer_does(
    app, user_a_id, user_b_id
):
    """Tras A→B, B lista la tarea y A ya no (FR-005, FR-007)."""
    task_id = _make_task(app, user_a_id)
    with app.app_context():
        TaskService.assign_task(
            actor_id=user_a_id, task_id=task_id, raw_email="b@ejemplo.com"
        )
        tasks_b = TaskService.get_user_tasks(user_id=user_b_id)
        assert [t.id for t in tasks_b] == [task_id]
        assert TaskService.get_user_tasks(user_id=user_a_id) == []


def test_origin_filter_classifies_mine_assigned_all(
    app, user_a_id, user_b_id
):
    """Filtro origin: mine/assigned/all según created_by vs user_id."""
    own_id = _make_task(app, user_b_id, title="Propia de B")
    delegated_id = _make_task(app, user_a_id, title="Delegada a B")
    with app.app_context():
        TaskService.assign_task(
            actor_id=user_a_id, task_id=delegated_id,
            raw_email="b@ejemplo.com",
        )
        assert {t.id for t in TaskService.get_user_tasks(
            user_id=user_b_id, origin="mine")} == {own_id}
        assert {t.id for t in TaskService.get_user_tasks(
            user_id=user_b_id, origin="assigned")} == {delegated_id}
        assert {t.id for t in TaskService.get_user_tasks(
            user_id=user_b_id, origin="all")} == {own_id, delegated_id}
        # origin ausente o inválido equivale a all
        assert {t.id for t in TaskService.get_user_tasks(
            user_id=user_b_id)} == {own_id, delegated_id}
        assert {t.id for t in TaskService.get_user_tasks(
            user_id=user_b_id, origin="bogus")} == {own_id, delegated_id}


def test_assign_to_unregistered_email_rejected_without_side_effects(
    app, user_a_id
):
    """Correo no registrado → error, sin mutación, auditoría ni notificación."""
    task_id = _make_task(app, user_a_id)
    with app.app_context():
        from src.taskcontrol.services.task_service import UserNotFoundError
        with pytest.raises(UserNotFoundError):
            TaskService.assign_task(
                actor_id=user_a_id, task_id=task_id,
                raw_email="fantasma@ejemplo.com",
            )
        task = TaskService.get_task_by_id(
            user_id=user_a_id, task_id=task_id
        )
        assert task.user_id == user_a_id
        assert AuditLog.query.filter_by(
            action="TASK_ASSIGNED", entity_id=task_id
        ).count() == 0
        assert Notification.query.filter_by(task_id=task_id).count() == 0


def test_assign_foreign_task_rejected(app, user_a_id, user_b_id, user_c_id):
    """Asignar tarea ajena se rechaza sin alterar nada (FR-004)."""
    task_id = _make_task(app, user_a_id)
    with app.app_context():
        with pytest.raises(TaskNotFoundError):
            TaskService.assign_task(
                actor_id=user_b_id, task_id=task_id,
                raw_email="c@ejemplo.com",
            )
        assert TaskService.get_task_by_id(
            user_id=user_a_id, task_id=task_id
        ).user_id == user_a_id
        assert AuditLog.query.filter_by(
            action="TASK_ASSIGNED", entity_id=task_id
        ).count() == 0


def test_assign_deleted_task_rejected(app, user_a_id, user_b_id):
    """Tarea eliminada lógicamente no puede asignarse (FR-004)."""
    task_id = _make_task(app, user_a_id)
    with app.app_context():
        TaskService.delete_task(user_id=user_a_id, task_id=task_id)
        with pytest.raises(TaskNotFoundError):
            TaskService.assign_task(
                actor_id=user_a_id, task_id=task_id,
                raw_email="b@ejemplo.com",
            )
        assert AuditLog.query.filter_by(
            action="TASK_ASSIGNED", entity_id=task_id
        ).count() == 0


def test_assign_to_self_rejected_without_side_effects(app, user_a_id):
    """Auto-asignación → error 400 sin auditoría ni notificación."""
    task_id = _make_task(app, user_a_id)
    with app.app_context():
        from src.taskcontrol.services.task_service import AssignToSelfError
        with pytest.raises(AssignToSelfError):
            TaskService.assign_task(
                actor_id=user_a_id, task_id=task_id,
                raw_email="a@ejemplo.com",
            )
        assert AuditLog.query.filter_by(
            action="TASK_ASSIGNED", entity_id=task_id
        ).count() == 0
        assert Notification.query.filter_by(task_id=task_id).count() == 0


def test_assign_invalid_email_format_rejected(app, user_a_id):
    """Email ausente o malformado → error de validación sin efectos."""
    task_id = _make_task(app, user_a_id)
    with app.app_context():
        with pytest.raises(TaskValidationError):
            TaskService.assign_task(
                actor_id=user_a_id, task_id=task_id, raw_email="no-es-email"
            )
        with pytest.raises(TaskValidationError):
            TaskService.assign_task(
                actor_id=user_a_id, task_id=task_id, raw_email="   "
            )


def test_assign_normalizes_email_case_and_spaces(app, user_a_id, user_b_id):
    """El destinatario se normaliza (strip + insensible a mayúsculas)."""
    task_id = _make_task(app, user_a_id)
    with app.app_context():
        task = TaskService.assign_task(
            actor_id=user_a_id, task_id=task_id,
            raw_email="  B@EJEMPLO.COM  ",
        )
        assert task.user_id == user_b_id


def test_successful_assign_emits_single_audit_with_required_fields(
    app, user_a_id, user_b_id
):
    """Cada asignación genera exactamente un TASK_ASSIGNED con los 4 campos."""
    task_id = _make_task(app, user_a_id)
    with app.app_context():
        TaskService.assign_task(
            actor_id=user_a_id, task_id=task_id, raw_email="b@ejemplo.com"
        )
        events = AuditLog.query.filter_by(
            action="TASK_ASSIGNED", entity_id=task_id
        ).all()
        assert len(events) == 1
        event = events[0]
        assert event.actor_id == user_a_id
        assert event.action == "TASK_ASSIGNED"
        assert event.entity_id == task_id
        assert event.timestamp is not None


def test_successful_assign_creates_exactly_one_notification(
    app, user_a_id, user_b_id
):
    """Cada asignación genera exactamente una notificación al asignado."""
    task_id = _make_task(app, user_a_id)
    with app.app_context():
        TaskService.assign_task(
            actor_id=user_a_id, task_id=task_id, raw_email="b@ejemplo.com"
        )
        notes = Notification.query.filter_by(task_id=task_id).all()
        assert len(notes) == 1
        assert notes[0].user_id == user_b_id
        assert notes[0].assigned_by == user_a_id
        assert notes[0].is_read is False


def test_reassign_by_current_owner_transfers_again(
    app, user_a_id, user_b_id, user_c_id
):
    """Reasignación B→C: C lista, B ya no; una auditoría y aviso por cambio."""
    task_id = _make_task(app, user_a_id)
    with app.app_context():
        TaskService.assign_task(
            actor_id=user_a_id, task_id=task_id, raw_email="b@ejemplo.com"
        )
        TaskService.assign_task(
            actor_id=user_b_id, task_id=task_id, raw_email="c@ejemplo.com"
        )
        assert [t.id for t in TaskService.get_user_tasks(
            user_id=user_c_id)] == [task_id]
        assert TaskService.get_user_tasks(user_id=user_b_id) == []
        assert AuditLog.query.filter_by(
            action="TASK_ASSIGNED", entity_id=task_id
        ).count() == 2
        assert Notification.query.filter_by(task_id=task_id).count() == 2


def test_atomicity_failure_leaves_no_partial_effects(
    app, user_a_id, user_b_id, monkeypatch
):
    """Fallo inyectado a mitad de transacción ⇒ ni transferencia ni aviso."""
    from src.taskcontrol.services import task_service as ts_module
    task_id = _make_task(app, user_a_id)
    with app.app_context():
        real_log = ts_module.AuditService.log_event

        def _boom(*args, **kwargs):
            raise RuntimeError("fallo inyectado")

        monkeypatch.setattr(
            ts_module.AuditService, "log_event", _boom
        )
        with pytest.raises(RuntimeError):
            TaskService.assign_task(
                actor_id=user_a_id, task_id=task_id,
                raw_email="b@ejemplo.com",
            )
        task = TaskService.get_task_by_id(
            user_id=user_a_id, task_id=task_id
        )
        assert task.user_id == user_a_id
        assert Notification.query.filter_by(task_id=task_id).count() == 0
        assert real_log is not None
