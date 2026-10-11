# Quickstart: Interacción fluida del listado (Incremento 5)

**Fecha**: 2026-10-11 | **Spec**: [spec.md](spec.md) | **Contratos**: [contracts/order-contracts.md](contracts/order-contracts.md) | **Modelo**: [data-model.md](data-model.md)

Guía de validación end-to-end. Sin código de implementación: los cuerpos de servicios, rutas y migraciones pertenecen a `tasks.md`/implementación.

## Prerrequisitos

1. Entorno unificado levantado con un comando (`docker compose up` o `run.sh` / `run.ps1`).
2. Migración de `sort_order` aplicada (ver `data-model.md` y R-05 en [research.md](research.md)).
3. Usuario registrado con ≥ 5 tareas (mezcla `pending`/`in_progress`) y sesión iniciada.
4. Backend sirviendo el listado SSR en `GET /tasks` y los contratos Inc.1 (`POST /tasks/<id>/status`).

## Q-1. Completar sin recarga (HU-15, éxito)

1. Abrir el listado con la pestaña de red del navegador visible.
2. Accionar completar en una tarea `pending`.
3. **Esperado**: la fila cambia a completada sin recarga (petición `POST /tasks/<id>/status` con `{"status":"completed"}` → `200`); tras recarga manual, persiste; `AuditLog(STATUS_CHANGED)` registrado. (SC-001, SC-004.)

## Q-2. Reordenar con arrastre (HU-16, éxito)

1. Con ≥ 3 tareas visibles, arrastrar una fila a otra posición y soltar.
2. **Esperado**: el orden cambia al instante (petición `POST /tasks/reorder` con `ordered_ids` → `200`); tras recarga, idéntico orden; `AuditLog(TASK_ORDER_CHANGED)` registrado. Repetir con 5 tareas (SC-003). Verificar que otro usuario no ve cambios (FR-009) y que los botones subir/bajar replican el comportamiento por teclado (FR-015).

## Q-3. Fallo al completar → reversión (HU-15, manual BLOQUEANTE)

> **Se indica explícitamente**: no hay infraestructura de pruebas frontend en el proyecto (sin `package.json` ni runner JS; solo `pytest`), por lo que esta verificación es **manual y bloqueante** para HU-15 (R-06).

1. Con red activa, abrir el listado; cortar la red (modo offline) o detener el backend; accionar completar.
2. **Esperado**: la fila revierte a su estado anterior y aparece un mensaje comprensible; ningún estado falso queda visible (SC-002). Repetir con sesión cerrada (debe pedir re-login) y con doble clic rápido (solo una confirmación prevalece).

## Q-4. Fallo al persistir orden → reversión (HU-16, manual BLOQUEANTE)

1. Reordenar con el backend detenido o forzando `500`.
2. **Esperado**: el listado vuelve al orden anterior confirmado + mensaje de error; tras recuperar el backend y recargar, el orden original intacto (FR-010).

## Q-5. Contratos y servicio (automatizado BLOQUEANTE, `pytest`)

```bash
pytest tests/services/test_task_service.py tests/functional/test_task_routes.py -q
```

**Esperado**: verde, incluyendo — persistencia de orden actualiza todas las afectadas con valores densos; lote con id ajeno rechaza íntegro (`404` neutro, nada escrito); tarea nueva al final; `401` sin sesión; `400` con lote vacío/duplicado; salto directo pendiente→completada vía `/status` intacto.
