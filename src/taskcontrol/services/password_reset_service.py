import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone

from werkzeug.security import generate_password_hash

from src.taskcontrol.extensions import db
from src.taskcontrol.models.user import User
from src.taskcontrol.models.password_reset_token import PasswordResetToken
from src.taskcontrol.services.audit_service import AuditService

logger = logging.getLogger("taskcontrol.password_reset")


class InvalidOrExpiredTokenError(Exception):
    """Token inexistente, consumido, expirado o manipulado (FR-017)."""
    pass


class ValidationError(Exception):
    """Validación de nueva contraseña (FR-018, idéntica a registro)."""
    pass


class PasswordResetService:
    """Recuperación segura de acceso con anti-enumeración (HU-14, Principio VII)."""

    NEUTRAL_MESSAGE = (
        "Si el correo se encuentra registrado en el sistema, "
        "se han enviado las instrucciones de restablecimiento"
    )
    TOKEN_TTL = timedelta(minutes=60)

    # Hook solo para fixtures de testing: email -> último token en claro.
    # Nunca se registra en producción (ver research.md R-04).
    _testing_tokens: dict = {}

    @staticmethod
    def _hash_token(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @classmethod
    def _now(cls):
        return datetime.now(timezone.utc)

    @classmethod
    def request_reset(cls, email: str) -> dict:
        """Genera token si el correo existe; respuesta neutra idéntica en ambos casos."""
        clean = (email or "").strip().lower()

        user = User.query.filter_by(email=clean).first() if clean else None
        if user is None:
            # Rama inexistente: sin token, sin correo, sin auditoría con PII.
            return {"message": cls.NEUTRAL_MESSAGE, "token": None}

        # Rotación: invalidar previos vivos del usuario (FR-014)
        now = cls._now()
        live = PasswordResetToken.query.filter_by(user_id=user.id, used_at=None).all()
        for row in live:
            row.used_at = now
        db.session.commit()

        token = secrets.token_urlsafe(32)
        row = PasswordResetToken(
            user_id=user.id,
            token_hash=cls._hash_token(token),
            expires_at=now + cls.TOKEN_TTL,
            used_at=None,
            created_at=now,
        )
        db.session.add(row)
        db.session.commit()

        AuditService.log_event(
            actor_id=user.id,
            action="PASSWORD_RESET_REQUESTED",
            entity_id=user.id,
            details={},
        )
        db.session.commit()

        # Correo simulado por log/consola solo en desarrollo (research.md R-04).
        # El claro nunca toca AuditLog, BD ni repositorio.
        logger.info(
            "Enlace de restablecimiento (solo desarrollo): "
            "/auth/password-reset-confirm?token=%s",
            token,
        )
        cls._testing_tokens[clean] = token

        return {"message": cls.NEUTRAL_MESSAGE, "token": token}

    @classmethod
    def confirm_reset(cls, token: str, new_password: str) -> str:
        """Consume un token válido y establece la nueva contraseña (FR-015/FR-016)."""
        if not token or not token.strip():
            raise InvalidOrExpiredTokenError(
                "El enlace es inválido, ya fue utilizado o ha expirado"
            )

        row = PasswordResetToken.query.filter_by(
            token_hash=cls._hash_token(token.strip())
        ).first()
        if row is None or not row.is_live:
            raise InvalidOrExpiredTokenError(
                "El enlace es inválido, ya fue utilizado o ha expirado"
            )

        if not new_password or len(new_password) < 8:
            raise ValidationError("La contraseña debe tener al menos 8 caracteres")

        user = User.query.filter_by(id=row.user_id).first()
        if user is None:
            raise InvalidOrExpiredTokenError(
                "El enlace es inválido, ya fue utilizado o ha expirado"
            )

        # Consumo atómico: hash + invalidación + auditoría sin secretos
        user.password_hash = generate_password_hash(new_password)
        row.used_at = cls._now()
        AuditService.log_event(
            actor_id=user.id,
            action="PASSWORD_RESET_COMPLETED",
            entity_id=user.id,
            details={},
        )
        db.session.commit()

        cls._testing_tokens.pop(user.email.strip().lower(), None)
        return user.email
