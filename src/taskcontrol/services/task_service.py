from datetime import date, datetime, timezone
from src.taskcontrol.extensions import db
from src.taskcontrol.models.task import Task
from src.taskcontrol.services.audit_service import AuditService


class TaskValidationError(Exception):
    """Error de validación para tareas."""
    pass


class TaskNotFoundError(Exception):
    """Tarea no encontrada o no perteneciente al usuario."""
    pass


class InvalidStateTransitionError(Exception):
    """Transición de estado no permitida por la máquina de estados."""
    pass


class TaskAlreadyDeletedError(Exception):
    """La tarea ya fue eliminada lógicamente (doble eliminación, FR-004)."""
    pass


class TaskDeletedError(Exception):
    """Operación bloqueada sobre una tarea con eliminación lógica (FR-005)."""
    pass


class TaskService:
    """Lógica de negocio del ciclo de vida y gestión de tareas (Principio II)."""

    VALID_TRANSITIONS = {
        "pending": {"in_progress", "completed"},
        "in_progress": {"pending", "completed"},
        "completed": set(),  # Bloqueada la reapertura en este incremento
    }

    VALID_PRIORITIES = {"high", "medium", "low"}
    DEFAULT_PRIORITY = "medium"

    @classmethod
    def _validate_priority(cls, priority: str):
        if priority not in cls.VALID_PRIORITIES:
            raise TaskValidationError(
                "Prioridad inválida. Debe ser 'high', 'medium' o 'low'"
            )

    @classmethod
    def _resolve_owned_category_id(cls, user_id: int, category_id=None):
        """Valida pertenencia de la categoría al usuario o lanza error."""
        from src.taskcontrol.models.category import Category

        if category_id is None or str(category_id).strip() == "":
            return None
        try:
            resolved = int(category_id)
        except (TypeError, ValueError):
            raise TaskValidationError(
                "La categoría indicada no existe o no pertenece a su usuario."
            )
        category = Category.query.filter_by(id=resolved, user_id=user_id).first()
        if category is None:
            raise TaskValidationError(
                "La categoría indicada no existe o no pertenece a su usuario."
            )
        return resolved

    @classmethod
    def create_task(
        cls,
        user_id: int,
        title: str,
        description: str = None,
        due_date: date = None,
        priority: str = None,
        category_id=None,
    ) -> Task:
        """Crea una nueva tarea para el usuario y audita el evento."""
        if not title or not title.strip():
            raise TaskValidationError("El título de la tarea es obligatorio y no puede estar vacío")

        clean_title = title.strip()
        if len(clean_title) > 150:
            raise TaskValidationError("El título no puede exceder 150 caracteres")

        if priority is None:
            priority = cls.DEFAULT_PRIORITY
        cls._validate_priority(priority)

        resolved_category_id = cls._resolve_owned_category_id(
            user_id=user_id, category_id=category_id
        )

        task = Task(
            user_id=user_id,
            title=clean_title,
            description=description.strip() if description else None,
            due_date=due_date,
            status="pending",
            priority=priority,
            category_id=resolved_category_id,
            is_deleted=False,
            deleted_at=None,
        )
        db.session.add(task)
        db.session.commit()

        # Auditoría obligatoria (Principio VIII)
        AuditService.log_event(
            actor_id=user_id,
            action="TASK_CREATED",
            entity_id=task.id,
            details={"title": clean_title, "status": "pending"},
        )
        db.session.commit()

        return task

    @classmethod
    def get_user_tasks(
        cls,
        user_id: int,
        status: str = None,
        category_id=None,
        sort_by: str = None,
        order: str = "desc",
    ):
        """Lista las tareas vivas del usuario (excluye eliminación lógica, FR-003).

        Filtros acumulativos (AND): status, category_id (entero o
        "none"/"uncategorized" para sin categoría). Orden: sort_by="priority"
        usa expresión CASE con desempate determinista; sin sort_by mantiene
        el orden legado por creación descendente.
        """
        query = Task.query.filter_by(user_id=user_id, is_deleted=False)
        if status in {"pending", "in_progress", "completed"}:
            query = query.filter_by(status=status)
        if category_id is not None:
            if isinstance(category_id, str) and category_id in {
                "none",
                "uncategorized",
            }:
                query = query.filter(Task.category_id.is_(None))
            else:
                try:
                    query = query.filter_by(category_id=int(category_id))
                except (TypeError, ValueError):
                    pass
        if sort_by == "priority":
            priority_order = db.case(
                (Task.priority == "high", 1),
                (Task.priority == "medium", 2),
                (Task.priority == "low", 3),
                else_=4,
            )
            # CASE numera urgencia (high=1); desc = Alta primero => ASC numérico.
            if order == "asc":
                query = query.order_by(
                    priority_order.desc(), Task.due_date.asc(), Task.id.desc()
                )
            else:
                query = query.order_by(
                    priority_order.asc(), Task.due_date.asc(), Task.id.desc()
                )
        else:
            query = query.order_by(Task.created_at.desc())
        return query.all()

    @classmethod
    def update_task_priority(
        cls, user_id: int, task_id: int, new_priority: str
    ) -> Task:
        """Modifica la prioridad de una tarea viva propia (HU-07, FR-004)."""
        task = cls._get_owned_task_any_state(user_id=user_id, task_id=task_id)
        cls._ensure_not_deleted(task)
        cls._validate_priority(new_priority)

        old_priority = task.priority
        task.priority = new_priority
        db.session.commit()

        AuditService.log_event(
            actor_id=user_id,
            action="TASK_PRIORITY_CHANGED",
            entity_id=task.id,
            details={"old_priority": old_priority, "new_priority": new_priority},
        )
        db.session.commit()

        return task

    @classmethod
    def update_task_category(
        cls, user_id: int, task_id: int, category_id=None
    ) -> Task:
        """Asocia o desvincula la categoría de una tarea viva propia (HU-08).

        category_id None/vacío → "sin categoría". Verifica que la categoría
        pertenezca al mismo usuario (anti-IDOR, FR-012).
        """
        task = cls._get_owned_task_any_state(user_id=user_id, task_id=task_id)
        cls._ensure_not_deleted(task)

        new_category_id = cls._resolve_owned_category_id(
            user_id=user_id, category_id=category_id
        )

        old_category_id = task.category_id
        task.category_id = new_category_id
        db.session.commit()

        AuditService.log_event(
            actor_id=user_id,
            action="TASK_CATEGORY_CHANGED",
            entity_id=task.id,
            details={
                "old_category_id": old_category_id,
                "new_category_id": new_category_id,
            },
        )
        db.session.commit()

        return task

    @classmethod
    def get_task_by_id(cls, user_id: int, task_id: int) -> Task:
        """Obtiene una tarea viva verificando propiedad (FR-021; eliminadas → 404)."""
        task = Task.query.filter_by(id=task_id, user_id=user_id, is_deleted=False).first()
        if not task:
            raise TaskNotFoundError("Tarea no encontrada")
        return task

    @classmethod
    def _get_owned_task_any_state(cls, user_id: int, task_id: int) -> Task:
        """Obtiene la tarea propia sin filtrar eliminación (uso interno)."""
        task = Task.query.filter_by(id=task_id, user_id=user_id).first()
        if not task:
            raise TaskNotFoundError("Tarea no encontrada")
        return task

    @classmethod
    def _ensure_not_deleted(cls, task: Task):
        if task.is_deleted:
            raise TaskDeletedError("No se puede operar sobre una tarea eliminada")

    @classmethod
    def delete_task(cls, user_id: int, task_id: int) -> Task:
        """Eliminación lógica con auditoría TASK_DELETED (HU-05, FR-001/FR-002/FR-006).

        Prohibido el borrado físico: jamás se usa db.session.delete(task).
        """
        task = cls._get_owned_task_any_state(user_id=user_id, task_id=task_id)
        if task.is_deleted:
            raise TaskAlreadyDeletedError("La tarea ya fue eliminada")
        task.is_deleted = True
        task.deleted_at = datetime.now(timezone.utc)
        db.session.commit()

        AuditService.log_event(
            actor_id=user_id,
            action="TASK_DELETED",
            entity_id=task.id,
            details={"status_at_delete": task.status,
                     "deleted_at": task.deleted_at.isoformat()},
        )
        db.session.commit()
        return task

    @classmethod
    def update_task_status(cls, user_id: int, task_id: int, new_status: str) -> Task:
        """Aplica una transición de estado a la tarea viva del usuario (FR-005).

        `completed → *` sigue bloqueado; la reapertura solo vía reopen_task (HU-06).
        """
        task = cls._get_owned_task_any_state(user_id=user_id, task_id=task_id)
        cls._ensure_not_deleted(task)

        if new_status not in cls.VALID_TRANSITIONS.get(task.status, set()):
            raise InvalidStateTransitionError(
                f"No se permite la transición desde '{task.status}' hacia '{new_status}' en este incremento"
            )

        old_status = task.status
        task.status = new_status
        db.session.commit()

        # Auditoría obligatoria (Principio VIII)
        AuditService.log_event(
            actor_id=user_id,
            action="STATUS_CHANGED",
            entity_id=task.id,
            details={"previous_status": old_status, "current_status": new_status},
        )
        db.session.commit()

        return task

    @classmethod
    def reopen_task(cls, user_id: int, task_id: int) -> Task:
        """Reapertura dedicada completed→pending con TASK_REOPENED (HU-06).

        Única vía legal desde completed; update_task_status sigue bloqueando
        completed→*. La segunda petición concurrente ve pending y recibe
        InvalidStateTransitionError sin duplicar el evento.
        """
        task = cls._get_owned_task_any_state(user_id=user_id, task_id=task_id)
        cls._ensure_not_deleted(task)
        if task.status != "completed":
            raise InvalidStateTransitionError(
                "Solo las tareas completadas pueden reabrirse"
            )
        task.status = "pending"
        db.session.commit()

        AuditService.log_event(
            actor_id=user_id,
            action="TASK_REOPENED",
            entity_id=task.id,
            details={"previous_status": "completed", "current_status": "pending"},
        )
        db.session.commit()
        return task

    @classmethod
    def update_task_details(
        cls,
        user_id: int,
        task_id: int,
        title: str,
        description: str = None,
        due_date: date = None,
    ) -> Task:
        """Actualiza los campos informativos de una tarea viva propia (FR-005)."""
        task = cls._get_owned_task_any_state(user_id=user_id, task_id=task_id)
        cls._ensure_not_deleted(task)

        if not title or not title.strip():
            raise TaskValidationError("El título de la tarea es obligatorio y no puede estar vacío")

        clean_title = title.strip()
        if len(clean_title) > 150:
            raise TaskValidationError("El título no puede exceder 150 caracteres")

        task.title = clean_title
        task.description = description.strip() if description else None
        task.due_date = due_date
        db.session.commit()

        # Auditoría obligatoria (Principio VIII)
        AuditService.log_event(
            actor_id=user_id,
            action="TASK_UPDATED",
            entity_id=task.id,
            details={"title": clean_title},
        )
        db.session.commit()

        return task
