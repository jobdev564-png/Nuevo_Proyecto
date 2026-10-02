# Quickstart & Guía de Validación: 002-task-lifecycle-recovery

**Feature**: 002-task-lifecycle-recovery (HU-05, HU-06, HU-14)
**Date**: 2026-10-02
**Base**: Asume Incremento 1 desplegado y migrado (`flask db upgrade` al día). No duplica implementación; solo validación E2E. Detalles de esquema en `data-model.md`, endpoints en `contracts/`.

---

## 1. Prerrequisitos

- Entorno del Incremento 1 operativo (`.venv`, `requirements.txt` instalado, `.env` con `SECRET_KEY` + `DATABASE_URL`).
- Migración de este incremento generada y aplicada (ver `plan.md` §6):
  ```powershell
  .\.venv\Scripts\Activate.ps1
  flask db migrate -m "add_soft_delete_and_reset_tokens"
  flask db upgrade
  ```
- Servidor: `.\run.ps1` o `flask run --port 5000` → `http://127.0.0.1:5000`.

## 2. Suite automatizada (Principio IV — bloqueante a nivel servicio)

```powershell
pytest tests/services/test_task_soft_delete.py tests/services/test_task_reopen.py tests/services/test_password_reset_service.py -v
pytest tests/functional/test_task_lifecycle_routes.py tests/functional/test_password_reset_routes.py -v
pytest -v
```

Verde obligatorio antes de integrar (Quality Gate de la constitución).

## 3. Escenarios E2E (validación manual / curl)

### E1. Eliminación lógica (HU-05)
1. Login → `POST /tasks` crea "Tarea a depurar".
2. `POST /tasks/<id>/delete` → `200` + `{"is_deleted": true}`.
3. `GET /tasks` → la tarea **no aparece**; en BD la fila persiste con `is_deleted=1, deleted_at NOT NULL`.
4. Repetir `POST /tasks/<id>/delete` → `404 TASK_ALREADY_DELETED`.
5. `POST /tasks/<id>/status` o `/edit` sobre ella → `404`; con otro usuario → `404` y tarea intacta.
6. En `audit_logs`: existe `TASK_DELETED` con `actor_id, action, entity_id, timestamp`.

### E2. Reapertura (HU-06)
1. Completar una tarea (`POST /tasks/<id>/status {"status":"completed"}`).
2. `POST /tasks/<id>/reopen` → `200`, `current_status=pending`; reaparece en filtro `?status=pending`.
3. En `audit_logs`: `TASK_REOPENED` (distinto de `STATUS_CHANGED`).
4. `POST /tasks/<id>/reopen` sobre `pending/in_progress` → `400 INVALID_STATE_TRANSITION`; sobre eliminada → `404`; `POST .../status {"status":"pending"}` desde `completed` → sigue `400`.

### E3. Recuperación de contraseña (HU-14)
1. `POST /auth/password-reset-request {"email": <registrado>}` → `200` mensaje neutro; el log del servidor muestra el enlace con `?token=...`.
2. Repetir con correo inexistente → **mismo** `200` y mensaje; sin token en logs.
3. `POST /auth/password-reset-confirm {"token": ..., "new_password": "NuevaClave123!"}` → `200`; login con la nueva clave funciona.
4. Reusar el token → `400 INVALID_OR_EXPIRED_TOKEN`; token de >60 min → mismo rechazo; pedir un token nuevo invalida el anterior.
5. En `audit_logs`: `PASSWORD_RESET_REQUESTED` y `PASSWORD_RESET_COMPLETED` sin secretos en `details`.
