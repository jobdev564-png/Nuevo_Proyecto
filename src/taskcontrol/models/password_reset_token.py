from datetime import datetime, timezone
from src.taskcontrol.extensions import db


class PasswordResetToken(db.Model):
    """Credencial temporal de un solo uso para recuperación de acceso (HU-14).

    Solo se persiste el hash SHA-256 del token; el claro jamás toca la BD.
    """

    __tablename__ = "password_reset_tokens"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash = db.Column(db.String(255), nullable=False, unique=True, index=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    used_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    user = db.relationship(
        "User", backref=db.backref("reset_tokens", cascade="all, delete-orphan", lazy=True)
    )

    @property
    def is_live(self) -> bool:
        def _naive(dt):
            return dt.replace(tzinfo=None) if dt is not None and dt.tzinfo is not None else dt

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        return (
            self.used_at is None
            and self.expires_at is not None
            and _naive(self.expires_at) > now
        )
