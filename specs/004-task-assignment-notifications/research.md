# Research: 003-task-assignment-notifications

**Feature**: 003-task-assignment-notifications (HU-10, HU-11)
**Date**: 2026-10-02
**Base**: Incrementos 1–3 (`001-basic-tasks-auth`, `002-task-lifecycle-recovery`); código actual `src/taskcontrol/{models,services,routes}`

Todas las decisiones respetan la constitución v1.0.0 (monolito, 4 capas, contratos explícitos, test-first, YAGNI, migraciones, seguridad backend, auditoría).

---

## R-01. `Task.user_id` como responsable + `created_by` informativo (no doble FK operativo)

- **Decision**: `user_id` se reinterpreta como *responsable actual* (única columna operativa de visibilidad/permisos). Se añade `created_by` (`FK users.id`, NOT NULL) como dato informativo inmutable que conserva al creador para la etiqueta "Asignada a mí (por …)" y el filtro `origin`. La asignación muta solo `user_id`; `created_by` nunca cambia tras la creación.
- **Rationale**: preserva intactas todas las consultas y guardas existentes (`get_user_tasks(filter_by user_id)`, `get_task_by_id`, `update_task_status/details`, guardas de soft-delete del Inc.2) — la visibilidad del asignado "de la misma forma que las suyas" (HU-10) sale gratis; mantiene el invariante FR-007 (responsable único) con una sola fuente de verdad; backfill trivial (`created_by = user_id`).
- **Alternatives considered**:
  - *Doble FK operativo (`owner_id` + `assignee_id`, listado por `OR`)*: rechazado — duplica guardas de autorización (¿quién edita/cambia estado/elimina tras delegar?), rompe `get_task_by_id` y exige índices compuestos nuevos, sin requisito del backlog que lo pida (viola YAGNI, Principio V).
  - *Tabla de asignaciones histórica separada (`task_assignments`)*: rechazado — sobrediseño para responsable único; el historial ya lo cubre `AuditLog(TASK_ASSIGNED)` (Principio VIII).

## R-02. `Notification` como historial persistente con `is_read`/`read_at`

- **Decision**: tabla `notifications(id, user_id destinatario FK, task_id FK, assigned_by FK, created_at UTC, is_read BOOL DEFAULT FALSE, read_at NULLABLE)` + índice `(user_id, is_read, created_at)`. Marcar como leída = `is_read=True, read_at=now`; jamás se borra la fila; sin endpoint de borrado ni caducidad.
- **Rationale**: cumple FR-011/FR-012 (persiste tras leerse, historial diferenciable) con el mecanismo más simple; `task_id` sin cascade preserva evidencia aunque la tarea se elimine (edge case del spec); el índice compuesto sirve el `unread_count` y el historial ordenado sin escaneos.
- **Alternatives considered**:
  - *Descartar al leer (DELETE)*: rechazado — contradice la decisión del spec y pierde evidencia de delegación.
  - *Notificación derivada (sin tabla, "tareas con created_by != user_id y sin vista")*: rechazado — no hay "momento de aviso" ni estado de lectura persistente; imposible el contador de pendientes y el historial tras reasignaciones.

## R-03. Contratos: `POST /tasks/<id>/assign` + blueprint `/notifications` + `?origin=` compatible

- **Decision**: `POST /tasks/<id>/assign {email}` (form + JSON, coherente con `POST /<id>/delete|/reopen` del Inc.2); blueprint nuevo `notifications.py` con `GET /` (lista + `unread_count`), `POST /<id>/read` (idempotente), `POST /read-all`; `GET /tasks` acepta `?origin=all|mine|assigned` donde ausente/inválido ≡ `all` (contrato Inc.1 intacto). Códigos de error nuevos: `USER_NOT_FOUND (404)`, `ASSIGN_TO_SELF (400)`; reutilizados: `TASK_NOT_FOUND (404)`, `VALIDATION_ERROR (400)`, `NOTIFICATION_NOT_FOUND (404)`, `401` sin sesión.
- **Rationale**: Principio III — cada endpoint documentado antes de codificar en `contracts/`; `POST` (no `PUT/PATCH`) porque los formularios HTML solo emiten GET/POST y el proyecto ya usa esa convención; `origin` como filtro de presentación derivado de `created_by vs user_id`, sin cambiar la fuente de visibilidad.
- **Alternatives considered**:
  - *`PUT /tasks/<id>` genérico con `{assignee}`*: rechazado — mezcla edición de contenido (HU-04) con transferencia de responsabilidad; impide códigos de error específicos y auditoría diferenciada.
  - *Marcar leída vía `PATCH /notifications/<id> {is_read}`*: rechazado — sobregeneraliza; las acciones dedicadas expresan intención y son idempotentes sin exponer mutaciones arbitrarias.

## R-04. Atomicidad: notificación creada dentro de `TaskService.assign_task()`

- **Decision**: `assign_task()` ejecuta en una única transacción `db.session`: transferencia `user_id` → `AuditService.log_event(TASK_ASSIGNED)` → `INSERT Notification` → `commit()` único. El blueprint no crea notificaciones ni audita; solo traduce excepciones a HTTP (Principio II).
- **Rationale**: garantiza SC-004 (exactamente una notificación por asignación exitosa) y su contrapositiva (cero notificaciones en fallos); sin colas ni doble commit (Principio I); el test de atomicidad con fallo inyectado es escribible a nivel de servicio sin HTTP.
- **Alternatives considered**:
  - *Crear la notificación en el blueprint tras llamar al servicio*: rechazado — dos unidades de trabajo separadas; un fallo entre ambas deja transferencia sin aviso o aviso sin transferencia.
  - *Señal/evento diferido*: rechazado — introduce infraestructura asíncrona prohibida por el Principio I sin justificación empírica.

## R-05. Migración única aditiva `add_assignment_and_notifications`

- **Decision**: una migración Alembic reversible: `ADD created_by NULL → backfill `created_by = user_id` → `SET NOT NULL + FK → users.id` + `CREATE TABLE notifications` (+ FKs, UNIQUE innecesario, índice compuesto). Flujo `flask db migrate -m … && flask db upgrade`.
- **Rationale**: Principio VI — versionada, reproducible, sin `db.create_all()` ni DDL manual; el backfill dentro de la propia migración evita scripts externos; filas de los incrementos previos quedan consistentes automáticamente.
- **Alternatives considered**:
  - *Dos migraciones (columna / tabla)*: admisible como variante operativa pero innecesaria; se documenta como alternativa válida si el motor exige NOT NULL en dos pasos.
  - *`created_by` NULLABLE permanente*: rechazado — debilita el invariante informativo y complica el filtro `origin` con un tercer estado.

## R-06. Estrategia de pruebas bloqueantes (Principio IV)

- **Decision**: Red-Green-Refactor obligatorio en `tests/services/test_task_assignment_service.py` (transferencia, rechazo a inexistente, listado del asignado, auto-asignación, ajena/eliminada, `TASK_ASSIGNED` con 4 campos, atomicidad con fallo inyectado) y `tests/services/test_notification_service.py` (una notificación por asignación, `unread_count`, `mark_read`/`mark_all_read` idempotentes y persistentes, aislamiento por destinatario, huérfana tras soft-delete); `tests/functional/` cubre los 5 contratos (códigos + envoltorio `{status,…}` + rama HTML `302`).
- **Rationale**: las tres propiedades del encargo son verificables a nivel de servicio sin HTTP (rápidas, deterministas); los tests funcionales solo aseguran la traducción excepción→código. Ninguna HU se cierra sin su suite en verde (puerta de calidad constitucional).
- **Alternatives considered**:
  - *Solo tests funcionales HTTP*: rechazado — más lentos y frágiles; no aíslan dominio (viola el espíritu del Principio II/IV).
