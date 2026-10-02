# Implementation Plan: 002-task-lifecycle-recovery

**Branch**: `002-task-lifecycle-recovery` | **Date**: 2026-10-02 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-task-lifecycle-recovery/spec.md` (HU-05, HU-06, HU-14; base: Incremento 1 `001-basic-tasks-auth` en producción).

---

## Summary

Cierre de la gestión básica de tareas y recuperación de acceso sobre el monolito TaskControl sin romper el Incremento 1: (1) soft delete de `Task` con `is_deleted + deleted_at`, filtrado por defecto en HU-02; (2) reapertura dedicada `completed → pending` con evento `TASK_REOPENED` distinguible de `STATUS_CHANGED`; (3) recuperación de contraseña con tokens `SHA-256`, 60 min, un solo uso, rotación e invalidación, respuesta neutral anti-enumeración y correo simulado por log en desarrollo. Todo cambio de esquema vía migración Alembic aditiva; toda regla de dominio con pruebas bloqueantes Red-Green-Refactor.

Decisiones y alternativas en [`research.md`](./research.md). Esquema y máquina de estados en [`data-model.md`](./data-model.md). Contratos en [`contracts/`](./contracts/task-lifecycle-contracts.md). Validación E2E en [`quickstart.md`](./quickstart.md).

---

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: Flask 3.x, Flask-SQLAlchemy (SQLAlchemy 2.x), Flask-Migrate (Alembic), Werkzeug (hash scrypt/pbkdf2), stdlib `secrets` + `hashlib.sha256` para tokens
**Storage**: Relacional existente (SQLite dev/test, PostgreSQL-compatible); tabla nueva `password_reset_tokens`; 2 columnas nuevas en `tasks`
**Testing**: pytest + pytest-flask; suites bloqueantes `tests/services/` (Principio IV) + `tests/functional/` para contratos
**Target Platform**: Monolito único (`flask run` / `run.ps1`), Windows/Linux/macOS server
**Project Type**: Monolito web (Jinja2 SSR + JS vanilla Fetch)
**Performance Goals**: Listado <100 ms local con índice `is_deleted`; lookup de token por `UNIQUE(token_hash)` O(log n); reset-request con tiempo homogéneo exista o no el correo
**Constraints**: Cero microservicios/colas (PI); 4 capas sin saltos blueprint→ORM (PII); contratos previos (PIII); TDD bloqueante servicios (PIV); solo migraciones versionadas (PVI); validación backend + hash + sin secretos en repo (PVII); auditoría `actor_id/action/entity_id/timestamp` por mutación (PVIII)
**Scale/Scope**: 3 HU (HU-05 P1, HU-06 P2, HU-14 P1); 4 endpoints nuevos; 1 entidad nueva; 0 cambios a contratos del Incremento 1

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio | Estado | Mecanismo de cumplimiento en este incremento |
|---|---|---|
| **I. Monolito por diseño** | PASS | Un proceso Flask, una BD relacional. Sin colas/SMTP externo: correo simulado por `logging`. |
| **II. Separación en 4 capas** | PASS | `models/` (Task extendido, PasswordResetToken) ← `services/` (`TaskService.delete/reopen`, `PasswordResetService`) ← `routes/` (`tasks.py`, `auth.py`) ← `templates/static`. Blueprints sin ORM directo. |
| **III. Contrato explícito** | PASS | `contracts/task-lifecycle-contracts.md` (delete, reopen) + `contracts/password-recovery-contracts.md` (request, confirm): ruta, método, payloads in/out y códigos por endpoint, definidos antes de codificar. |
| **IV. Test-first bloqueante** | PASS | Suites `test_task_soft_delete`, `test_task_reopen`, `test_password_reset_service` en Red-Green-Refactor; HU no cerrada sin suite en verde (ver §7). |
| **V. Simplicidad (YAGNI)** | PASS | Sin papelera/restauración, sin JWT, sin Flask-Mail/SMTP, sin `include_deleted` para usuarios; solo lo exigido por FR-001–FR-021. |
| **VI. Integridad y migraciones** | PASS | Migración única aditiva/reversible vía `flask db migrate/upgrade`; `SERVER_DEFAULT` para backfill; prohibido `db.create_all()` y DDL manual (ver §6). |
| **VII. Seguridad por defecto** | PASS | Sesión verificada por endpoint; aislamiento `user_id`; hash de passwords (Werkzeug) y de tokens (SHA-256); respuesta neutral anti-enumeración; validación password idéntica a registro; secretos solo en `.env`; invalidación de sesión tras reset. |
| **VIII. Observabilidad mínima** | PASS | `TASK_DELETED`, `TASK_REOPENED`, `PASSWORD_RESET_REQUESTED/COMPLETED` con los 4 campos + `details` sin secretos, vía `AuditService` centralizado. |

Post-diseño (Fase 1): sin violaciones; no se requiere tabla de complejidad.

---

## 1. Soft delete sobre el modelo `Task` existente (HU-05)

Extensión aditiva (detalle en `data-model.md` §2.1, decisión en `research.md` R-01):
- Nuevas columnas: `is_deleted Boolean NOT NULL DEFAULT FALSE INDEX` + `deleted_at DateTime UTC NULLABLE`. Filas del Incremento 1 quedan `False/NULL` por `SERVER_DEFAULT`, sin migración de datos manual.
- `create_task()` inicializa `is_deleted=False`; ningún camino ejecuta borrado físico (`db.session.delete(task)` prohibido).
- `get_user_tasks()` (HU-02) añade `WHERE is_deleted=FALSE` antes del filtro de `status` — **firma y contrato HTTP intactos**, el listado excluye eliminadas por defecto y los conteos no las incluyen.
- `get_task_by_id()` filtra vivas; cualquier `edit`/`status`/`reopen`/lectura directa sobre eliminada → `404` (`TASK_NOT_FOUND` / `TASK_ALREADY_DELETED` en segunda eliminación, `TASK_DELETED` admisible según ruta).
- `delete_task()` es idempotente-segura: segunda eliminación → error controlado sin nueva auditoría ni mutación. Autorización por propiedad → `403/404` sin filtrar datos ajenos.

## 2. Reapertura vs. cambio ordinario + auditoría (HU-06)

Transición habilitada: **`completed → pending` únicamente vía `TaskService.reopen_task()` + `POST /tasks/<id>/reopen`** (decisión `research.md` R-02, esquema `data-model.md` §2.2):
- `update_task_status()` **no cambia**: `completed → *` sigue vacío y devuelve `400 INVALID_STATE_TRANSITION` (contrato del Incremento 1 preservado).
- `reopen_task()` exige viva + `status=='completed'` + propiedad; muta a `pending` y emite **`TASK_REOPENED`** (`details={previous_status:'completed', current_status:'pending'}`), distinguible de `TASK_CREATED` y de `STATUS_CHANGED` (cambios HU-03, nunca desde `completed`). Reapertura sobre `pending/in_progress`/eliminada → `400/404`; ajena → `403/404`. Concurrencia: la segunda petición ve `pending` y recibe `400` sin duplicar el evento.

## 3. Contratos de nuevos endpoints (Principio III)

Definición completa (payloads y códigos) en `contracts/`; resumen:

| Endpoint | Método/Ruta | In → Out | Errores |
|---|---|---|---|
| Eliminar tarea (HU-05) | `POST /tasks/<id>/delete` (canónico; alias opcional `DELETE /tasks/<id>`) auth obligatoria | in: vacío → out `200 {id, is_deleted:true, deleted_at}` / HTML `302→/tasks` | `401` sin sesión; `404 TASK_NOT_FOUND` (inexistente/ajena/eliminada-lectura); `404 TASK_ALREADY_DELETED` (doble eliminación) |
| Reabrir tarea (HU-06) | `POST /tasks/<id>/reopen` auth obligatoria | in: vacío → out `200 {id, previous_status:completed, current_status:pending}` / HTML `302` | `401`; `404 TASK_NOT_FOUND`; `400 INVALID_STATE_TRANSITION` (no completada) |
| Solicitar reset (HU-14) | `POST /auth/password-reset-request` pública, `{email}` | out siempre `200 {message neutro}` idéntico exista o no | `400 VALIDATION_ERROR` solo si falta `email`; nunca `404/409` |
| Confirmar reset (HU-14) | `POST /auth/password-reset-confirm` pública, `{token, new_password}` | out `200 {email}` + sesión rotada | `400 INVALID_OR_EXPIRED_TOKEN` (inexistente/usado/expirado/manipulado); `400 VALIDATION_ERROR` (clave <8) |

`GET /tasks` (HU-02) no cambia de contrato: solo añade exclusión de eliminadas.

## 4. Tokens de restablecimiento: datos, expiración y anti-enumeración (HU-14)

Modelo `PasswordResetToken` (`data-model.md` §2.3; `research.md` R-03): `user_id FK CASCADE`, `token_hash=SHA256(token_urlsafe(32)) UNIQUE INDEX`, `expires_at=created_at+60min`, `used_at NULL=vivo`, `created_at`.
- **Vida útil**: 60 min estrictos (`expires_at <= now` → rechazo).
- **Un solo uso**: consumo atómico `password_hash:=hash(nueva) + used_at:=now + PASSWORD_RESET_COMPLETED`; reutilización → `INVALID_OR_EXPIRED_TOKEN`.
- **Rotación**: nuevo token invalida previos vivos del usuario.
- **Anti-enumeración**: misma respuesta `200` + mensaje neutro y forma idéntica para correo registrado/no registrado; sin token ni correo en esa rama; `PASSWORD_RESET_REQUESTED` solo para existentes con `details` vacío; validación de fortaleza idéntica a registro; hash seguro, cero texto plano en BD o `AuditLog` (SC-006).

## 5. Envío del correo en desarrollo

**Simulación por log/consola, sin servicio real** (`research.md` R-04): `PasswordResetService` registra el enlace `.../password-reset-confirm?token=<claro>` vía `logging`/`stdout` solo en `development`; hook de fixture solo en `testing` para recuperar el token. Justificación: alcance académico (cero credenciales SMTP, coste y spam), YAGNI (Principio V), y asunción explícita del spec; el claro nunca toca `AuditLog`/BD/repo. Variables `MAIL_*` quedan reservadas sin implementar.

## 6. Migraciones sobre el esquema existente (Principio VI)

Migración única `add_soft_delete_and_reset_tokens` (`research.md` R-05): `ADD COLUMN is_deleted SERVER_DEFAULT '0'` + índice, `ADD COLUMN deleted_at NULL`, `CREATE TABLE password_reset_tokens` (FK + índices + UNIQUE), con `downgrade()` inverso. Flujo: `flask db migrate -m "add_soft_delete_and_reset_tokens" && flask db upgrade`. Sin `UPDATE` manual (backfill por default del motor), sin pérdida de tareas/auditoría del Incremento 1, reproducible dev/test/prod. Prohibido `db.create_all()` y DDL manual.

## 7. Pruebas bloqueantes modelo/servicio (Principio IV)

Gate de integración: suites en `research.md` R-06 y escenarios en `quickstart.md` deben estar en verde. Bloqueantes exigidos por el encargo:
- Eliminada **no aparece** en `get_user_tasks` (ni en conteos/filtros por estado).
- **Doble eliminación** rechazada (`TASK_ALREADY_DELETED`, sin segunda auditoría ni mutación).
- Token **usado o expirado rechazado** (`INVALID_OR_EXPIRED_TOKEN`; expiración >60 min verificada con `expires_at` manipulado por fixture).
- Cobertura adyacente obligatoria: edición/estado/reapertura sobre eliminada bloqueadas; `reopen` solo desde `completed` con `TASK_REOPENED`; `update_task_status(completed→pending)` sigue `400`; respuesta neutral ante correo inexistente; rotación invalida previos; validación de clave = registro; propiedad cruzada `403/404`.

---

## Project Structure

### Documentation (this feature)

```text
specs/002-task-lifecycle-recovery/
├── spec.md                          # Especificación funcional (HU-05, HU-06, HU-14)
├── plan.md                          # Este plan técnico
├── research.md                      # Fase 0: decisiones R-01..R-06
├── data-model.md                    # Fase 1: delta Task + PasswordResetToken + máquina de estados
├── quickstart.md                    # Fase 1: validación E2E y suites
├── contracts/                       # Fase 1: contratos explícitos (Principio III)
│   ├── task-lifecycle-contracts.md  # POST /tasks/<id>/delete, POST /tasks/<id>/reopen
│   └── password-recovery-contracts.md # POST /auth/password-reset-request|confirm
├── checklists/
└── tasks.md                         # Fase 2 (comando /speckit-tasks, NO generado aquí)
```

### Source Code (repository root — delta sobre Incremento 1)

```text
src/taskcontrol/
├── models/
│   ├── task.py                      # + is_deleted, deleted_at
│   ├── password_reset_token.py      # NUEVO modelo PasswordResetToken
│   └── __init__.py                  # exportar nuevo modelo
├── services/
│   ├── task_service.py              # + delete_task, reopen_task; endurecer get/list/update
│   ├── password_reset_service.py    # NUEVO: request_reset + confirm_reset + correo simulado
│   └── audit_service.py             # sin cambios (nuevas actions por convención)
├── routes/
│   ├── tasks.py                     # + POST /<id>/delete, POST /<id>/reopen (+ alias DELETE)
│   └── auth.py                      # + POST /password-reset-request, POST /password-reset-confirm
└── templates/ static/               # botones "Eliminar"/"Reabrir" + formularios reset (JS vanilla)

tests/
├── services/                        # BLOQUEANTES (PIV)
│   ├── test_task_soft_delete.py
│   ├── test_task_reopen.py
│   └── test_password_reset_service.py
└── functional/
    ├── test_task_lifecycle_routes.py
    └── test_password_reset_routes.py

migrations/versions/                 # NUEVA migración add_soft_delete_and_reset_tokens
```

**Structure Decision**: Monolito de 4 capas del Incremento 1 sin cambios estructurales; solo extensiones aditivas en `models → services → routes` + tabla/columnas nuevas. Permite aislar dominio en pruebas y conservar todos los contratos previos.

---

## Complexity Tracking

Sin violaciones constitucionales. Sin abstracciones nuevas: no hay papelera/restauración, ni JWT, ni SMTP, ni capa de repositorio — todo lo añadido responde a un FR documentado (FR-001–FR-021).
