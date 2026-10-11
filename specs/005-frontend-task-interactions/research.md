# Research: Interacción fluida del listado de tareas (Incremento 5)

**Fecha**: 2026-10-11 | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

Todos los puntos corresponden a los 6 solicitados. Sin `NEEDS CLARIFICATION` abiertos: el contexto técnico quedó resuelto con spec + clarificaciones 2026-10-11 + contratos de incrementos anteriores.

## R-01. Estrategia JS sin recarga (HU-15): fetch nativo + reversión optimista

- **Decision**: `fetch` nativo contra el endpoint existente `POST /tasks/<id>/status` con cuerpo JSON `{"status": "completed"}` y cabecera `Accept: application/json`; actualización optimista de la fila con instantánea previa (`previousStatus`, clases, posición en filtro) y reversión obligatoria ante cualquier fallo; cero frameworks o librerías nuevas (el módulo vive en `src/taskcontrol/static/js/main.js`).
- **Rationale**: El contrato existente ya acepta JSON y el salto directo pendiente→completada (Inc.1: desde `pending` hacia `in_progress` o `completed`), por lo que la aclaración "salto directo" no exige cambio backend. La reversión cubre FR-003/FR-004 (cero estados falsos): ante `!response.ok`, excepción de red o `status: error`, se restaura la instantánea y se muestra mensaje no técnico (sesión expirada → aviso de re-login). El doble clic se neutraliza deshabilitando el control hasta la respuesta y aceptando solo la última confirmación.
- **Alternatives considered**: Re-render SSR tras mutación (rechazado: viola FR-001, recarga). Librería reactiva ligera (rechazada: YAGNI, Principio V; el caso es un formulario por fila, no estado global). `XMLHttpRequest` (rechazado: API obsoleta frente a Fetch, ya exigido por la constitución).
- **Por qué no hay framework adicional**: la constitución lo prohíbe sin enmienda y el problema no la justifica — dos interacciones acotadas (PATCH visual por fila + reordenar lista) sin enrutado, sin estado compartido ni tiempo real. Vanilla ES6+ es la opción por defecto del stack y mantiene el JS auditable en un solo módulo.

## R-02. Técnica de drag-and-drop (HU-16): DnD nativo + botones de teclado

- **Decision**: API nativa HTML5 Drag-and-Drop (`draggable`, `dragstart/dragover/drop/dragend`) sobre las filas (`data-task-id`, `data-sort-order`), sin librerías; como alternativa accesible (aclaración 2026-10-11), botones subir/bajar por fila operables por teclado que reutilizan la misma rutina de persistencia.
- **Rationale**: Cero dependencias, cero peso, soporte universal con puntero en navegadores modernos; el evento `drop` entrega el nuevo orden visible que se persiste inmediatamente (FR-008). Los botones cubren teclado/lector de pantalla y la degradación sin DnD (FR-015: el flujo base con recarga sigue disponible).
- **Alternatives considered**: SortableJS / Dragula (~10–40 KB, más gestos táctiles) — rechazadas por YAGNI (Principio V): el alcance excluye gestos táctiles avanzados y el DnD nativo basta para puntero + botones. Pointer Events con arrastre manual — rechazado: reimplementa lo que el navegador ya da (más código propio, más riesgo).
- **Límite "sin framework SPA pesado"**: la decisión queda órdenes de magnitud por debajo — ni framework ni librería, solo APIs del navegador ya asumidas por la constitución (Fetch/DnD). Nada que enmendar.

## R-03. Cambio backend y contrato del orden (único elemento nuevo)

- **Decision**: Un campo persistente `Task.sort_order` (entero, no nulo) + un endpoint mínimo nuevo `POST /tasks/reorder` que recibe la lista ordenada de ids de la vista actual y la persiste atómicamente. Contrato formal en `contracts/order-contracts.md` (ruta, método, payloads, códigos). HU-15 no crea ni extiende nada: reutiliza `POST /tasks/<id>/status` tal cual.
- **Rationale**: El orden es estado que debe sobrevivir a la recarga (FR-008/FR-011); sin columna no hay dónde guardarlo. El endpoint de estado no puede asumir esta escritura sin pervertir su semántica (una transición ≠ una permutación), y el spec exige contrato explícito para toda interacción dinámica (Principio III): un endpoint mínimo y documentado es la opción simple y honesta (Principio V) frente a sobrecargar `/status` con parámetros implícitos.
- **Alternatives considered**: Reutilizar `/status` con campo extra de posición (rechazado: acopla dos operaciones, rompe semántica del contrato Inc.1, validación ambigua). Extender `POST /tasks/<id>/edit` (rechazado: es edición por tarea, no permutación; N peticiones por arrastre). Persistir solo en `localStorage` (rechazado: viola FR-008, el orden debe sobrevivir en servidor y entre dispositivos).
- **Desviación del spec declarada**: el spec decía "ningún endpoint nuevo"; se documenta aquí la excepción mínima y su motivo. Todo lo demás del spec se respeta (ninguna otra operación nueva).

## R-04. Paralelismo entre usuarios: aislamiento por propiedad + lote atómico

- **Decision**: El orden es por usuario y por vista (aclaraciones 2026-10-11): no existe orden global compartido, luego dos usuarios reordenando en paralelo operan sobre conjuntos disjuntos (`tasks.user_id`). Cada lote `POST /tasks/reorder` valida en servidor que **todos** los ids pertenecen al solicitante antes de escribir nada; cualquier id ajeno/inexistente/eliminado aborta el lote completo con `404` neutro (sin revelar propiedad), y la escritura es una transacción atómica.
- **Rationale**: Al no haber recurso compartido no hay condición de carrera entre usuarios (Principio VII satisfecho con la misma regla que los endpoints anteriores: `session['user_id']` + filtro por propietario). La validación total-previa evita persistencias parciales corruptas; el `404` neutro evita enumeración de tareas ajenas.
- **Alternatives considered**: Bloqueos pesimistas / versionado optimista global (rechazados: YAGNI — no hay recurso compartido que proteger). Escritura parcial "lo válido sí" (rechazada: deja el orden a medias y contradice la reversión FR-010).

## R-05. Migración del campo de orden (Principio VI)

- **Decision**: Migración Flask-Migrate/Alembic versionada: `ALTER TABLE tasks ADD COLUMN sort_order INTEGER NOT NULL DEFAULT 0` (o equivalente del backend), seguida de backfill por usuario según orden de creación (`created_at`, desempate `id`) con valores densos 0..N-1, y default de aplicación para tareas nuevas = `max(sort_order)+1` del propietario (regla "nuevas al final", aclaración 2026-10-11). Prohibida cualquier alteración manual.
- **Rationale**: `DEFAULT 0` hace la migración segura sobre datos existentes; el backfill restaura un orden determinista coherente con el historial (incrementos 1–4 no conocían el campo) sin romper listados actuales; el default por propietario preserva la regla aclarada sin intervención del cliente.
- **Alternatives considered**: Columna anulable sin backfill (rechazada: `NULL` rompe `ORDER BY` determinista y exige lógica especial permanente). Reutilizar `updated_at`/`id` como orden implícito (rechazado: muta con ediciones y no representa intención del usuario).

## R-06. Pruebas bloqueantes (qué es automático, qué es manual)

- **Decision**: Bloqueantes automatizadas con `pytest` (Red-Green-Refactor, Principio IV): (a) servicio — persistir un orden nuevo actualiza **todas** las tareas afectadas con valores densos y conserva las no incluidas; lote con id ajeno rechaza íntegro sin escribir nada; tarea nueva queda al final; (b) ruta — `POST /tasks/reorder` exige sesión (`401`), propiedad (`404` neutro), payload válido (`400`), responde envoltorio `{status,…}` y emite auditoría; (c) regresión — `POST /tasks/<id>/status` vía fetch sigue aceptando salto directo. **Sin infraestructura de pruebas frontend en el proyecto** (constatado: sin `package.json` ni runner JS; solo `pytest`): la reversión visual ante error de backend **se verifica con protocolo manual bloqueante** en `quickstart.md` (Q-3/Q-4), ejecutado antes de dar por cerradas HU-15/HU-16. Se declara explícitamente, según lo solicitado, en lugar de simular cobertura automática inexistente.
- **Rationale**: El riesgo de dominio (orden corrupto, fuga entre usuarios) queda cubierto por pruebas de servicio/ruta; el riesgo de UI (estado falso) queda cubierto por el protocolo manual reproducible, proporcional al stack del proyecto (Principio V: no se monta un harness JS solo para este incremento).
- **Alternatives considered**: Introducir Vitest/Playwright solo para este incremento (rechazado: YAGNI + contradice entorno unificado de un comando; se reevaluaría si el JS sigue creciendo). Marcar HU-15/HU-16 como hechas solo con tests backend (rechazado: dejaría FR-003/FR-004 sin verificación).
