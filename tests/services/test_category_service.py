import pytest
from src.taskcontrol.services.user_service import UserService
from src.taskcontrol.services.task_service import TaskService, TaskValidationError
from src.taskcontrol.services.category_service import (
    CategoryService,
    CategoryValidationError,
    CategoryNotFoundError,
    CategoryDuplicateError,
)
from src.taskcontrol.models.audit import AuditLog


@pytest.fixture
def test_user_id(app):
    with app.app_context():
        user = UserService.register_user("catowner@example.com", "Password123!")
        return user.id


@pytest.fixture
def second_user_id(app):
    with app.app_context():
        user = UserService.register_user("catsecond@example.com", "Password123!")
        return user.id


# --- Incremento 3 / HU-08: Categorías (US2) ---

def test_create_category_success_and_audit(app, test_user_id):
    """Crear categoría propia con nombre válido genera CATEGORY_CREATED."""
    with app.app_context():
        cat = CategoryService.create_category(
            user_id=test_user_id, name="Trabajo", description="Proyectos"
        )
        assert cat.id is not None
        assert cat.name == "Trabajo"
        audit = AuditLog.query.filter_by(
            action="CATEGORY_CREATED", entity_id=cat.id
        ).first()
        assert audit is not None
        assert audit.actor_id == test_user_id


def test_create_category_blank_or_too_long_rejected(app, test_user_id):
    """Nombre vacío/solo-espacios o > 50 caracteres se rechaza (FR-008)."""
    with app.app_context():
        with pytest.raises(CategoryValidationError):
            CategoryService.create_category(user_id=test_user_id, name="   ")
        with pytest.raises(CategoryValidationError):
            CategoryService.create_category(user_id=test_user_id, name="A" * 51)


def test_category_name_unique_per_user(app, test_user_id, second_user_id):
    """Duplicado propio (case-insensitive) se rechaza; homónimo ajeno se permite."""
    with app.app_context():
        CategoryService.create_category(user_id=test_user_id, name="Trabajo")
        with pytest.raises(CategoryDuplicateError):
            CategoryService.create_category(user_id=test_user_id, name="  trabajo  ")
        other = CategoryService.create_category(
            user_id=second_user_id, name="Trabajo"
        )
        assert other.id is not None


def test_list_categories_only_own(app, test_user_id, second_user_id):
    """El listado expone exclusivamente las categorías propias (FR-010)."""
    with app.app_context():
        CategoryService.create_category(user_id=test_user_id, name="Mía")
        CategoryService.create_category(user_id=second_user_id, name="Ajena")
        cats = CategoryService.get_user_categories(user_id=test_user_id)
        assert [c.name for c in cats] == ["Mía"]


def test_delete_category_unlinks_tasks_and_does_not_delete_them(
    app, test_user_id
):
    """Eliminar categoría preserva el 100% de tareas con category_id NULL."""
    with app.app_context():
        cat = CategoryService.create_category(user_id=test_user_id, name="Temp")
        t1 = TaskService.create_task(user_id=test_user_id, title="Una")
        t2 = TaskService.create_task(user_id=test_user_id, title="Dos")
        TaskService.update_task_category(
            user_id=test_user_id, task_id=t1.id, category_id=cat.id
        )
        TaskService.update_task_category(
            user_id=test_user_id, task_id=t2.id, category_id=cat.id
        )
        result = CategoryService.delete_category(
            user_id=test_user_id, category_id=cat.id
        )
        assert result["unlinked_tasks"] == 2
        for tid in (t1.id, t2.id):
            task = TaskService.get_task_by_id(user_id=test_user_id, task_id=tid)
            assert task.category_id is None
        audit = AuditLog.query.filter_by(
            action="CATEGORY_DELETED", entity_id=cat.id
        ).first()
        assert audit is not None


def test_delete_foreign_category_not_found(app, test_user_id, second_user_id):
    """Eliminar categoría ajena → CategoryNotFoundError."""
    with app.app_context():
        cat = CategoryService.create_category(
            user_id=second_user_id, name="Ajena"
        )
        with pytest.raises(CategoryNotFoundError):
            CategoryService.delete_category(
                user_id=test_user_id, category_id=cat.id
            )


def test_cannot_assign_foreign_category(app, test_user_id, second_user_id):
    """Asignar categoría de otro usuario se rechaza (FR-012, anti-IDOR)."""
    with app.app_context():
        task = TaskService.create_task(user_id=test_user_id, title="Mía")
        foreign = CategoryService.create_category(
            user_id=second_user_id, name="Ajena"
        )
        with pytest.raises(TaskValidationError):
            TaskService.update_task_category(
                user_id=test_user_id, task_id=task.id, category_id=foreign.id
            )


def test_unlink_category_sets_none_and_audits(app, test_user_id):
    """Remover la categoría deja la tarea 'sin categoría' y audita el cambio."""
    with app.app_context():
        cat = CategoryService.create_category(user_id=test_user_id, name="X")
        task = TaskService.create_task(user_id=test_user_id, title="Y")
        TaskService.update_task_category(
            user_id=test_user_id, task_id=task.id, category_id=cat.id
        )
        updated = TaskService.update_task_category(
            user_id=test_user_id, task_id=task.id, category_id=None
        )
        assert updated.category_id is None
        audits = AuditLog.query.filter_by(
            action="TASK_CATEGORY_CHANGED", entity_id=task.id
        ).all()
        assert len(audits) == 2
