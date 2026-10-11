from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    jsonify,
)
from src.taskcontrol.routes.auth_helpers import login_required
from src.taskcontrol.services.category_service import (
    CategoryService,
    CategoryValidationError,
    CategoryNotFoundError,
    CategoryDuplicateError,
)

categories_bp = Blueprint("categories", __name__)


def _is_json_request():
    return (
        request.is_json
        or request.headers.get("Accept") == "application/json"
        or request.path.startswith("/api/")
    )


@categories_bp.route("/", methods=["GET"])
@login_required
def list_categories():
    """Listado de categorías propias del usuario (HU-08)."""
    user_id = session["user_id"]
    categories = CategoryService.get_user_categories(user_id=user_id)

    if _is_json_request():
        return (
            jsonify(
                {
                    "status": "success",
                    "data": [c.to_dict() for c in categories],
                }
            ),
            200,
        )

    return render_template("categories/index.html", categories=categories)


@categories_bp.route("/", methods=["POST"])
@login_required
def create_category_route():
    """Creación de categoría propia (HU-08)."""
    user_id = session["user_id"]
    data = request.get_json(silent=True) or request.form

    try:
        category = CategoryService.create_category(
            user_id=user_id,
            name=data.get("name", ""),
            description=data.get("description"),
        )

        if _is_json_request():
            return (
                jsonify(
                    {
                        "status": "success",
                        "message": "Categoría creada exitosamente.",
                        "data": category.to_dict(),
                    }
                ),
                201,
            )

        flash("Categoría creada exitosamente.", "success")
        return redirect(url_for("categories.list_categories"))

    except CategoryValidationError as e:
        if _is_json_request():
            return (
                jsonify(
                    {
                        "status": "error",
                        "code": "VALIDATION_ERROR",
                        "message": str(e),
                    }
                ),
                400,
            )
        flash(str(e), "error")
        return redirect(url_for("categories.list_categories")), 400

    except CategoryDuplicateError as e:
        if _is_json_request():
            return (
                jsonify(
                    {
                        "status": "error",
                        "code": "CATEGORY_DUPLICATE",
                        "message": str(e),
                    }
                ),
                409,
            )
        flash(str(e), "error")
        return redirect(url_for("categories.list_categories")), 409


@categories_bp.route("/<int:category_id>/delete", methods=["POST", "DELETE"])
@login_required
def delete_category_route(category_id: int):
    """Eliminación propia con desvinculación segura, nunca en cascada (HU-08)."""
    user_id = session["user_id"]

    try:
        result = CategoryService.delete_category(
            user_id=user_id, category_id=category_id
        )

        if _is_json_request():
            return (
                jsonify(
                    {
                        "status": "success",
                        "message": (
                            "Categoría eliminada exitosamente. "
                            "Las tareas asociadas fueron desvinculadas."
                        ),
                        "data": result,
                    }
                ),
                200,
            )

        flash(
            "Categoría eliminada. Las tareas asociadas ahora están sin categoría.",
            "success",
        )
        return redirect(url_for("categories.list_categories"))

    except CategoryNotFoundError as e:
        if _is_json_request():
            return (
                jsonify(
                    {
                        "status": "error",
                        "code": "CATEGORY_NOT_FOUND",
                        "message": "Categoría no encontrada.",
                    }
                ),
                404,
            )
        flash("Categoría no encontrada.", "error")
        return redirect(url_for("categories.list_categories")), 404
