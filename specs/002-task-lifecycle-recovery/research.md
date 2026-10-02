# Research & Decisions: 002-task-lifecycle-recovery

**Feature**: 002-task-lifecycle-recovery (HU-05, HU-06, HU-14)
**Date**: 2026-10-02
**Status**: Completed
**Base**: Extiende `specs/001-basic-tasks-auth/` (modelos `User`, `Task`, `AuditLog`; blueprints `auth_bp`, `tasks_bp`; servicios `UserService`, `TaskService`, `AuditService`).

---

## R-01. Soft delete sobre `Task` sin romper Incremento 1

### Decision
Extender `Task` con dos columnas aditivas y anulables por defecto seguro:
- `is_deleted: Boolean, NOT NULL, DEFAULT FALSE, INDEX`
- `deleted_at: DateTime(timezone UTC), NULLABLE`

Toda lectura existente (`get_user_tasks`, `get_task_by_id`) se endurece con filtro `is_deleted == False`. Ninguna consulta expone un flag `include_deleted` a usuarios estándar; el borrado físico queda prohibido a nivel de servicio (no se expone `db.session.delete(task)` en ningún camino).

### Rationale
- El spec exige preservar registro + historial (FR-002, FR-004) y que HU-02 excluya eliminadas por defecto (FR-003).
- Booleano + timestamp cubre los dos usos: filtrado barato indexado (`is_deleted`) y auditoría forense (`deleted_at` = cuándo).
- Alternativa `status='deleted'` rechazada: contaminaría la máquina de estados (`pending/in_progress/completed`) y rompería filtros por estado del Incremento 1.

### Alternatives considered
- Columna única `deleted_at NULL = viva`: válida pero obliga a filtrar por `IS NULL` (menos expresivo en SQLite y sin índice booleano directo). Se descarta por legibilidad; se mantienen ambas columnas sincronizadas en servicio (`is_deleted=True` ⇔ `deleted_at=now_utc`).
- Tabla `Trash` separada: rechazada por Principio V (YAGNI) y porque rompería FKs e historial.

---

## R-02. Reapertura `completed → pending` distinguible de `STATUS_CHANGED`

### Decision
- Nueva transición única habilitada: `completed → pending` **solo** vía método dedicado `TaskService.reopen_task()`, no vía `update_task_status()`.
- `update_task_status()` mantiene `completed → *` bloqueado (`INVALID_STATE_TRANSITION`), preservando contrato del Incremento 1.
- `reopen_task()` valida: tarea viva (`is_deleted=False`), `status == 'completed'`, propiedad (`task.user_id == actor`), y emite `AuditLog(action='TASK_REOPENED', details={previous_status:'completed', current_status:'pending'})`.
- Concurrencia: transacción única + re-chequeo de estado dentro de la misma sesión; la segunda petición concurrente ve `pending` y recibe `INVALID_STATE_TRANSITION` (idempotencia segura, sin doble `TASK_REOPENED`).

### Rationale
- El spec (FR-008/FR-009) exige retorno al estado activo inicial `pending` y evento unívoco `TASK_REOPENED` distinto de `TASK_CREATED` y `STATUS_CHANGED` (Principio VIII).
- Un endpoint/método separado evita ambigüedad cliente-servidor (Principio III) y permite mensaje de error específico ("solo completadas son reabribles").

### Alternatives considered
- Reutilizar `POST /tasks/<id>/status` con `status=pending`: rechazado porque haría indistinguible una reapertura de una pausa (`in_progress → pending`) en logs y contratos, violando FR-009.
- Reapertura a `in_progress`: rechazada; el spec fija `pending` como estado destino.

---

## R-03. Tokens de restablecimiento: modelo, vida útil, anti-enumeración

### Decision
Nueva entidad `PasswordResetToken`:
- `id PK`, `user_id FK(users.id) NOT NULL INDEX`, `token_hash String(255) NOT NULL UNIQUE`, `expires_at DateTime UTC NOT NULL`, `used_at DateTime UTC NULLABLE`, `created_at DateTime UTC NOT NULL DEFAULT now`.
- Token en claro: `secrets.token_urlsafe(32)` (~256 bits). **Solo se persiste `SHA-256(token)`** (Werkzeug no es apto para comparar tokens de alta entropía de forma eficiente; SHA-256 + UNIQUE es estándar para lookup). El claro solo viaja en el enlace de correo / log de consola en desarrollo, nunca en BD ni en `AuditLog`.
- Vida útil: `expires_at = created_at + 60 minutos` (asunción del spec).
- Un solo uso: `used_at` se marca en la misma transacción que actualiza `password_hash`; toda reutilización → `410 Gone` / `400 INVALID_OR_EXPIRED_TOKEN`.
- Rotación: al generar un token nuevo se invalidan los previos vivos del mismo usuario (`expires_at = now` o borrado lógico vía `used_at = now` + marca `superseded`; implementación elegida: invalidar por `used_at = now` con `details` de rotación, o intervalo expirado — documentar en servicio).
- Anti-enumeración: `POST /auth/password-reset-request` retorna siempre `200` + mensaje neutro idéntico exista o no el correo; no se mide tiempo diferencial (sin `time.sleep` artificial — se evita timing-oracle por rama corta: ambas ramas ejecutan `AuditService` y misma serialización; solo la rama existente genera token + correo). Nunca se audita el email inexistente con PII; solo `PASSWORD_RESET_REQUESTED` para correos existentes con `entity_id=user.id` y `details` sin secretos.

### Rationale
- Cumple FR-012–FR-017 + Principio VII (sin texto plano, sin fuga de existencia, hash + expiración estricta).
- SHA-256 del token (no bcrypt/scrypt) porque el token ya tiene 256 bits de entropía y se necesita búsqueda por igualdad indexada; bcrypt rompería la unicidad y sería lento para lookup.

### Alternatives considered
- JWT autofirmado sin persistencia (stateless): rechazado — impide invalidación tras uso y rotación (FR-014/FR-016) sin lista de revocación, que equivale a persistir de todos modos.
- Guardar token en claro en BD: prohibido por SC-006 / Principio VII.
- ItsDangerous `URLSafeTimedSerializer`: viable pero acopla secreto de firma con expiración embebida no revocable; se rechaza frente a tabla + `secrets` por control explícito de un solo uso.

---

## R-04. Envío de correo en desarrollo: simulación por log/consola

### Decision
**Simulación por log/consola en desarrollo** (sin servicio SMTP real):
- `PasswordResetService` emite el enlace `http://127.0.0.1:5000/auth/password-reset-confirm?token=<claro>` vía `logging` (`logger.info`) y, opcionalmente, imprime en `stdout` en `FLASK_ENV=development`.
- En `testing`, el servicio expone hook `get_last_token_for_email()` solo bajo fixture (nunca en producción) para que las pruebas recuperen el token sin leer correo real.
- Config futura (`MAIL_SERVER`, `MAIL_*` en `.env`) queda reservada pero **no implementada** en este incremento (YAGNI).

### Rationale
- Alcance académico: evita credenciales SMTP, costes, spam y configuración frágil; cumple la asunción del spec ("puede ser simulada o registrada en consola").
- Mantiene Principio VII: el token en claro solo aparece en log local de desarrollo, nunca en `AuditLog` persistente ni en repositorio.
- Alternativa SMTP real (Flask-Mail / smtplib + Mailtrap): rechazada por Principio V — sobredimensiona un MVP sin requisito de envío externo.

---

## R-05. Migraciones aditivas sin romper datos del Incremento 1 (Principio VI)

### Decision
- Migración única Alembic `add_soft_delete_and_reset_tokens` con operaciones **aditivas y reversibles**:
  1. `ALTER TABLE tasks ADD COLUMN is_deleted BOOLEAN NOT NULL SERVER_DEFAULT '0'` + `ADD COLUMN deleted_at DATETIME NULL` + `CREATE INDEX ix_tasks_is_deleted`.
  2. Backfill implícito: `SERVER_DEFAULT` pone `False` a filas existentes sin `UPDATE` manual.
  3. `CREATE TABLE password_reset_tokens (...)` con FK `user_id → users.id ON DELETE CASCADE`, índices en `user_id` y `token_hash UNIQUE`.
- Prohibido `db.create_all()` en producción; flujo `flask db migrate -m ... && flask db upgrade`. Downgrade elimina tabla + columnas.

### Rationale
- Garantiza reproducibilidad entre dev/test/prod (Principio VI) y cero pérdida de tareas/auditoría del Incremento 1.

---

## R-06. Estrategia de pruebas bloqueantes (Principio IV)

### Decision
- Capa `tests/services/` **bloqueante** (Red-Green-Refactor antes de servicios):
  - `test_task_soft_delete.py`: eliminada no aparece en `get_user_tasks`; doble eliminación → error; edición/cambio-estado/reapertura sobre eliminada → error; `TASK_DELETED` con 4 campos.
  - `test_task_reopen.py`: `completed → pending` vía `reopen_task` + `TASK_REOPENED`; `pending/in_progress` → `reopen` rechazado; eliminada → rechazado; `update_task_status(completed→pending)` sigue bloqueado.
  - `test_password_reset_service.py`: respuesta idéntica para correo existente/inexistente; token válido rota contraseña + invalida; reutilización → rechazo; expirado (>60min) → rechazo; nuevo token invalida previos; validación de contraseña idéntica a registro (≥8).
- `tests/functional/` (contratos HTTP): códigos de cada endpoint (ver contratos).

### Rationale
- Cubre SC-001–SC-007 y el punto 7 del encargo con pruebas ejecutables como especificación viva.
