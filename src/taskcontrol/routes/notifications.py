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
from src.taskcontrol.services.notification_service import (
    NotificationService,
    NotificationNotFoundError,
)

notifications_bp = Blueprint("notifications", __name__)


def _is_json_request():
    return (
        request.is_json
        or request.headers.get("Accept") == "application/json"
        or request.path.startswith("/api/")
    )


@notifications_bp.app_context_processor
def _inject_unread_count():
    """Contador de pendientes disponible en todas las plantillas (HU-11)."""
    user_id = session.get("user_id")
    if not user_id:
        return {"unread_count": 0}
    return {"unread_count": NotificationService.unread_count(
        user_id=user_id
    )}


@notifications_bp.route("", methods=["GET"])
@notifications_bp.route("/", methods=["GET"])
@login_required
def list_notifications():
    """Historial de notificaciones con contador de pendientes (HU-11)."""
    user_id = session["user_id"]
    unread_only = request.args.get("unread_only") == "1"
    items = NotificationService.list_detailed(
        user_id=user_id, unread_only=unread_only
    )
    count = NotificationService.unread_count(user_id=user_id)

    if _is_json_request():
        return (
            jsonify(
                {
                    "status": "success",
                    "data": {
                        "notifications": items,
                        "unread_count": count,
                        "count": len(items),
                    },
                }
            ),
            200,
        )

    return render_template(
        "notifications/index.html",
        notifications=items,
        unread_count=count,
    )


@notifications_bp.route("/read-all", methods=["POST"])
@login_required
def mark_all_read_route():
    """Marca todas las pendientes como leídas (HU-11)."""
    user_id = session["user_id"]
    marked = NotificationService.mark_all_read(user_id=user_id)

    if _is_json_request():
        return (
            jsonify(
                {
                    "status": "success",
                    "message": "Notificaciones marcadas como leídas",
                    "data": {"marked_count": marked},
                }
            ),
            200,
        )

    flash("Notificaciones marcadas como leídas.", "success")
    return redirect(url_for("notifications.list_notifications"))


@notifications_bp.route("/<int:notification_id>/read", methods=["POST"])
@login_required
def mark_read_route(notification_id: int):
    """Marca una notificación como leída, persiste en historial (HU-11)."""
    user_id = session["user_id"]

    try:
        note = NotificationService.mark_read(
            user_id=user_id, notification_id=notification_id
        )

        if _is_json_request():
            return (
                jsonify(
                    {
                        "status": "success",
                        "message": "Notificación marcada como leída",
                        "data": {
                            "id": note.id,
                            "is_read": True,
                            "read_at": note.read_at.isoformat()
                            if note.read_at
                            else None,
                        },
                    }
                ),
                200,
            )

        flash("Notificación marcada como leída.", "success")
        return redirect(url_for("notifications.list_notifications"))

    except NotificationNotFoundError:
        if _is_json_request():
            return (
                jsonify(
                    {
                        "status": "error",
                        "code": "NOTIFICATION_NOT_FOUND",
                        "message": "Notificación no encontrada",
                    }
                ),
                404,
            )
        flash("Notificación no encontrada.", "error")
        return redirect(url_for("notifications.list_notifications")), 404
