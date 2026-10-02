# Contratos HTTP: Ciclo de vida — eliminar y reabrir (HU-05, HU-06)

**Blueprints**: `tasks_bp` (`/tasks`) — extiende `specs/001-basic-tasks-auth/contracts/task-contracts.md` sin modificarlo.
**Cumplimiento**: Principio III (contrato explícito), VII (sesión verificada en backend, aislamiento por `user_id`), VIII (auditoría por mutación).
**Convención Inc.1**: cada endpoint acepta `application/x-www-form-urlencoded` (HTML) y `application/json` (API). JSON se detecta como en `tasks.py` (`is_json` o `Accept: application/json`). Respuestas JSON con envoltorio `{status, message?, data?, code?}`.

> Nota de compatibilidad: `GET /tasks` (HU-02) **no cambia de contrato**; a partir de este incremento excluye `is_deleted=True` por defecto (ver `data-model.md`).

---

## 1. Eliminar tarea — soft delete (HU-05)

### `POST /tasks/<task_id>/delete`
Capa HTML/form necesita `POST` (los formularios no emiten `DELETE`). Es el endpoint canónico para ambos clientes.

- **Método**: `POST` (canónico). Alias opcional `DELETE /tasks/<task_id>` → misma semántica, solo JSON (recomendado exponerlo si el cliente JS usa `fetch`; si se omite no rompe HU-05).
- **Ruta**: `/tasks/<int:task_id>/delete`
- **Autenticación**: obligatoria (`session['user_id']`, decorador `login_required`).
- **Payload entrada**: vacío. JSON `{}` o sin cuerpo; formulario sin campos.
- **Efecto**: `TaskService.delete_task()` → `is_deleted=True, deleted_at=now_utc` + `AuditLog(TASK_DELETED)`.
- **Respuestas**:
  - `200 OK` (JSON) / `302 Found` (HTML → `/tasks` con flash):
    ```json
    { "status": "success", "message": "Tarea eliminada correctamente", "data": { "id": 102, "is_deleted": true, "deleted_at": "2026-10-02T12:00:00Z" } }
    ```
  - `404 Not Found` — tarea inexistente, de otro usuario, **o ya eliminada** (`code` distingue sin filtrar propiedad):
    ```json
    { "status": "error", "code": "TASK_NOT_FOUND", "message": "Tarea no encontrada" }
    ```
    ```json
    { "status": "error", "code": "TASK_ALREADY_DELETED", "message": "La tarea ya fue eliminada" }
    ```
  - `401 Unauthorized` — sin sesión.
- **Errores nuevos**: `TASK_ALREADY_DELETED` (segunda eliminación). Nunca se emite doble `TASK_DELETED`.

### Guarda transversal (sin endpoint propio)
`POST /tasks/<id>/status`, `POST|PUT /tasks/<id>/edit` y `GET /tasks/<id>/edit` sobre tarea eliminada → `404` (`TASK_NOT_FOUND`) o `400` (`TASK_DELETED`) según implemente la ruta; el plan fija `404 TASK_NOT_FOUND` para lectura/estado y `400 TASK_DELETED` admisible solo si la ruta ya cargó el objeto. `GET /tasks` nunca devuelve eliminadas.

---

## 2. Reabrir tarea completada (HU-06)

### `POST /tasks/<task_id>/reopen`
Endpoint dedicado — **no** reutilizar `/status` (ver `research.md` R-02).

- **Método**: `POST`
- **Ruta**: `/tasks/<int:task_id>/reopen`
- **Autenticación**: obligatoria.
- **Payload entrada**: vacío (`{}`).
- **Efecto**: `TaskService.reopen_task()` → `status: completed → pending` + `AuditLog(TASK_REOPENED, details={previous_status:'completed', current_status:'pending'})`.
- **Respuestas**:
  - `200 OK` (JSON) / `302 Found` (HTML):
    ```json
    { "status": "success", "message": "Tarea reabierta correctamente", "data": { "id": 102, "previous_status": "completed", "current_status": "pending", "updated_at": "2026-10-02T12:05:00Z" } }
    ```
  - `400 Bad Request` — tarea viva pero no completada:
    ```json
    { "status": "error", "code": "INVALID_STATE_TRANSITION", "message": "Solo las tareas completadas pueden reabrirse" }
    ```
  - `404 Not Found` — inexistente, ajena o eliminada:
    ```json
    { "status": "error", "code": "TASK_NOT_FOUND", "message": "Tarea no encontrada" }
    ```
  - `401 Unauthorized` — sin sesión.
- **Invariante**: `POST /tasks/<id>/status` con `{"status":"pending"}` desde `completed` **sigue devolviendo** `400 INVALID_STATE_TRANSITION` (contrato Inc.1 intacto).
