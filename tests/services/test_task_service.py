from datetime import date
import pytest
from src.taskcontrol.services.user_service import UserService
from src.taskcontrol.services.task_service import (
    TaskService,
    TaskValidationError,
    TaskNotFoundError,
    InvalidStateTransitionError,
)
from src.taskcontrol.models.audit import AuditLog


@pytest.fixture
def test_user_id(app):
    with app.app_context():
        user = UserService.register_user("taskowner@example.com", "Password123!")
        return user.id


@pytest.fixture
def second_user_id(app):
    with app.app_context():
        user = UserService.register_user("seconduser@example.com", "Password123!")
        return user.id


# --- US3: Creación de Tareas (HU-01) ---

def test_create_task_success(app, test_user_id):
    """Verifica la creación exitosa de una tarea con estado pending y log de auditoría."""
    with app.app_context():
        task = TaskService.create_task(
            user_id=test_user_id,
            title="Mi primera tarea",
            description="Descripción opcional",
            due_date=date(2026, 10, 15),
        )
        assert task.id is not None
        assert task.title == "Mi primera tarea"
        assert task.description == "Descripción opcional"
        assert task.status == "pending"
        assert task.user_id == test_user_id

        # Verificar generación de auditoría (Principio VIII)
        audit = AuditLog.query.filter_by(
            action="TASK_CREATED", entity_id=task.id
        ).first()
        assert audit is not None
        assert audit.actor_id == test_user_id


def test_create_task_empty_title_fails(app, test_user_id):
    """Verifica que se rechace un título vacío o con solo espacios."""
    with app.app_context():
        with pytest.raises(TaskValidationError):
            TaskService.create_task(user_id=test_user_id, title="   ")


def test_create_task_title_too_long(app, test_user_id):
    """Verifica que se rechace un título que exceda 150 caracteres."""
    with app.app_context():
        with pytest.raises(TaskValidationError):
            TaskService.create_task(user_id=test_user_id, title="A" * 151)


# --- US4: Listado y Filtrado de Tareas (HU-02) ---

def test_get_user_tasks_isolation(app, test_user_id, second_user_id):
    """Verifica aislamiento estricto entre usuarios (Principio VII / Cero IDOR)."""
    with app.app_context():
        TaskService.create_task(user_id=test_user_id, title="Tarea de Usuario 1")
        TaskService.create_task(user_id=second_user_id, title="Tarea de Usuario 2")

        tasks_user1 = TaskService.get_user_tasks(user_id=test_user_id)
        assert len(tasks_user1) == 1
        assert tasks_user1[0].title == "Tarea de Usuario 1"

        tasks_user2 = TaskService.get_user_tasks(user_id=second_user_id)
        assert len(tasks_user2) == 1
        assert tasks_user2[0].title == "Tarea de Usuario 2"


def test_filter_tasks_by_status(app, test_user_id):
    """Verifica que el filtrado por estado retorne únicamente las tareas coincidentes."""
    with app.app_context():
        t1 = TaskService.create_task(user_id=test_user_id, title="Tarea 1")
        t2 = TaskService.create_task(user_id=test_user_id, title="Tarea 2")
        TaskService.update_task_status(
            user_id=test_user_id, task_id=t2.id, new_status="completed"
        )

        pending = TaskService.get_user_tasks(user_id=test_user_id, status="pending")
        completed = TaskService.get_user_tasks(user_id=test_user_id, status="completed")

        assert len(pending) == 1
        assert pending[0].id == t1.id
        assert len(completed) == 1
        assert completed[0].id == t2.id


# --- US5: Cambio de Estado de Tareas (HU-03) ---

def test_task_state_transitions(app, test_user_id):
    """Verifica transiciones válidas y emisión de log de auditoría STATUS_CHANGED."""
    with app.app_context():
        task = TaskService.create_task(user_id=test_user_id, title="Tarea Flujo")

        # pending -> in_progress
        task = TaskService.update_task_status(
            user_id=test_user_id, task_id=task.id, new_status="in_progress"
        )
        assert task.status == "in_progress"

        # in_progress -> completed
        task = TaskService.update_task_status(
            user_id=test_user_id, task_id=task.id, new_status="completed"
        )
        assert task.status == "completed"

        # Verificar auditoría
        audits = AuditLog.query.filter_by(
            action="STATUS_CHANGED", entity_id=task.id
        ).all()
        assert len(audits) == 2


def test_reopening_completed_task_fails(app, test_user_id):
    """Verifica que la reapertura (completed -> pending) esté explícitamente bloqueada en este incremento."""
    with app.app_context():
        task = TaskService.create_task(user_id=test_user_id, title="Tarea Finalizada")
        TaskService.update_task_status(
            user_id=test_user_id, task_id=task.id, new_status="completed"
        )

        with pytest.raises(InvalidStateTransitionError):
            TaskService.update_task_status(
                user_id=test_user_id, task_id=task.id, new_status="pending"
            )


# --- US6: Edición de Tareas (HU-04) ---

def test_update_task_details_success(app, test_user_id):
    """Verifica edición de campos informativos y registro en auditoría."""
    with app.app_context():
        task = TaskService.create_task(user_id=test_user_id, title="Título Inicial")
        updated = TaskService.update_task_details(
            user_id=test_user_id,
            task_id=task.id,
            title="Título Modificado",
            description="Nueva descripción",
            due_date=date(2026, 11, 1),
        )
        assert updated.title == "Título Modificado"
        assert updated.description == "Nueva descripción"
        assert updated.due_date == date(2026, 11, 1)

        audit = AuditLog.query.filter_by(
            action="TASK_UPDATED", entity_id=task.id
        ).first()
        assert audit is not None


def test_update_task_empty_title_fails(app, test_user_id):
    """Verifica que editar con título vacío sea rechazado."""
    with app.app_context():
        task = TaskService.create_task(user_id=test_user_id, title="Título Válido")
        with pytest.raises(TaskValidationError):
            TaskService.update_task_details(
                user_id=test_user_id, task_id=task.id, title=""
            )


def test_update_task_unauthorized_user(app, test_user_id, second_user_id):
    """Verifica que un usuario no pueda editar tareas de otro usuario (Cero IDOR)."""
    with app.app_context():
        task = TaskService.create_task(user_id=test_user_id, title="Tarea de User 1")
        with pytest.raises(TaskNotFoundError):
            TaskService.update_task_details(
                user_id=second_user_id, task_id=task.id, title="Hack intento"
            )


# --- Incremento 3 / HU-07: Prioridad de Tareas (US1) ---

def test_default_priority_is_medium(app, test_user_id):
    """Sin prioridad explícita la tarea se almacena con 'medium' (FR-002)."""
    with app.app_context():
        task = TaskService.create_task(user_id=test_user_id, title="Sin prioridad")
        assert task.priority == "medium"


def test_invalid_priority_rejected(app, test_user_id):
    """Valores fuera de {high, medium, low} se rechazan (FR-003)."""
    with app.app_context():
        with pytest.raises(TaskValidationError) as exc:
            TaskService.create_task(
                user_id=test_user_id, title="Mala prioridad", priority="urgent"
            )
        assert "Prioridad inválida" in str(exc.value)
        task = TaskService.create_task(
            user_id=test_user_id, title="Base", priority="low"
        )
        with pytest.raises(TaskValidationError):
            TaskService.update_task_priority(
                user_id=test_user_id, task_id=task.id, new_priority="critical"
            )


def test_update_task_priority_persists_and_audits(app, test_user_id):
    """El propietario cambia la prioridad y se audita TASK_PRIORITY_CHANGED."""
    with app.app_context():
        task = TaskService.create_task(
            user_id=test_user_id, title="Cambiable", priority="low"
        )
        updated = TaskService.update_task_priority(
            user_id=test_user_id, task_id=task.id, new_priority="high"
        )
        assert updated.priority == "high"
        audit = AuditLog.query.filter_by(
            action="TASK_PRIORITY_CHANGED", entity_id=task.id
        ).first()
        assert audit is not None
        assert audit.actor_id == test_user_id


def test_tasks_ordered_by_priority_desc(app, test_user_id):
    """Orden descendente: high -> medium -> low (FR-005)."""
    with app.app_context():
        TaskService.create_task(user_id=test_user_id, title="Baja", priority="low")
        TaskService.create_task(user_id=test_user_id, title="Alta", priority="high")
        TaskService.create_task(
            user_id=test_user_id, title="Media", priority="medium"
        )
        tasks = TaskService.get_user_tasks(
            user_id=test_user_id, sort_by="priority", order="desc"
        )
        assert [t.priority for t in tasks] == ["high", "medium", "low"]


def test_tasks_ordered_by_priority_asc(app, test_user_id):
    """Orden ascendente: low -> medium -> high (FR-005)."""
    with app.app_context():
        TaskService.create_task(user_id=test_user_id, title="Alta", priority="high")
        TaskService.create_task(user_id=test_user_id, title="Baja", priority="low")
        TaskService.create_task(
            user_id=test_user_id, title="Media", priority="medium"
        )
        tasks = TaskService.get_user_tasks(
            user_id=test_user_id, sort_by="priority", order="asc"
        )
        assert [t.priority for t in tasks] == ["low", "medium", "high"]


def test_tasks_order_with_status_filter(app, test_user_id):
    """El orden por prioridad se combina con filtros de estado (FR-007)."""
    with app.app_context():
        low = TaskService.create_task(
            user_id=test_user_id, title="Baja pendiente", priority="low"
        )
        high = TaskService.create_task(
            user_id=test_user_id, title="Alta pendiente", priority="high"
        )
        done = TaskService.create_task(
            user_id=test_user_id, title="Alta completada", priority="high"
        )
        TaskService.update_task_status(
            user_id=test_user_id, task_id=done.id, new_status="completed"
        )
        tasks = TaskService.get_user_tasks(
            user_id=test_user_id, status="pending", sort_by="priority", order="desc"
        )
        assert {t.id for t in tasks} == {low.id, high.id}
        assert [t.priority for t in tasks] == ["high", "low"]


def test_priority_order_tiebreak_deterministic(app, test_user_id):
    """Empate de prioridad: desempate por due_date asc y luego id desc (FR-006)."""
    with app.app_context():
        t1 = TaskService.create_task(
            user_id=test_user_id, title="Lejana",
            due_date=date(2026, 12, 31), priority="high",
        )
        t2 = TaskService.create_task(
            user_id=test_user_id, title="Cercana",
            due_date=date(2026, 10, 20), priority="high",
        )
        tasks = TaskService.get_user_tasks(
            user_id=test_user_id, sort_by="priority", order="desc"
        )
        assert [t.id for t in tasks] == [t2.id, t1.id]
        a = TaskService.create_task(
            user_id=test_user_id, title="Sin fecha A", priority="low"
        )
        b = TaskService.create_task(
            user_id=test_user_id, title="Sin fecha B", priority="low"
        )
        tasks = TaskService.get_user_tasks(
            user_id=test_user_id, sort_by="priority", order="desc"
        )
        low_ids = [t.id for t in tasks if t.priority == "low"]
        assert low_ids == sorted(low_ids, reverse=True)


# --- Incremento 3 / HU-09: Tareas Vencidas (US3) ---

def test_overdue_when_due_date_passed_and_pending(app, test_user_id):
    """Fecha pasada + pending/in_progress → is_overdue True (FR-017)."""
    with app.app_context():
        from datetime import timedelta
        yesterday = date.today() - timedelta(days=1)
        task = TaskService.create_task(
            user_id=test_user_id, title="Atrasada", due_date=yesterday
        )
        assert task.is_overdue is True
        TaskService.update_task_status(
            user_id=test_user_id, task_id=task.id, new_status="in_progress"
        )
        assert task.is_overdue is True


def test_never_overdue_when_completed(app, test_user_id):
    """BLOQUEANTE: fecha pasada + completed → is_overdue False (FR-018)."""
    with app.app_context():
        from datetime import timedelta
        yesterday = date.today() - timedelta(days=1)
        task = TaskService.create_task(
            user_id=test_user_id, title="Lista", due_date=yesterday
        )
        TaskService.update_task_status(
            user_id=test_user_id, task_id=task.id, new_status="completed"
        )
        assert task.is_overdue is False


def test_never_overdue_when_today_or_future(app, test_user_id):
    """Fecha de hoy o futura → is_overdue False."""
    with app.app_context():
        from datetime import timedelta
        today_task = TaskService.create_task(
            user_id=test_user_id, title="Hoy", due_date=date.today()
        )
        future_task = TaskService.create_task(
            user_id=test_user_id, title="Mañana",
            due_date=date.today() + timedelta(days=1),
        )
        assert today_task.is_overdue is False
        assert future_task.is_overdue is False


def test_never_overdue_when_no_due_date(app, test_user_id):
    """Sin fecha límite → is_overdue False (FR-019)."""
    with app.app_context():
        task = TaskService.create_task(user_id=test_user_id, title="Sin fecha")
        assert task.is_overdue is False


def test_never_overdue_when_deleted(app, test_user_id):
    """Tarea eliminada lógicamente → is_overdue False."""
    with app.app_context():
        from datetime import timedelta
        task = TaskService.create_task(
            user_id=test_user_id, title="Borrada",
            due_date=date.today() - timedelta(days=1),
        )
        TaskService.delete_task(user_id=test_user_id, task_id=task.id)
        assert task.is_overdue is False
