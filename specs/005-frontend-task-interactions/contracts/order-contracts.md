# Contratos HTTP: Reordenamiento manual del listado (HU-16)

**Blueprint**: `tasks_bp` (`/tasks`) — extiende `specs/001-basic-tasks-auth/contracts/task-contracts.md` sin modificarlo y convive con `specs/002-task-lifecycle-recovery/contracts/task-lifecycle-contracts.md`.
**Cumplimiento**: Principio III (contrato explícito previo a implementar), VII (sesión + propiedad por tarea), VIII (auditoría por persistencia).
**Convención Inc.1**: acepta `application/json` (cliente JS con `fetch`) y `application/x-www-form-urlencoded` (degradación); respuestas JSON con envoltorio `{status, message?, data?, code?}`.

> HU-15 no define contrato nuevo: reutiliza `POST /tasks/<id>/status` (`{"status": "completed"}`, salto directo pendiente→completada permitido desde Inc.1, `AuditLog(STATUS_CHANGED)`). Ver Inc.1 `task-contracts.md` §3.

---

## `POST /tasks/reorder` — persistir orden manual (único contrato nuevo del incremento)

Recibe la lista ordenada de ids **de la vista filtrada actual** tras soltar el elemento (o tras accionar subir/bajar) y la persiste atómicamente para el usuario autenticado.

- **Método**: `POST` (canónico; formularios HTML no emiten `PATCH/PUT`). Alias opcional `PATCH /tasks/reorder` → misma semántica, solo JSON.
- **Ruta**: `/tasks/reorder` (¡antes que `/tasks/<id>` en el registro del blueprint para evitar capturas!).
- **Autenticación**: obligatoria (`session['user_id']`, decorador `login_required`).
- **Headers**: `Content-Type: application/json`; `Accept: application/json`.
- **Payload entrada**:
  ```json
  { "ordered_ids": [34, 31, 37], "view": "pending" }
  ```
  - `ordered_ids` (requerido): array no vacío de enteros, sin duplicados, con exactamente los ids visibles de la vista declarada.
  - `view` (opcional): `all` (defecto) | `pending` | `in_progress` | `completed`; documenta a qué vista aplica el orden.
- **Efecto**: `TaskService.reorder_tasks(user_id, ordered_ids, view)` → renumeración densa `sort_order = 0..N-1` en el orden recibido, en una transacción; tareas del usuario fuera de la vista conservan su valor + `AuditLog(TASK_ORDER_CHANGED)` por persistencia (aclaración 2026-10-11).
- **Orden de lectura**: `GET /tasks` (contrato sin cambios) ordena `sort_order ASC, id ASC` dentro del filtro; las tareas nuevas aparecen al final (`max+1`).
- **Respuestas**:
  - `200 OK`:
    ```json
    { "status": "success", "message": "Orden actualizado correctamente", "data": { "ordered_ids": [34, 31, 37], "view": "pending" } }
    ```
  - `400 Bad Request` — cuerpo ausente o `ordered_ids` vacío/duplicado/incompleto respecto a la vista:
    ```json
    { "status": "error", "code": "VALIDATION_ERROR", "message": "La lista ordenada es obligatoria y no puede estar vacía" }
    ```
    ```json
    { "status": "error", "code": "ORDER_INCOMPLETE", "message": "La lista no coincide con las tareas de la vista actual" }
    ```
  - `401 Unauthorized` — sin sesión:
    ```json
    { "status": "error", "code": "UNAUTHORIZED", "message": "Es necesario iniciar sesión" }
    ```
  - `404 Not Found` — algún id inexistente, eliminado o de otro usuario (neutro, sin distinguir causa):
    ```json
    { "status": "error", "code": "TASK_NOT_FOUND", "message": "Tarea no encontrada" }
    ```
- **Notas de cliente (JS)**: ante `4xx/5xx` o fallo de red, revertir al orden anterior confirmado y mostrar mensaje no técnico (FR-010). Ante `401`, avisar de re-login. El cuerpo nunca incluye secretos; el log de auditoría registra ids, no contenidos.
