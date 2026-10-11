import json
import logging
from datetime import datetime, timezone
from src.taskcontrol.extensions import db
from src.taskcontrol.models.audit import AuditLog

logger = logging.getLogger("taskcontrol.audit")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


class AuditService:
    """Servicio centralizado de auditoría y observabilidad estructurada.

    Vocabulario controlado de acciones (Principio VIII):
    - Incremento 1: TASK_CREATED, STATUS_CHANGED, TASK_UPDATED, TASK_ASSIGNED
    - 002-task-lifecycle-recovery (HU-05/HU-06/HU-14): TASK_DELETED,
      TASK_REOPENED, PASSWORD_RESET_REQUESTED, PASSWORD_RESET_COMPLETED
    Todo evento incluye actor_id/action/entity_id/timestamp UTC; details
    nunca contiene secretos (tokens, contraseñas) — ver SC-006.
    """

    @staticmethod
    def log_event(actor_id: int, action: str, entity_id: int, details: dict = None):
        """Registra una mutación en base de datos y emite log estructurado JSON."""
        now = datetime.now(timezone.utc)
        details_str = json.dumps(details) if details else None

        # 1. Persistencia relacional inmutable
        audit_entry = AuditLog(
            actor_id=actor_id,
            action=action,
            entity_id=entity_id,
            timestamp=now,
            details=details_str,
        )
        db.session.add(audit_entry)
        db.session.flush()

        # 2. Emisión a log estructurado JSON
        log_payload = {
            "timestamp": now.isoformat(),
            "actor_id": actor_id,
            "action": action,
            "entity_id": entity_id,
            "details": details or {},
        }
        logger.info(json.dumps(log_payload))

        return audit_entry
