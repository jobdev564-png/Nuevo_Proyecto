from src.taskcontrol.extensions import db
from src.taskcontrol.models.task import Task
from src.taskcontrol.models.category import Category
from src.taskcontrol.services.audit_service import AuditService


class CategoryValidationError(Exception):
    """Error de validación para categorías (nombre vacío o > 50)."""
    pass


class CategoryNotFoundError(Exception):
    """Categoría inexistente o no perteneciente al usuario."""
    pass


class CategoryDuplicateError(Exception):
    """Nombre de categoría duplicado para el mismo usuario."""
    pass


class CategoryService:
    """Lógica de negocio de categorías y desvinculación segura (HU-08)."""

    MAX_NAME_LENGTH = 50

    @classmethod
    def _clean_name(cls, name: str) -> str:
        if name is None:
            raise CategoryValidationError(
                "El nombre de la categoría es obligatorio y debe tener "
                "como máximo 50 caracteres."
            )
        clean = name.strip()
        if not clean or len(clean) > cls.MAX_NAME_LENGTH:
            raise CategoryValidationError(
                "El nombre de la categoría es obligatorio y debe tener "
                "como máximo 50 caracteres."
            )
        return clean

    @classmethod
    def create_category(
        cls, user_id: int, name: str, description: str = None
    ) -> Category:
        """Crea una categoría propia con unicidad por usuario (FR-008/FR-009)."""
        clean_name = cls._clean_name(name)

        existing = Category.query.filter_by(user_id=user_id).all()
        if any(c.name.strip().lower() == clean_name.lower() for c in existing):
            raise CategoryDuplicateError(
                "Ya existe una categoría con ese nombre en su cuenta."
            )

        category = Category(
            user_id=user_id,
            name=clean_name,
            description=description.strip() if description else None,
        )
        db.session.add(category)
        db.session.commit()

        AuditService.log_event(
            actor_id=user_id,
            action="CATEGORY_CREATED",
            entity_id=category.id,
            details={"name": clean_name},
        )
        db.session.commit()

        return category

    @classmethod
    def get_user_categories(cls, user_id: int):
        """Lista exclusivamente las categorías propias ordenadas por nombre."""
        return (
            Category.query.filter_by(user_id=user_id)
            .order_by(Category.name.asc())
            .all()
        )

    @classmethod
    def get_category_by_id(cls, user_id: int, category_id: int) -> Category:
        """Obtiene una categoría propia o lanza CategoryNotFoundError."""
        category = Category.query.filter_by(
            id=category_id, user_id=user_id
        ).first()
        if not category:
            raise CategoryNotFoundError("Categoría no encontrada.")
        return category

    @classmethod
    def delete_category(cls, user_id: int, category_id: int) -> dict:
        """Elimina una categoría propia desvinculando tareas (SET NULL).

        Defensa en profundidad: desvinculación explícita en servicio además
        del ON DELETE SET NULL a nivel DDL. Jamás elimina tareas en cascada.
        """
        category = cls.get_category_by_id(
            user_id=user_id, category_id=category_id
        )

        unlinked = (
            Task.query.filter_by(category_id=category.id)
            .update({Task.category_id: None})
        )
        name = category.name
        db.session.delete(category)
        db.session.commit()

        AuditService.log_event(
            actor_id=user_id,
            action="CATEGORY_DELETED",
            entity_id=category_id,
            details={"name": name, "unlinked_tasks_count": unlinked},
        )
        db.session.commit()

        return {
            "deleted_category_id": category_id,
            "unlinked_tasks": unlinked,
        }
