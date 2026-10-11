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
from src.taskcontrol.services.user_service import (
    UserService,
    ValidationError,
    DuplicateEmailError,
)
from src.taskcontrol.services.password_reset_service import (
    PasswordResetService,
    InvalidOrExpiredTokenError,
    ValidationError as ResetValidationError,
)

auth_bp = Blueprint("auth", __name__)


def _wants_json():
    return (
        request.is_json
        or request.headers.get("Accept") == "application/json"
        or request.path.startswith("/api/")
    )


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    """Registro de usuario (HU-12)."""
    if request.method == "GET":
        if "user_id" in session:
            return redirect(url_for("tasks.list_tasks"))
        return render_template("auth/register.html")

    data = request.get_json(silent=True) or request.form
    email = data.get("email", "")
    password = data.get("password", "")

    wants_json = (
        request.is_json
        or request.headers.get("Accept") == "application/json"
        or request.path.startswith("/api/")
    )

    try:
        user = UserService.register_user(email=email, password=password)
        if wants_json:
            return (
                jsonify(
                    {
                        "status": "success",
                        "message": "Usuario registrado exitosamente",
                        "data": user.to_dict(),
                    }
                ),
                201,
            )

        flash("Registro exitoso. Por favor inicia sesión.", "success")
        return redirect(url_for("auth.login"))

    except ValidationError as e:
        if wants_json:
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
        return render_template("auth/register.html", email=email), 400

    except DuplicateEmailError as e:
        if wants_json:
            return (
                jsonify(
                    {
                        "status": "error",
                        "code": "EMAIL_ALREADY_EXISTS",
                        "message": str(e),
                    }
                ),
                409,
            )
        flash(str(e), "error")
        return render_template("auth/register.html", email=email), 409


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Inicio de sesión (HU-13)."""
    if request.method == "GET":
        if "user_id" in session:
            return redirect(url_for("tasks.list_tasks"))
        return render_template("auth/login.html")

    data = request.get_json(silent=True) or request.form
    email = data.get("email", "")
    password = data.get("password", "")

    wants_json = (
        request.is_json
        or request.headers.get("Accept") == "application/json"
        or request.path.startswith("/api/")
    )

    user = UserService.authenticate_user(email=email, password=password)
    if not user:
        if wants_json:
            return (
                jsonify(
                    {
                        "status": "error",
                        "code": "INVALID_CREDENTIALS",
                        "message": "Correo o contraseña incorrectos",
                    }
                ),
                401,
            )
        flash("Correo o contraseña incorrectos", "error")
        return render_template("auth/login.html", email=email), 401

    # Establecer sesión segura en el backend (Principio VII)
    session["user_id"] = user.id
    session["user_email"] = user.email

    if wants_json:
        return (
            jsonify(
                {
                    "status": "success",
                    "message": "Inicio de sesión exitoso",
                    "data": user.to_dict(),
                }
            ),
            200,
        )

    flash("Bienvenido de nuevo.", "success")
    return redirect(url_for("tasks.list_tasks"))


@auth_bp.route("/logout", methods=["POST"])
def logout():
    """Cierre de sesión (HU-13)."""
    session.clear()

    wants_json = (
        request.is_json
        or request.headers.get("Accept") == "application/json"
        or request.path.startswith("/api/")
    )

    if wants_json:
        return (
            jsonify(
                {
                    "status": "success",
                    "message": "Sesión finalizada exitosamente",
                }
            ),
            200,
        )

    flash("Has cerrado sesión.", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/password-reset-request", methods=["GET", "POST"])
def password_reset_request():
    """Solicitud pública de restablecimiento (HU-14, FR-011/FR-012)."""
    if request.method == "GET":
        return render_template("auth/password_reset_request.html")

    data = request.get_json(silent=True) or request.form

    if "email" not in data or data.get("email") is None:
        if _wants_json():
            return (
                jsonify(
                    {
                        "status": "error",
                        "code": "VALIDATION_ERROR",
                        "message": "El correo electrónico es obligatorio",
                    }
                ),
                400,
            )
        flash("El correo electrónico es obligatorio.", "error")
        return render_template("auth/password_reset_request.html"), 400

    result = PasswordResetService.request_reset(data.get("email", ""))

    if _wants_json():
        return jsonify({"status": "success", "message": result["message"]}), 200

    flash(result["message"], "success")
    return render_template("auth/password_reset_request.html")


@auth_bp.route("/password-reset-confirm", methods=["GET", "POST"])
def password_reset_confirm():
    """Confirmación pública con token de un solo uso (HU-14, FR-015/FR-017)."""
    if request.method == "GET":
        return render_template(
            "auth/password_reset_confirm.html",
            token=request.args.get("token", ""),
        )

    data = request.get_json(silent=True) or request.form
    token = data.get("token", "")
    new_password = data.get("new_password") or data.get("password", "")

    try:
        email = PasswordResetService.confirm_reset(token, new_password)
    except ResetValidationError as e:
        if _wants_json():
            return (
                jsonify(
                    {"status": "error", "code": "VALIDATION_ERROR", "message": str(e)}
                ),
                400,
            )
        flash(str(e), "error")
        return render_template("auth/password_reset_confirm.html", token=token), 400
    except InvalidOrExpiredTokenError as e:
        if _wants_json():
            return (
                jsonify(
                    {
                        "status": "error",
                        "code": "INVALID_OR_EXPIRED_TOKEN",
                        "message": str(e),
                    }
                ),
                400,
            )
        flash(str(e), "error")
        return render_template("auth/password_reset_confirm.html", token=token), 400

    # Invalidación de sesiones previas tras restablecimiento (Edge Case).
    session.clear()

    if _wants_json():
        return (
            jsonify(
                {
                    "status": "success",
                    "message": "Contraseña restablecida correctamente. "
                    "Inicia sesión con tu nueva contraseña",
                    "data": {"email": email},
                }
            ),
            200,
        )

    flash("Contraseña restablecida correctamente. Inicia sesión.", "success")
    return redirect(url_for("auth.login"))
