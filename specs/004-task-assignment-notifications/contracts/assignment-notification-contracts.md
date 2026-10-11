# Contratos HTTP: Asignación y notificaciones (HU-10, HU-11)

**Blueprints**: `tasks_bp` (`/tasks`, extendido) + `notifications_bp` nuevo (`/notifications`).
**Cumplimiento**: Principio III (contrato explícito), VII (sesión y propiedad verificadas en backend, destinatario resuelto en servicio), VIII (auditoría por mutación).
**Convención de incrementos previos**: cada endpoint acepta `application/x-www-form-urlencoded` (HTML) y `application/json` (API). JSON se detecta como en `tasks.py` (`is_json` o `Accept: application/json`). Respuestas JSON con envoltorio `{status, message?, data?, code?}`.
**Base**: extiende `specs/001-basic-tasks-auth/contracts/task-contracts.md` y `specs/002-task-lifecycle-recovery/contracts/` sin modificarlos, salvo la extensión compatible de `GET /tasks`.

---

## 1. Asignar / reasignar tarea (HU-10)

### `POST /tasks/<task_id>/assign`

Endpoint dedicado — **no** reutilizar `/edit` (ver `research.md` R-03).

- **Método**: `POST`
- **Ruta**: `/tasks/<int:task_id>/assign`
- **Autenticación**: obligatoria (`session['user_id']`, decorador `login_required`).
- **Payload entrada**:
  - JSON: `{ "email": "destino@ejemplo.com" }`
  - Formulario HTML: campo `email`.
- **Efecto**: `TaskService.assign_task()` → `task.user_id = destino` (transferencia) + `AuditLog(TASK_ASSIGNED, details={previous_owner_id, new_owner_id, assigned_to_email})` + `Notification(destino, task_id, assigned_by=actor)` en una transacción.
- **Respuestas**:
  - `200 OK` (JSON) / `302 Found` (HTML → `/tasks` con flash):
    ```json
    { "status": "success", "message": "Tarea asignada correctamente", "data": { "id": 102, "previous_owner_id": 1, "new_owner_id": 2, "assigned_to_email": "destino@ejemplo.com" } }
    ```
  - `404 Not Found` — tarea inexistente, de otro usuario o eliminada (sin distinguir):
    ```json
    { "status": "error", "code": "TASK_NOT_FOUND", "message": "Tarea no encontrada" }
    ```
  - `404 Not Found` — correo sin usuario registrado (sin mutación, sin auditoría, sin notificación):
    ```json
    { "status": "error", "code": "USER_NOT_FOUND", "message": "No existe un usuario con ese correo" }
    ```
  - `400 Bad Request` — auto-asignación (sin efectos):
    ```json
    { "status": "error", "code": "ASSIGN_TO_SELF", "message": "La tarea ya te pertenece" }
    ```
  - `400 Bad Request` — email ausente o con formato inválido:
    ```json
    { "status": "error", "code": "VALIDATION_ERROR", "message": "El correo del destinatario no es válido" }
    ```
  - `401 Unauthorized` — sin sesión.
- **Normalización**: `strip()` + comparación insensible a mayúsculas en el servicio (Principio VII); el frontend puede ofrecer selector, pero la verdad la decide el backend.

---

## 2. Listar notificaciones del usuario autenticado (HU-11)

### `GET /notifications`

- **Método**: `GET`
- **Ruta**: `/notifications`
- **Autenticación**: obligatoria. Solo devuelve notificaciones del solicitante (`user_id == session`), ordenadas por `created_at DESC`.
- **Payload entrada**: vacío. Query opcional `?unread_only=1` (solo pendientes; por defecto incluye historial leído).
- **Respuestas**:
  - `200 OK` (JSON) / `200` HTML (página con indicador de pendientes):
    ```json
    { "status": "success", "data": { "notifications": [ { "id": 7, "task_id": 102, "task_title": "Preparar informe", "assigned_by": 1, "assigned_by_email": "origen@ejemplo.com", "created_at": "2026-10-02T12:00:00Z", "is_read": false, "read_at": null } ], "unread_count": 1, "count": 1 } }
    ```
  - `401 Unauthorized` — sin sesión.
- **Nota**: si la tarea referida fue eliminada tras notificar, el item se sigue devolviendo con `task_title` conocido y la navegación a la tarea informa no disponible (edge case del spec).

---

## 3. Marcar una notificación como leída (HU-11)

### `POST /notifications/<notification_id>/read`

- **Método**: `POST`
- **Ruta**: `/notifications/<int:notification_id>/read`
- **Autenticación**: obligatoria.
- **Payload entrada**: vacío (`{}`).
- **Efecto**: `NotificationService.mark_read()` → `is_read=True, read_at=now_utc`. Idempotente: si ya estaba leída, responde `200` sin mutar. La fila **persiste** (no se elimina).
- **Respuestas**:
  - `200 OK` (JSON) / `302 Found` (HTML → `/notifications`):
    ```json
    { "status": "success", "message": "Notificación marcada como leída", "data": { "id": 7, "is_read": true, "read_at": "2026-10-02T12:05:00Z" } }
    ```
  - `404 Not Found` — inexistente o de otro usuario:
    ```json
    { "status": "error", "code": "NOTIFICATION_NOT_FOUND", "message": "Notificación no encontrada" }
    ```
  - `401 Unauthorized` — sin sesión.

---

## 4. Marcar todas como leídas (HU-11)

### `POST /notifications/read-all`

> Debe registrarse **antes** que `/<id>/read` en el blueprint para que `read-all` no se interprete como `<notification_id>`.

- **Método**: `POST`
- **Ruta**: `/notifications/read-all`
- **Autenticación**: obligatoria.
- **Payload entrada**: vacío.
- **Efecto**: `NotificationService.mark_all_read()` → todas las pendientes del solicitante a leídas en un lote.
- **Respuestas**:
  - `200 OK` (JSON) / `302 Found` (HTML):
    ```json
    { "status": "success", "message": "Notificaciones marcadas como leídas", "data": { "marked_count": 3 } }
    ```
  - `401 Unauthorized` — sin sesión.

---

## 5. Extensión compatible del listado de tareas (HU-02 + HU-10)

### `GET /tasks?origin=all|mine|assigned` (extiende, no rompe)

- **Método/Ruta**: `GET /tasks` (existente). Nuevo query opcional `origin`:
  - ausente o inválido ≡ `all` (comportamiento del contrato Inc.1, byte a byte);
  - `mine` ⇔ tareas donde `user_id == viewer AND created_by == viewer`;
  - `assigned` ⇔ tareas donde `user_id == viewer AND created_by != viewer`;
  - en todos los casos se excluyen eliminadas (Inc.2) y se conservan filtros `status` y ordenación existentes (combinables: `?status=pending&origin=assigned`).
- **Presentación**: cada item añade solo lectura `{created_by, assigned:boolean, assigned_by_email?}`; el `to_dict()` base no pierde campos. La etiqueta "Asignada a mí (por …)" y el selector de filtro se alimentan de estos campos.
- **Respuestas**: `200` con envoltorio existente + `origin` eco (`{tasks, count, filter, origin}`); `401` sin sesión. Sin nuevos códigos de error.
