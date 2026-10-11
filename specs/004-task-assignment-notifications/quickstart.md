# Quickstart: 003-task-assignment-notifications

**Feature**: 003-task-assignment-notifications (HU-10, HU-11) | **Date**: 2026-10-02
**Precondición**: incrementos 1–3 operativos; BD migrada con `add_assignment_and_notifications`.

Guía de validación E2E (sin código de implementación: los cuerpos de modelos/servicios/rutas/migraciones y las suites completas pertenecen a `tasks.md` y a la fase de implementación).

---

## 1. Preparar entorno

```powershell
# Desde la raíz del repo
.\run.ps1            # o: docker compose up / flask run
flask db upgrade     # aplica add_assignment_and_notifications (Principio VI)
pytest tests/services/test_task_assignment_service.py tests/services/test_notification_service.py -v
```

Esperado: ambas suites bloqueantes en verde antes de probar rutas (Principio IV).

## 2. Escenario A — Asignación exitosa genera exactamente una notificación (HU-10 → HU-11)

1. Registra e inicia sesión como `a@ejemplo.com`; crea la tarea "Preparar informe".
2. Registra `b@ejemplo.com`.
3. Como A: `POST /tasks/<id>/assign {"email": "b@ejemplo.com"}` → `200 {new_owner_id: B}` (o `302` en HTML).
4. Verifica como B (tras recarga, sin JS asíncrono):
   - `GET /tasks` incluye "Preparar informe" con etiqueta "Asignada a mí (por a@ejemplo.com)"; `?origin=assigned` la muestra, `?origin=mine` no; como A ya no aparece.
   - `GET /notifications` devuelve exactamente 1 item (`task_id`, `assigned_by_email=a@ejemplo.com`) y `unread_count=1`.
5. Verifica auditoría: existe un único `TASK_ASSIGNED` con `actor_id=A`, `entity_id=<id>`, `timestamp` UTC y `details={previous_owner_id, new_owner_id}`.

## 3. Escenario B — Rechazo a correo no registrado (Principio VII)

1. Como A con tarea propia: `POST /tasks/<id>/assign {"email": "fantasma@ejemplo.com"}` → `404 USER_NOT_FOUND`.
2. Verifica: la tarea sigue en el listado de A intacta; no existe `TASK_ASSIGNED` nuevo; `GET /notifications` de A y de cualquier usuario no muestra nada nuevo.

## 4. Escenario C — Reasignación + lectura persistente (HU-10 + HU-11)

1. Registra `c@ejemplo.com`. Como B (responsable actual): `POST /tasks/<id>/assign {"email": "c@ejemplo.com"}` → `200`.
2. Como C: `GET /tasks?origin=assigned` muestra la tarea; como B ya no.
3. Como C: `GET /notifications` → 1 pendiente; `POST /notifications/<nid>/read` → `200 {is_read:true}`; recarga: sigue visible como leída y `unread_count=0`.
4. Crea una segunda asignación hacia C y usa `POST /notifications/read-all` → `200 {marked_count:1}`; el historial conserva ambas como leídas.

## 5. Escenario D — Guardas (matriz mínima de rechazos)

| Caso | Esperado |
|---|---|
| Asignar tarea ajena o eliminada | `404 TASK_NOT_FOUND`, sin efectos |
| Auto-asignación (`email` propio) | `400 ASSIGN_TO_SELF`, sin auditoría ni notificación |
| Email ausente/malformado | `400 VALIDATION_ERROR` |
| `POST /notifications/<nid>/read` ajena | `404 NOTIFICATION_NOT_FOUND` |
| Sin sesión en cualquier endpoint nuevo | `401` |
| `GET /tasks?origin=bogus` | equivale a `all` (sin error) |

## 6. Criterio de aceptación del incremento

Verde en: las 2 suites bloqueantes de servicio + `tests/functional/test_assignment_routes.py` + `tests/functional/test_notification_routes.py` + escenarios A–D manuales; `TASK_ASSIGNED` presente por cada transferencia; cero notificaciones por correo/push (solo internas); `GET /tasks` sin `origin` byte-compatible con el incremento anterior.
