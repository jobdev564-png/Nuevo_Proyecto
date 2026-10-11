from datetime import datetime, timezone, timedelta
import pytest
from src.taskcontrol.services.user_service import UserService
from src.taskcontrol.services.password_reset_service import (
    PasswordResetService,
    InvalidOrExpiredTokenError,
    ValidationError as ResetValidationError,
)
from src.taskcontrol.models.audit import AuditLog
from src.taskcontrol.models.password_reset_token import PasswordResetToken


@pytest.fixture
def user_email(app):
    with app.app_context():
        UserService.register_user("resetuser@example.com", "Password123!")
        return "resetuser@example.com"


def _request(app, email):
    with app.app_context():
        return PasswordResetService.request_reset(email)


def test_request_existing_email_returns_neutral_and_token(app, user_email):
    """Correo existente → mensaje neutro + token vivo de 60 min (FR-011/FR-012/FR-013)."""
    with app.app_context():
        result = PasswordResetService.request_reset(user_email)
        assert result["message"] == PasswordResetService.NEUTRAL_MESSAGE
        assert result["token"] is not None

        from src.taskcontrol.models.user import User
        user = User.query.filter_by(email=user_email).first()
        token_row = PasswordResetToken.query.filter_by(user_id=user.id).all()
        assert len(token_row) == 1
        assert token_row[0].used_at is None
        delta = token_row[0].expires_at - token_row[0].created_at
        assert timedelta(minutes=59) <= delta <= timedelta(minutes=61)

        audit = AuditLog.query.filter_by(
            action="PASSWORD_RESET_REQUESTED", entity_id=user.id
        ).first()
        assert audit is not None
        assert "token" not in (audit.details or "").lower()


def test_request_unknown_email_identical_neutral_no_token(app):
    """Correo inexistente → mismo mensaje, sin token ni PII (FR-012/SC-004)."""
    with app.app_context():
        result = PasswordResetService.request_reset("nadie@example.com")
        assert result["message"] == PasswordResetService.NEUTRAL_MESSAGE
        assert result.get("token") is None
        assert PasswordResetToken.query.count() == 0


def test_confirm_valid_token_rotates_password_and_invalidates(app, user_email):
    """Token válido → nueva contraseña funciona, token invalidado, auditoría limpia (FR-015/FR-016/FR-020)."""
    with app.app_context():
        token = _request(app, user_email)["token"]
        email = PasswordResetService.confirm_reset(token, "NuevaClave123!")

        assert email == user_email
        assert UserService.authenticate_user(user_email, "NuevaClave123!") is not None
        assert UserService.authenticate_user(user_email, "Password123!") is None

        from src.taskcontrol.models.user import User
        user = User.query.filter_by(email=user_email).first()
        assert "NuevaClave" not in user.password_hash
        audit = AuditLog.query.filter_by(
            action="PASSWORD_RESET_COMPLETED", entity_id=user.id
        ).first()
        assert audit is not None
        assert "NuevaClave" not in (audit.details or "")
        assert "token" not in (audit.details or "").lower()


def test_reuse_token_rejected(app, user_email):
    """Reutilización → INVALID_OR_EXPIRED_TOKEN (FR-016/FR-017/SC-005)."""
    with app.app_context():
        token = _request(app, user_email)["token"]
        PasswordResetService.confirm_reset(token, "NuevaClave123!")
        with pytest.raises(InvalidOrExpiredTokenError):
            PasswordResetService.confirm_reset(token, "OtraClave123!")


def test_expired_token_rejected(app, user_email):
    """Token >60 min → rechazo (FR-017/SC-005)."""
    with app.app_context():
        token = _request(app, user_email)["token"]
        row = PasswordResetToken.query.filter_by(used_at=None).first()
        row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        from src.taskcontrol.extensions import db
        db.session.commit()

        with pytest.raises(InvalidOrExpiredTokenError):
            PasswordResetService.confirm_reset(token, "NuevaClave123!")


def test_new_request_invalidates_previous_tokens(app, user_email):
    """Rotación: nuevo token invalida previos vivos (FR-014)."""
    with app.app_context():
        first = _request(app, user_email)["token"]
        second = _request(app, user_email)["token"]
        assert first != second

        with pytest.raises(InvalidOrExpiredTokenError):
            PasswordResetService.confirm_reset(first, "NuevaClave123!")
        assert PasswordResetService.confirm_reset(second, "NuevaClave123!") == user_email


def test_weak_password_rejected_with_registration_rule(app, user_email):
    """Clave <8 → VALIDATION_ERROR idéntica a registro (FR-018)."""
    with app.app_context():
        token = _request(app, user_email)["token"]
        with pytest.raises(ResetValidationError):
            PasswordResetService.confirm_reset(token, "corta")


def test_malformed_token_rejected_safely(app):
    """Tokens manipulados/vacíos → rechazo seguro sin 500 (Edge Cases/FR-017)."""
    with app.app_context():
        for bad in ("", "   ", "no-es-un-token!!!", "a" * 8):
            with pytest.raises(InvalidOrExpiredTokenError):
                PasswordResetService.confirm_reset(bad, "NuevaClave123!")
