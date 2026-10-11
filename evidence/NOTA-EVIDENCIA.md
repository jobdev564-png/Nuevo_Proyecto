# Evidencia test-first — pytest por incremento

Logs de `pytest -v` que demuestran el estado final en verde de cada
incremento y el ciclo test-first (rojo → verde) del incremento 5.

## Declaración de alcance (honestidad de la evidencia)

- **Incrementos 1–4**: fueron implementados en sesiones anteriores a la
  del agente actual. **No existen logs del estado rojo intermedio** de
  esos incrementos (el agente no los escribió ni los observó). Los logs
  `*-verde.log` prueban el estado final en verde, agrupados por
  incremento según su cobertura principal.
- **Incremento 5**: el agente sí aplicó Red-Green-Refactor en vivo.
  `pytest-inc5-rojo.log` reproduce el rojo de forma verificable:
  pruebas nuevas del incremento 5 ejecutadas sobre el código del commit
  previo (`4ba6b11`, worktree temporal, luego eliminado). Las mismas
  pruebas en el código actual están en `pytest-inc5-verde.log` (13/13).

## Archivos

| Log | Incremento | Resultado |
|-----|------------|-----------|
| `pytest-inc1-verde.log` | 1 — auth y usuarios (`test_user_service`, `test_auth_routes`) | 13 passed |
| `pytest-inc1-core-verde.log` | 1 — núcleo tareas (`test_task_service`, `test_task_routes`, archivo completo) | 51 passed |
| `pytest-inc2-verde.log` | 2 — ciclo de vida y recuperación (reopen, soft-delete, password-reset) | 34 passed |
| `pytest-inc3-verde.log` | 3 — organización (categorías, prioridades) | 14 passed |
| `pytest-inc4-verde.log` | 4 — asignación y notificaciones | 37 passed |
| `pytest-inc5-verde.log` | 5 — HU-15/HU-16, 13 pruebas nuevas sobre código actual | 13 passed |
| `pytest-inc5-rojo.log` | 5 — las mismas 13 pruebas sobre código `4ba6b11` (sin incremento 5) | **9 failed, 4 passed** |

Total suite completa: **149 passed** (verificado con `pytest` sobre `tests/`).

## Lectura del rojo (incremento 5)

- Fallan las 9 pruebas de comportamiento genuinamente nuevo:
  `AttributeError: 'Task' object has no attribute 'sort_order'`,
  `type object 'TaskService' has no attribute 'reorder_tasks'`,
  y 404 en `POST /tasks/reorder` (ruta inexistente).
- Pasan 4 pruebas de contrato reutilizado (HU-15 usa el endpoint de
  estado del incremento 1): salto directo `pending→completed`,
  contrato fetch y 404 neutro. Para comportamiento preexistente no hay
  rojo posible; esas 4 son pruebas de regresión, no de código nuevo.
- En la sesión en vivo se observó el mismo rojo antes de implementar:
  2 fallos de fundación (T008) y 7 fallos de reordenamiento
  (T017/T018/T019), todos en verde tras la implementación.
