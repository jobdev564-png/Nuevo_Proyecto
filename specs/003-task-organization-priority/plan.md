# Implementation Plan: 003-task-organization-priority

**Branch**: `003-task-organization-priority` | **Date**: 2026-10-01 | **Spec**: [spec.md](file:///C:/Users/SALAS/Documents/Nuevo_Proyecto/specs/003-task-organization-priority/spec.md)

**Input**: Feature specification from `/specs/003-task-organization-priority/spec.md`

---

## Summary

Implementar el tercer incremento funcional de **TaskControl**: organización y priorización de tareas (`HU-07`, `HU-08`, `HU-09`).
El alcance técnico abarca:
1. **Prioridad de tareas (`HU-07`)**: Incorporar niveles de prioridad (`high`, `medium`, `low`) con valor por defecto obligatorio (`medium`), soporte para ordenamiento jerárquico determinista en listados y modificación en cualquier momento por el usuario propietario.
2. **Categorías o proyectos (`HU-08`)**: Introducir la entidad `Category` con separación estricta en 4 capas (Modelo `Category` -> `CategoryService` -> Blueprint `/categories` -> Vistas Jinja2), garantizando la regla no negociable de **desvinculación segura (`ON DELETE SET NULL`)**: eliminar una categoría jamás elimina en cascada las tareas asociadas.
3. **Indicación de tareas vencidas (`HU-09`)**: Resolver el cálculo del indicador `is_overdue` exclusivamente en el backend (servidor UTC), entregándolo como campo derivado no persistido en el contrato de datos, excluyendo de forma terminante a las tareas completadas, sin fecha límite o eliminadas lógicamente.
4. **Migración segura (Principio VI)**: Modificar el esquema relacional con Flask-Migrate asegurando que todas las tareas preexistentes adquieran la prioridad por defecto `'medium'` sin interrupción del servicio ni inconsistencias.
5. **Pruebas bloqueantes (Principio IV)**: Validación test-first en la capa de servicios para ordenamiento, desvinculación sin borrado en cascada y cálculo estricto de vencimiento.

---

## Technical Context

**Language/Version**: Python 3.11+  
**Primary Dependencies**: Flask 3.x, Flask-SQLAlchemy, Flask-Migrate (Alembic), Jinja2  
**Storage**: Base de datos relacional SQLite (desarrollo y pruebas locales) / PostgreSQL-compatible  
**Testing**: pytest (pytest-flask)  
**Target Platform**: Linux / Windows / macOS server (proceso monolítico único)  
**Project Type**: Monolito web (Jinja2 renderizado en servidor + JavaScript vanilla para interactividad ligera)  
**Performance Goals**: Tiempo de respuesta < 100ms para listado y ordenamiento de hasta 500 tareas por usuario; < 50ms para operaciones CRUD de categorías  
**Constraints**:
- Prohibición estricta de microservicios o colas asíncronas externas (Principio I).
- Separación rigurosa en 4 capas: rutas nunca consultan modelos directamente, delegan siempre en servicios (Principio II).
- Contratos explícitos entre backend y frontend documentados previamente (Principio III).
- TDD obligatorio y bloqueante en la capa de servicios para toda regla de negocio (Principio IV).
- Simplicidad YAGNI: relación 1 a N simple, sin M:N innecesario (Principio V).
- Esquema versionado exclusivamente con Flask-Migrate (Principio VI).
- Validación en backend y aislamiento total por `user_id` autenticado (Principio VII).
- Auditoría estructurada inmutable de cada mutación en `AuditLog` (Principio VIII).  
**Scale/Scope**: Incremento 3 (3 Historias de Usuario: HU-07, HU-08, HU-09) construyendo sobre los Incrementos 1 y 2.

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio Constitucional | Estado | Justificación / Mecanismo de Cumplimiento |
|---|:---:|---|
| **I. Monolito por diseño** | **PASS** | Mantiene un único proceso web en ejecución, un único repositorio y una única base de datos relacional. Sin microservicios, lambdas ni colas de mensajería externas. |
| **II. Separación de responsabilidades** | **PASS** | `Category` se introduce como entidad independiente en `models/category.py`, operada exclusivamente mediante `CategoryService` y expuesta por el blueprint `routes/categories.py`. Las rutas de tareas (`routes/tasks.py`) delegan en `TaskService`. Ningún blueprint ejecuta consultas SQL u ORM directas. |
| **III. Contrato explícito** | **PASS** | Los endpoints de categorías y tareas extendidas están formalizados en `specs/003-task-organization-priority/contracts/`. El cálculo de vencimiento (`is_overdue`) se entrega resuelto por el backend como parte del contrato, prohibiendo cálculos de fechas en el JavaScript del cliente. |
| **IV. Test-first en lógica de negocio** | **PASS** | Se definen pruebas unitarias y de servicios bloqueantes previas al código de producción: ordenamiento por prioridad, desvinculación `SET NULL` sin borrado en cascada y cálculo estricto de `is_overdue` (excluyendo tareas completadas). |
| **V. Simplicidad (YAGNI)** | **PASS** | Se implementa una relación 1 a N directa (una tarea pertenece a 0 o 1 categoría), evitando esquemas complejos de etiquetas multi-tag o taxonomías jerárquicas no solicitadas. `is_overdue` se calcula en tiempo de ejecución sin introducir jobs por lotes ni columnas persistidas redundantes. |
| **VI. Integridad de datos y migraciones** | **PASS** | Todo cambio estructural se realiza mediante una migración de Alembic con `batch_alter_table` y `server_default='medium'`, asegurando que las tareas existentes conserven su integridad. |
| **VII. Seguridad por defecto** | **PASS** | Verificación de `@login_required` en cada ruta. Validación en el backend de que cualquier categoría asignada a una tarea pertenezca al mismo `user_id` del propietario para impedir vulnerabilidades IDOR. |
| **VIII. Observabilidad mínima viable** | **PASS** | Se auditan todas las nuevas mutaciones con los campos obligatorios (`actor_id`, `action`, `entity_id`, `timestamp` UTC): `CATEGORY_CREATED`, `CATEGORY_DELETED`, `TASK_PRIORITY_CHANGED`, `TASK_CATEGORY_CHANGED`. |

---

## Project Structure

### Documentation (this feature)

```text
specs/003-task-organization-priority/
├── spec.md              # Especificación funcional validada
├── plan.md              # Este plan técnico de implementación
├── research.md          # Investigación técnica y decisiones arquitectónicas (Fase 0)
├── data-model.md        # Esquema de datos, ERD y reglas de integridad (Fase 1)
├── quickstart.md        # Guía de verificación y pruebas E2E (Fase 1)
├── contracts/           # Contratos explícitos de endpoints HTTP (Fase 1)
│   ├── category-contracts.md
│   └── task-organization-contracts.md
└── checklists/
    └── requirements.md  # Checklist de calidad de requerimientos
```

### Source Code (repository root)

```text
src/
└── taskcontrol/
    ├── __init__.py           # Application Factory: registro de blueprint categories_bp
    ├── config.py             # Configuración central
    ├── extensions.py         # db (SQLAlchemy), migrate (Flask-Migrate)
    │
    ├── models/               # Capa 4: Persistencia y datos
    │   ├── __init__.py       # Exporta User, Task, Category, AuditLog
    │   ├── user.py           # Modelo User
    │   ├── task.py           # Modelo Task extendido (priority, category_id, is_overdue)
    │   ├── category.py       # NUEVO: Modelo Category (id, user_id, name, description, created_at)
    │   └── audit.py          # Modelo AuditLog
    │
    ├── services/             # Capa 3: Lógica de negocio (Test-First bloqueante)
    │   ├── __init__.py
    │   ├── task_service.py   # Extendido: validación de prioridad, ordenamiento CASE, asignación de categoría
    │   ├── category_service.py # NUEVO: CRUD de categorías, unicidad por usuario, desvinculación de tareas
    │   ├── user_service.py   # Servicio de usuarios preexistente
    │   └── audit_service.py  # Emisión de eventos estructurados de auditoría
    │
    ├── routes/               # Capa 2: Blueprints HTTP (Transporte y sesión)
    │   ├── __init__.py
    │   ├── tasks.py          # Extendido: filtros combinados status/category, sort_by=priority, endpoints rápidos
    │   ├── categories.py     # NUEVO: Blueprint /categories (listar, crear, eliminar)
    │   ├── auth.py           # Blueprint de autenticación
    │   └── main.py           # Blueprint de navegación principal
    │
    ├── templates/            # Capa 1: Presentación Jinja2
    │   ├── base.html         # Navbar extendido con enlace a "Categorías"
    │   ├── categories/       # NUEVO: Directorio de plantillas de categorías
    │   │   └── index.html    # Listado y formulario modal de creación/eliminación de categorías
    │   └── tasks/
    │       ├── index.html    # Extendido: badges de prioridad, badge de vencida, selector de orden y categorías
    │       └── edit.html     # Extendido: campos para editar prioridad y categoría
    │
    └── static/
        ├── css/
        │   └── styles.css    # Estilos de badges de prioridad (alta/media/baja) y badge de vencida
        └── js/
            └── main.js       # Comportamiento ligero de interfaz

tests/
├── conftest.py               # Fixtures comunes
├── services/                 # Pruebas de dominio bloqueantes (Principio IV)
│   ├── test_task_service.py  # Extendido: orden por prioridad, asignación categoría, is_overdue
│   └── test_category_service.py # NUEVO: unicidad por usuario, eliminación con SET NULL de tareas
└── functional/               # Pruebas de integración HTTP
    ├── test_task_routes.py   # Extendido: parámetros query category_id y sort_by
    └── test_category_routes.py # NUEVO: endpoints de categorías y validación de sesión
```

---

## Complexity Tracking

> **Estado**: Sin violaciones constitucionales. Todas las decisiones arquitectónicas respetan el principio YAGNI y la arquitectura monolítica.

| Elemento | Justificación Técnica | Alternativa Más Simple Rechazada |
|---|---|---|
| Nueva entidad `Category` y servicio `CategoryService` | Requerido por el Principio II para encapsular las reglas de agrupación y desvinculación sin sobrecargar `TaskService`. | Gestionar categorías como cadenas de texto plano en `Task.category` rechazada porque no permite listar proyectos vacíos, renombrarlos ni controlar su ciclo de vida con integridad referencial. |
| Propiedad calculada `is_overdue` | Exigida por HU-09 y Principio III para calcularse en backend sin depender del huso horario del cliente. | Guardar `is_overdue` como columna persistida rechazada porque exigiría workers en segundo plano para actualizarla diariamente, introduciendo desincronización y complejidad operativa. |
| Desvinculación en BD (`ON DELETE SET NULL`) + Desvinculación en Servicio | Proporciona defensa en profundidad garantizando que ninguna tarea se borre en cascada aun en configuraciones de SQLite con claves foráneas deshabilitadas. | Confiar únicamente en la base de datos rechazada para evitar comportamientos inconsistentes entre motores de prueba y producción. |

---

## Detailed Implementation & Design Decisions

### 1. Extensión del Modelo Task (HU-07)
- **Atributo `priority`**:
  - `priority = db.Column(db.String(10), nullable=False, default="medium", server_default="medium")`
  - Valores admitidos en validación de servicio: `"high"`, `"medium"`, `"low"`.
  - Mapeo de presentación: `high` -> "Alta", `medium` -> "Media", `low` -> "Baja".
- **Relación con `Category`**:
  - `category_id = db.Column(db.Integer, db.ForeignKey("categories.id", ondelete="SET NULL"), nullable=True, index=True)`
  - `category = db.relationship("Category", backref=db.backref("tasks", lazy="dynamic"))`
  - Campo opcional: permite tareas sin categoría (`category_id = None`).

### 2. Modelo de Datos de Category (HU-08)
- Entidad `Category` (`categories`):
  - `id`: `INTEGER PRIMARY KEY AUTOINCREMENT`
  - `user_id`: `INTEGER NOT NULL, FOREIGN KEY (users.id) ON DELETE CASCADE, INDEXED`
  - `name`: `VARCHAR(50) NOT NULL` (1 a 50 caracteres, no vacío tras strip)
  - `description`: `TEXT NULLABLE`
  - `created_at`: `DATETIME NOT NULL, DEFAULT UTC`
  - `UniqueConstraint("user_id", "name", name="uq_user_category_name")`
- **Regla no negociable de desvinculación al eliminar categoría**:
  - A nivel DDL de base de datos: Clave foránea con `ON DELETE SET NULL`.
  - A nivel de servicio (`CategoryService.delete_category`): Ejecución explícita de `Task.query.filter_by(category_id=category_id).update({Task.category_id: None})` antes de la eliminación del registro de la categoría, garantizando que el 100% de las tareas queden preservadas en estado "sin categoría" y emitiendo auditoría `CATEGORY_DELETED`.

### 3. Contrato de Endpoints y Extensión del Listado Existente
- **`GET /tasks/` extendido**:
  - Soporta `status` (`pending`, `in_progress`, `completed`), `category_id` (entero o `"none"`), `sort_by` (`"priority"`), `order` (`"desc"` o `"asc"`).
  - Los filtros son acumulativos (AND). No se rompe la funcionalidad previa cuando los nuevos parámetros no se envían.
  - Ordenamiento por prioridad en SQL:
    ```python
    priority_order = db.case({"high": 1, "medium": 2, "low": 3}, value=Task.priority)
    query = query.order_by(priority_order.asc() if order == "asc" else priority_order.desc(), Task.due_date.asc(), Task.id.desc())
    ```
- **Nuevos endpoints**:
  - `GET /categories/`: Listado de categorías del usuario.
  - `POST /categories/`: Creación de categoría con validación de nombre y unicidad por usuario.
  - `POST /categories/<int:category_id>/delete`: Eliminación de categoría con desvinculación de tareas.
  - `POST /tasks/<int:task_id>/priority`: Actualización puntual de prioridad con auditoría `TASK_PRIORITY_CHANGED`.
  - `POST /tasks/<int:task_id>/category`: Actualización puntual de categoría con auditoría `TASK_CATEGORY_CHANGED`.

### 4. Cálculo del Indicador de Tareas Vencidas (`is_overdue`)
- Implementado como propiedad `@property` en `Task` o en la capa de servicios:
  ```python
  @property
  def is_overdue(self) -> bool:
      if self.status == "completed" or getattr(self, "is_deleted", False):
          return False
      if not self.due_date:
          return False
      return self.due_date < datetime.now(timezone.utc).date()
  ```
- **Reglas estrictas**:
  - Si la tarea está completada o eliminada: `is_overdue = False`.
  - Si no tiene fecha límite: `is_overdue = False`.
  - Si la fecha límite es hoy o futura: `is_overdue = False`.
  - Solo si la fecha límite ya pasó (`due_date < today_utc`) y la tarea no está completada: `is_overdue = True`.
- Expuesto directamente en la respuesta del listado y renderizado por Jinja2; **prohibido calcular en JavaScript del cliente**.

### 5. Plan de Migraciones (Principio VI)
- Script de migración con Flask-Migrate / Alembic:
  1. Crear tabla `categories` con sus campos, índice en `user_id` y restricción de unicidad `uq_user_category_name`.
  2. Modificar tabla `tasks` mediante `op.batch_alter_table('tasks')`:
     - Agregar columna `priority`: `VARCHAR(10)`, `nullable=False`, `server_default='medium'`.
     - Agregar columna `category_id`: `INTEGER`, `nullable=True`.
     - Crear índice `ix_tasks_category_id`.
     - Crear clave foránea con `ondelete='SET NULL'`.
  - **Preservación de datos**: Al definir `server_default='medium'`, todas las tareas creadas en incrementos anteriores adquieren automáticamente el valor `'medium'` de manera determinista.

### 6. Pruebas Automatizadas Bloqueantes (Principio IV)
Las siguientes pruebas en la capa de servicios son obligatorias y bloqueantes antes de habilitar rutas e interfaces:
1. **Ordenamiento por prioridad**:
   - `test_tasks_ordered_by_priority_desc`: Valida orden `high` -> `medium` -> `low`.
   - `test_tasks_ordered_by_priority_asc`: Valida orden `low` -> `medium` -> `high`.
   - `test_tasks_order_with_status_filter`: Valida combinación de orden por prioridad con filtro por estado.
   - `test_default_priority_is_medium`: Valida que omitir prioridad en la creación asigne `'medium'`.
   - `test_invalid_priority_rejected`: Valida que valores fuera de `high`, `medium`, `low` fallen.
2. **Eliminación de categoría sin pérdida de tareas**:
   - `test_delete_category_unlinks_tasks_and_does_not_delete_them`: Comprueba que tras eliminar una categoría con tareas vinculadas, las tareas sigan existiendo intactas con `category_id is None`.
   - `test_category_name_unique_per_user`: Comprueba rechazo de categorías duplicadas para el mismo usuario y aceptación de nombres iguales entre usuarios distintos.
   - `test_cannot_assign_foreign_category`: Comprueba rechazo al intentar asociar una categoría ajena a una tarea propia.
3. **Cálculo de vencimiento (`is_overdue`)**:
   - `test_overdue_when_due_date_passed_and_pending`: Fecha de ayer + `pending` -> `True`.
   - `test_never_overdue_when_completed`: **BLOQUEANTE**: Fecha de ayer + `completed` -> `False`.
   - `test_never_overdue_when_today_or_future`: Fecha de hoy o mañana -> `False`.
   - `test_never_overdue_when_no_due_date`: Sin fecha límite -> `False`.
