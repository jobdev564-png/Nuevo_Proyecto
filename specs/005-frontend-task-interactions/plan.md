# Implementation Plan: Interacción fluida del listado de tareas (Incremento 5)

**Branch**: `incremeto5` | **Date**: 2026-10-11 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/005-frontend-task-interactions/spec.md` (HU-15, HU-16; 5 clarificaciones 2026-10-11) + directrices del solicitante (6 puntos).

## Summary

Incremento 5 y final de TaskControl: dos mejoras de interacción sobre el listado existente, sin alterar el dominio central. (1) HU-15 — completar sin recarga mediante `fetch` nativo contra el contrato existente `POST /tasks/<id>/status`, con actualización optimista y reversión garantizada ante fallo. (2) HU-16 — reordenar con Drag-and-Drop nativo (+ botones subir/bajar por teclado) y persistencia inmediata del orden por vista filtrada mediante un único endpoint mínimo nuevo `POST /tasks/reorder` y un único campo nuevo `Task.sort_order` con migración Alembic. Desviación documentada respecto a la frase del spec "no introduce ningún endpoint nuevo": persistir el orden exige una vía de escritura que el endpoint de estado no puede asumir sin pervertir su semántica; se introduce el endpoint mínimo posible, con contrato explícito (Principio III) y sin reutilizaciones implícitas. Ver `research.md` R-03 y `contracts/order-contracts.md`.

## Technical Context

**Language/Version**: Python 3.11+ (backend, constitución) + JavaScript vanilla ES6+ en cliente (restricción de stack).

**Primary Dependencies**: Flask 3.1.3 (único framework web), Flask-SQLAlchemy 3.1.1, Flask-Migrate 4.1.0/Alembic (migraciones), Jinja2 (listado renderizado en servidor), Fetch API + HTML5 Drag-and-Drop API nativas (sin librerías ni frameworks SPA).

**Storage**: Base de datos relacional vía SQLAlchemy; único cambio de esquema: columna `tasks.sort_order` (entero, no nulo, con backfill). Ver `data-model.md`.

**Testing**: `pytest` + `pytest-flask` (bloqueantes a nivel servicio y ruta, ciclo Red-Green-Refactor, Principio IV). Sin infraestructura de pruebas frontend en el proyecto (sin `package.json`, sin runner JS): la reversión visual ante error de backend se verifica con protocolo manual bloqueante documentado en `quickstart.md` (se indica explícitamente, según lo solicitado).

**Target Platform**: Servidor Linux monolítico (`docker compose up` / `run.sh`·`run.ps1`); cliente: navegadores modernos con Fetch y DnD HTML5, con degradación al flujo base con recarga.

**Project Type**: Aplicación web monolítica (Jinja2 SSR + JS modular de interactividad).

**Performance Goals**: Resultado visual de completar/soltar en < 2 s en red normal (SC-004); persistencia de orden inmediata tras soltar (FR-008); 100 % de persistencia de orden tras recarga en prueba de 5 tareas (SC-003); cero estados falsos confirmados en pruebas de fallo (SC-002).

**Constraints**: Sin frameworks SPA (React/Vue/Angular) salvo enmienda — no se introducen (R-01, R-02). Reutilización exclusiva del contrato de estado existente para HU-15 (FR-005). Autorización y validación en servidor en cada endpoint (Principio VII). Auditoría estructurada por mutación, incluida cada persistencia de orden (FR-012 + aclaración 2026-10-11). Migración versionada obligatoria (Principio VI).

**Scale/Scope**: Listados personales por usuario (decenas–cientos de tareas); el orden es por usuario y por vista filtrada (aclaraciones 2026-10-11), sin orden global compartido; dos usuarios reordenando en paralelo no colisionan porque cada lote se valida contra la propiedad y se escribe en transacción atómica por usuario (R-04).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Monolito por diseño**: PASS. Sin microservicios, serverless ni colas. Un proceso Flask + una BD relacional; JS solo como interactividad cliente.
- **II. Separación de capas**: PASS. JS → Blueprints (`routes/tasks.py`) → `TaskService` → modelos SQLAlchemy. Prohibidas consultas ORM desde blueprints y desde JS; el servicio encapsula transición de estado y reordenamiento.
- **III. Contrato explícito**: PASS. HU-15 reutiliza `POST /tasks/<id>/status` documentado (Inc.1). El endpoint mínimo `POST /tasks/reorder` se documenta formalmente en `contracts/order-contracts.md` (ruta, método, payloads, códigos) antes de implementarse.
- **IV. Test-first**: PASS (bloqueante). Servicio: persistencia de orden, propiedad, atomicidad, tarea nueva al final. Rutas: auth, códigos, envoltorio `{status,…}`. Frontend sin runner: protocolo manual bloqueante en `quickstart.md` (excepción declarada, no exención).
- **V. Simplicidad (YAGNI)**: PASS. Cero dependencias nuevas: Fetch y DnD nativos, sin librerías. Único campo (`sort_order`) y único endpoint (`/reorder`); fuera de alcance: edición en línea, creación sin recarga, orden colaborativo, tiempo real.
- **VI. Migraciones**: PASS. Columna vía Flask-Migrate/Alembic con backfill determinista (orden de creación por usuario); prohibidas alteraciones manuales.
- **VII. Seguridad por defecto**: PASS. `login_required` + verificación de propiedad por tarea en cada lote; validación backend de transiciones (salto directo pendiente→completada permitido, reapertura solo vía `/reopen`) y de posiciones; sin validación confiada al cliente; sin secretos en logs.
- **VIII. Observabilidad**: PASS. `STATUS_CHANGED` (existente) + registro por cada persistencia de orden con `actor_id`, `action`, `entity_id`, `timestamp` ISO-8601 UTC (aclaración 2026-10-11).

*Re-evaluación post-Phase 1 (2026-10-11)*: los artefactos confirman los 8 gates. Sin violaciones que justifiquen tabla de Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/005-frontend-task-interactions/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   └── order-contracts.md
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
src/
└── taskcontrol/
    ├── models/
    │   └── task.py            # + sort_order (migración)
    ├── services/
    │   └── task_service.py    # + reorder_tasks() + auditoría
    ├── routes/
    │   └── tasks.py           # + POST /tasks/reorder (tasks_bp)
    ├── templates/
    │   └── tasks/             # listado: data-task-id, data-sort-order, controles
    └── static/
        └── js/
            └── main.js        # completar sin recarga + DnD + subir/bajar (+ tests manuales)

migrations/
└── versions/                  # + migración sort_order con backfill

tests/
├── services/
│   └── test_task_service.py   # tests bloqueantes de reordenamiento
└── functional/
    └── test_task_routes.py    # tests bloqueantes de contrato /reorder + status vía fetch
```

**Structure Decision**: Monolito existente tal cual (Single project). Sin directorios nuevos salvo la migración versionada; el JS vive en `src/taskcontrol/static/js/` (convención del repo, ver `main.js` existente). Los tests siguen la división `services` (dominio, Red-Green-Refactor) / `functional` (contratos HTTP).

## Complexity Tracking

> Sin violaciones constitucionales: tabla no aplicable. La única desviación es respecto a una frase del spec ("ningún endpoint nuevo"), no respecto a la constitución, y queda justificada en `research.md` R-03.
