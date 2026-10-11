# Implementation Plan: 003-task-assignment-notifications

**Branch**: `003-task-assignment-notifications` | **Date**: 2026-10-02 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/003-task-assignment-notifications/spec.md` (HU-10 asignación, HU-11 notificación interna; base: Incrementos 1–3 implementados).

---

## Summary

Colaboración entre usuarios sobre el monolito TaskControl sin romper los incrementos previos: (1) asignación con transferencia de responsabilidad a un único responsable — `Task.user_id` se reinterpreta como responsable actual y se añade `Task.created_by` solo informativo (`research.md` R-01); (2) entidad nueva `Notification` con historial persistente y flag de lectura (`is_read`/`read_at`); (3) el servicio `TaskService.assign_task()` ejecuta en una única transacción validación del destinatario en backend + transferencia + `TASK_ASSIGNED` + creación de exactamente una notificación (atomicidad, `research.md` R-04); (4) contratos nuevos `POST /tasks/<id>/assign`, `GET /notifications`, `POST /notifications/<id>/read`, `POST /notifications/read-all`, y extensión compatible de `GET /tasks` con filtro `origin` (Principio III); (5) todo cambio de esquema vía una migración Alembic aditiva; (6) suites bloqueantes Red-Green-Refactor para las tres propiedades exigidas (una notificación por asignación, rechazo a inexistente, visibilidad en listado del asignado).

Decisiones y alternativas en [`research.md`](./research.md). Esquema en [`data-model.md`](./data-model.md). Contratos en [`contracts/`](./contracts/assignment-notification-contracts.md). Validación E2E en [`quickstart.md`](./quickstart.md).

---

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: Flask 3.x, Flask-SQLAlchemy (SQLAlchemy 2.x), Flask-Migrate (Alembic), Werkzeug
**Storage**: Relacional existente (SQLite dev/test, PostgreSQL-compatible); 1 columna nueva en `tasks` (`created_by`) + backfill desde `user_id`; tabla nueva `notifications`
**Testing**: pytest + pytest-flask; suites bloqueantes `tests/services/` (Principio IV) + `tests/functional/` para contratos
**Target Platform**: Monolito único (`flask run` / `run.ps1`), Windows/Linux/macOS server
**Project Type**: Monolito web (Jinja2 SSR + JS vanilla; este incremento solo exige renderizado con recarga clásica, sin HU-15/HU-16)
**Performance Goals**: Asignación <200 ms local (2 lookups indexados por PK/email + 1 transacción); `GET /tasks` mantiene <100 ms (índice existente en `tasks.user_id`; filtro `origin` resuelto en Python sobre `created_by`, sin índice nuevo obligatorio); `GET /notifications` O(n) del destinatario con índice compuesto
**Constraints**: Cero microservicios/colas/correo externo (PI); 4 capas sin saltos blueprint→ORM (PII); contratos previos (PIII); TDD bloqueante servicios (PIV); solo migraciones versionadas (PVI); validación backend + sesión por endpoint (PVII); auditoría `actor_id/action/entity_id/timestamp` por mutación (PVIII)
**Scale/Scope**: 2 HU (HU-10 P1, HU-11 P2); 4 endpoints nuevos + 1 extensión compatible; 1 entidad nueva + 1 columna; 0 cambios rompedores a contratos previos

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio | Estado | Mecanismo de cumplimiento en este incremento |
|---|---|---|
| **I. Monolito por diseño** | PASS | Un proceso Flask, una BD relacional. Notificación creada en la misma transacción del servicio (cero colas, cero workers, cero SMTP). |
| **II. Separación en 4 capas** | PASS | `models/` (Task extendido, Notification nuevo) ← `services/` (`TaskService.assign_task`, `NotificationService`) ← `routes/` (`tasks.py`, `notifications.py` nuevo) ← `templates/`. Blueprints sin ORM directo. |
| **III. Contrato explícito** | PASS | `contracts/assignment-notification-contracts.md` (assign, notifications list/read/read-all, extensión `GET /tasks?origin=`): ruta, método, payloads in/out y códigos por endpoint, definidos antes de codificar. |
| **IV. Test-first bloqueante** | PASS | Suites `test_task_assignment_service`, `test_notification_service` en Red-Green-Refactor; las 3 propiedades del encargo son tests bloqueantes (ver §7). |
| **V. Simplicidad (YAGNI)** | PASS | Responsable único (sin multi-asignados ni roles); `created_by` informativo sin índice ni permisos asociados; notificaciones sin borrado ni caducidad; sin correo/push. |
| **VI. Integridad y migraciones** | PASS | Migración única aditiva/reversible vía `flask db migrate/upgrade` con backfill `created_by = user_id` por `SERVER_DEFAULT`/UPDATE de migración; prohibido `db.create_all()` y DDL manual (ver §6). |
| **VII. Seguridad por defecto** | PASS | Lookup del destinatario por email normalizado en el servicio; rechazo a no registrado sin mutación ni fuga diferencial más allá del mensaje de asignación; sesión y propiedad verificadas por endpoint; sin secretos en notificaciones/auditoría. |
| **VIII. Observabilidad mínima** | PASS | `TASK_ASSIGNED` con los 4 campos + `details={previous_owner_id, new_owner_id, assigned_to_email}` vía `AuditService` centralizado, en la misma transacción que la transferencia. |

Post-diseño (Fase 1): sin violaciones; no se requiere tabla de complejidad.

---

## 1. Modelo Task: `user_id` como responsable + `created_by` informativo (HU-10)

Decisión justificada en `research.md` R-01, esquema en `data-model.md` §2.1:

- **No se crean dos campos operativos**. `Task.user_id` **se reinterpreta** como *responsable actual* (quien ve y opera la tarea). Se añade `Task.created_by` (`FK users.id`, NOT NULL) como dato **informativo** que conserva al creador original para la etiqueta "Asignada a mí (por …)" y el filtro de origen.
- **Por qué**: (a) preserva la semántica de todas las consultas y guardas existentes (`filter_by(user_id=…)`, `get_task_by_id`, `update_task_status/details`, soft-delete del Inc.2) sin reescribir el aislamiento por usuario; (b) mantiene el invariante "un único responsable" exigible por FR-007 con una sola columna de verdad operativa; (c) YAGNI: la alternativa de doble FK operativo (`owner_id` + `assignee_id` con listado por `OR`) duplica las guardas de autorización y obliga a decidir quién edita/cambia estado/elimina tras delegar, sin requisito del backlog que lo pida.
- **Reglas**: crear tarea ⇒ `user_id = created_by = autor`; asignar ⇒ solo `user_id` muta al destinatario, `created_by` jamás cambia; `created_by` no otorga visibilidad ni permisos (la visibilidad deriva exclusivamente de `user_id` + `is_deleted=False`).
- **Backfill**: filas preexistentes quedan `created_by = user_id` vía migración (ver §6); invariante garantizado hacia adelante por `create_task()`.

## 2. Modelo Notification: historial persistente con lectura explícita (HU-11)

Esquema en `data-model.md` §2.2 (`research.md` R-02):

- `Notification(id, user_id FK destinatario INDEX, task_id FK tarea, assigned_by FK asignador, created_at UTC, is_read BOOL DEFAULT FALSE, read_at UTC NULLABLE)`, índice compuesto `(user_id, is_read, created_at)`.
- **Pertenencia**: al destinatario (`user_id`); **referencia**: a la tarea delegada (`task_id`, sin cascade de borrado — la notificación sobrevive como evidencia aunque la tarea se elimine lógicamente); **estado**: `is_read=False/read_at=NULL` al nacer, `True/now` al marcarse; **timestamp**: `created_at` = momento de la asignación (misma transacción, §4).
- **Sin borrado ni caducidad** en este incremento (FR del spec): marcar como leída nunca elimina la fila; no hay endpoint de borrado.

## 3. Contratos de nuevos endpoints + extensión de listado (Principio III)

Definición completa en `contracts/assignment-notification-contracts.md`; resumen:

| Endpoint | Método/Ruta | In → Out | Errores |
|---|---|---|---|
| Asignar/reasignar (HU-10) | `POST /tasks/<id>/assign` auth obligatoria | in `{email}` → out `200 {id, previous_owner_id, new_owner_id, assigned_to_email}` / HTML `302→/tasks` | `401` sin sesión; `404 TASK_NOT_FOUND` (inexistente/ajena/eliminada); `404 USER_NOT_FOUND` (correo no registrado); `400 ASSIGN_TO_SELF` (auto-asignación); `400 VALIDATION_ERROR` (email ausente/inválido) |
| Listar notificaciones (HU-11) | `GET /notifications` auth obligatoria | out `200 {notifications:[{id, task_id, task_title, assigned_by, assigned_by_email, created_at, is_read}], unread_count}` / HTML con indicador | `401` sin sesión |
| Marcar una como leída (HU-11) | `POST /notifications/<id>/read` auth obligatoria | in vacío → out `200 {id, is_read:true, read_at}` / HTML `302` | `401`; `404 NOTIFICATION_NOT_FOUND` (inexistente/ajena); idempotente si ya leída |
| Marcar todas como leídas (HU-11) | `POST /notifications/read-all` auth obligatoria | in vacío → out `200 {marked_count}` / HTML `302` | `401` |
| Listado de tareas extendido (HU-02+HU-10) | `GET /tasks?origin=all\|mine\|assigned` auth obligatoria | compatible: sin `origin` ≡ `all` (contrato Inc.1 intacto); cada item añade `{created_by, assigned:boolean, assigned_by_email?}` | `401`; `origin` inválido se ignora → `all` |

`POST /tasks/<id>/status`, `/edit`, `/delete`, `/reopen` **no cambian de contrato**: operan sobre el responsable actual (`user_id`) exactamente igual que antes.

## 4. Punto de creación de la notificación: misma transacción del servicio (atomicidad)

Flujo en `TaskService.assign_task(actor_id, task_id, raw_email)` (`research.md` R-04, `data-model.md` §3):

1. Cargar tarea viva del actor (`get_task_by_id` + guarda `is_deleted` → `404`); normalizar email (`strip().lower()`, validar formato → `400`).
2. Resolver destinatario por email en backend; inexistente → `UserNotFoundError` → `404 USER_NOT_FOUND`, **sin mutación, sin auditoría, sin notificación**.
3. Auto-asignación (`destino == actor`) → `400 ASSIGN_TO_SELF` sin efectos.
4. En **una sola transacción** (`db.session`): `task.user_id = destino.id` → `AuditService.log_event(TASK_ASSIGNED, …)` → `Notification(user_id=destino, task_id, assigned_by=actor)` → `commit()` único. Si cualquier paso falla, rollback total: nunca hay transferencia sin notificación ni notificación sin transferencia (SC-004).
5. El blueprint solo traduce excepciones a códigos HTTP; jamás consulta `User`/`Task`/`Notification` directamente (Principio II).

## 5. Validación backend del destinatario (Principio VII)

- El email se valida y normaliza **en el servicio**, no en el formulario/selector: `strip()`, comparación insensible a mayúsculas (coherente con registro normalizado en minúsculas del Inc.1), regex de formato; cualquier manipulación del frontend (email inexistente inyectado) muere en el lookup.
- Respuesta ante no registrado: `404 {code: USER_NOT_FOUND, message: "No existe un usuario con ese correo"}` — error controlado, estado inalterado, cero eventos. (Diferencia asumida con HU-14: allí la neutralidad anti-enumeración es requisito; aquí el asignador necesita saber que el destinatario no existe para corregir el correo, y el spec/FR-003 exige rechazo explícito.)
- Autorización: solo el responsable actual (`task.user_id == actor`) puede asignar; tareas ajenas/eliminadas → `404` sin distinguir propiedad (no fuga de existencia ajena más allá de lo ya establecido en incrementos previos).

## 6. Migraciones sobre el esquema existente (Principio VI)

Migración única `add_assignment_and_notifications` (`research.md` R-05):

- `ALTER TABLE tasks ADD COLUMN created_by INTEGER NULL` → `UPDATE tasks SET created_by = user_id WHERE created_by IS NULL` → `ALTER COLUMN created_by SET NOT NULL` + `FK created_by → users.id` (sin cascade de borrado) + índice opcional. Orden conmutable a dos migraciones si el motor lo exige; siempre reversible (`downgrade()` elimina FK/columna/tabla).
- `CREATE TABLE notifications (id PK, user_id FK→users.id NOT NULL INDEX, task_id FK→tasks.id NOT NULL INDEX, assigned_by FK→users.id NOT NULL, created_at NOT NULL, is_read NOT NULL SERVER_DEFAULT FALSE, read_at NULL)` + `INDEX(user_id, is_read, created_at)`.
- Flujo: `flask db migrate -m "add_assignment_and_notifications" && flask db upgrade`. Sin pérdida de tareas/auditoría/tokens previos; reproducible dev/test/prod. Prohibido `db.create_all()` y DDL manual.

## 7. Pruebas bloqueantes modelo/servicio (Principio IV)

Gate de integración: suites de `research.md` R-06 y escenarios de `quickstart.md` en verde. Bloqueantes exigidos por el encargo:

- **Exactamente una notificación por asignación**: asignar A→B crea 1 `Notification(user_id=B, task_id, assigned_by=A)`; reasignar B→C crea 1 más para C (total 2, 1 no leída para C); conteo `unread_count` coherente.
- **Imposible asignar a inexistente**: email no registrado → excepción/`404 USER_NOT_FOUND`, `task.user_id` inalterado, 0 `TASK_ASSIGNED`, 0 notificaciones.
- **Listado del asignado incluye la tarea**: tras A→B, `get_user_tasks(B)` contiene la tarea y `get_user_tasks(A)` ya no; filtro `origin=mine|assigned|all` clasifica por `created_by vs user_id`; etiqueta "Asignada a mí" derivable (`created_by != user_id`).
- Cobertura adyacente obligatoria: ajena/eliminada → `404`; auto-asignación → `400` sin efectos; formato inválido → `400`; marcar leída individual + `read-all` (idempotentes, persisten); notificaciones ajenas → `404`; `TASK_ASSIGNED` con los 4 campos + `details` sin secretos; atomicidad (fallo inyectado ⇒ ni transferencia ni notificación ni auditoría parcial).

---

## Project Structure

### Documentation (this feature)

```text
specs/003-task-assignment-notifications/
├── spec.md                          # Especificación funcional (HU-10, HU-11)
├── plan.md                          # Este plan técnico
├── research.md                      # Fase 0: decisiones R-01..R-06
├── data-model.md                    # Fase 1: delta Task + Notification + flujo assign
├── quickstart.md                    # Fase 1: validación E2E y suites
├── contracts/                       # Fase 1: contratos explícitos (Principio III)
│   └── assignment-notification-contracts.md  # assign, notifications, extensión GET /tasks
├── checklists/
└── tasks.md                         # Fase 2 (comando /speckit-tasks, NO generado aquí)
```

### Source Code (repository root — delta sobre incrementos previos)

```text
src/taskcontrol/
├── models/
│   ├── task.py                      # + created_by FK users.id (+ relación creator)
│   ├── notification.py              # NUEVO modelo Notification
│   ├── user.py                      # + relationships notifications/assigned (lazy, sin DDL)
│   └── __init__.py                  # exportar Notification
├── services/
│   ├── task_service.py              # + assign_task (+ UserNotFoundError, AssignToSelfError); create/get incorporan created_by/origin
│   ├── notification_service.py      # NUEVO: list/mark_read/mark_all_read/unread_count
│   └── audit_service.py             # sin cambios (nueva action por convención)
├── routes/
│   ├── tasks.py                     # + POST /<id>/assign; GET /tasks acepta ?origin=
│   ├── notifications.py             # NUEVO blueprint /notifications (GET, POST /<id>/read, POST /read-all)
│   └── __init__.py                  # registrar notifications_bp
└── templates/ static/               # formulario "Asignar por correo" + filtro origin + página notificaciones con contador

tests/
├── services/                        # BLOQUEANTES (PIV)
│   ├── test_task_assignment_service.py
│   └── test_notification_service.py
└── functional/
    ├── test_assignment_routes.py
    └── test_notification_routes.py

migrations/versions/                 # NUEVA migración add_assignment_and_notifications
```

**Structure Decision**: Monolito de 4 capas de los incrementos previos sin cambios estructurales; solo extensiones aditivas en `models → services → routes` + tabla/columna nuevas. Conserva todos los contratos previos salvo la extensión compatible de `GET /tasks`.

---

## Complexity Tracking

Sin violaciones constitucionales. Sin abstracciones nuevas: sin multi-responsables, sin roles, sin borrado/caducidad de notificaciones, sin correo/push, sin capa de repositorio — todo lo añadido responde a un FR documentado (FR-001–FR-014).
