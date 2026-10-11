# Data Model: Interacción fluida del listado de tareas (Incremento 5)

**Fecha**: 2026-10-11 | **Spec**: [spec.md](spec.md) | **Contratos**: [contracts/order-contracts.md](contracts/order-contracts.md)

Único cambio estructural del incremento: `Task.sort_order`. Resto del modelo sin cambios.

## 1. Task (extendida)

| Campo | Tipo | Restricciones | Origen | Notas |
|-------|------|---------------|--------|-------|
| `id` | Integer PK autoincrement | — | Inc.1 | Identificador usado en `data-task-id`. |
| `user_id` | Integer FK → `users.id`, index | NOT NULL | Inc.1 | Propietario; el orden se particiona por este campo. |
| `title` / `description` / `due_date` | String(150) / Text / Date | validaciones Inc.1 | Inc.1 | Sin cambios. |
| `status` | String(20) | `pending` \| `in_progress` \| `completed`; default `pending` | Inc.1 | Transiciones Inc.1 (+ `/reopen` Inc.2); la acción rápida usa salto directo pendiente→completada (aclaración 2026-10-11). |
| **`sort_order`** | **Integer** | **NOT NULL, DEFAULT 0** | **NUEVO Inc.5** | **Posición del propietario dentro de una vista; denso 0..N-1 tras cada reordenamiento. Migración + backfill (R-05).** |
| `is_deleted` / `deleted_at` | Boolean / DateTime | soft delete Inc.2 | Inc.2 | Las eliminadas no participan en el orden visible. |
| `created_at` / `updated_at` | DateTime UTC | — | Inc.1 | `created_at` (+`id` de desempate) fija el backfill inicial. |
| `priority`, `assignee`, `category` | segúnincs. 3–4 | — | Incs. 3–4 | Sin cambios; la vista por defecto del listado pasa a ordenar por `sort_order`. |

**Orden de presentación**: `ORDER BY sort_order ASC, id ASC` dentro del conjunto del usuario y filtro activo. El orden manual aplica por vista filtrada (aclaración 2026-10-11): el servicio renumera densamente solo las tareas de la vista enviada; las tareas del usuario fuera de esa vista conservan su `sort_order`.

**Reglas de validación** (servidor, Principio VII):
- Todo id del lote existe, está vivo (`is_deleted=False`) y pertenece a `session['user_id']`; si uno falla, lote íntegro rechazado (`404` neutro).
- Sin duplicados ni ausencias respecto a la vista declarada (`400 ORDER_INCOMPLETE` / `ORDER_DUPLICATE`).
- `status` de entrada en `/status` limitado a transiciones Inc.1; `completed → *` solo vía `/reopen`.

**Regla de creación**: tarea nueva → `sort_order = max(propietario)+1` (al final; aclaración 2026-10-11). Las completadas conservan su posición (sin reubicación automática).

## 2. Orden personal del listado (derivado, no tabla)

Secuencia `Task.id` del usuario ordenada por `sort_order` dentro de una vista; se conserva entre sesiones al estar materializada en la columna. Sin tabla ni recurso compartido nuevo: el paralelismo entre usuarios es disjunto por `user_id` (R-04).

## 3. Registro de auditoría (existente, un uso nuevo)

Cada `POST /tasks/reorder` aceptado emite un registro por persistencia (aclaración 2026-10-11) con `actor_id` (sesión), `action = TASK_ORDER_CHANGED`, `entity_id` (lote: ids reordenados o usuario), `timestamp` ISO-8601 UTC. `STATUS_CHANGED` (HU-15) sigue el camino existente sin cambios.

## 4. Transiciones relevantes

- `pending → completed`, `in_progress → completed` vía `POST /tasks/<id>/status` (salto directo, HU-15).
- Reordenamiento: permutación de `sort_order` dentro de la vista; no cambia `status` ni ningún otro campo.
