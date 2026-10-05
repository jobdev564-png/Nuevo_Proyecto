# Contratos de Endpoints: Organización, Priorización y Vencimiento de Tareas (HU-07, HU-08, HU-09)

**Feature**: 003-task-organization-priority  
**Módulo**: `src/taskcontrol/routes/tasks.py` (Blueprint: `tasks_bp`, url_prefix: `/tasks`)  

Todos los endpoints requieren autenticación activa mediante sesión de Flask (`session['user_id']`). En caso de no estar autenticado, las peticiones HTML redirigen a `/auth/login` y las peticiones JSON devuelven HTTP `401 Unauthorized`.

---

## 1. Listado Extendido de Tareas (Filtrado por Estado y Categoría con Orden por Prioridad)

Extiende el endpoint de listado preexistente para permitir filtrar por categoría y ordenar por prioridad sin romper los filtros de estado existentes.

- **Ruta**: `/tasks/`
- **Método**: `GET`
- **Autenticación**: Obligatoria (`@login_required`)

### Parámetros de Consulta (Query Parameters):
| Parámetro | Tipo | Opciones / Formato | Descripción |
|---|---|---|---|
| `status` | `string` | `pending`, `in_progress`, `completed`, o ausente | Filtro por estado existente (HU-02). |
| `category_id` | `string` / `int` | Número entero (ID de categoría), `"none"` o `"uncategorized"`, o ausente | **NUEVO**. Filtra tareas de una categoría específica o aquellas sin categoría. |
| `sort_by` | `string` | `"priority"`, `"due_date"`, `"created_at"` | **NUEVO**. Criterio de ordenamiento. |
| `order` | `string` | `"asc"`, `"desc"` (Default: `"desc"` cuando `sort_by=priority`) | Sentido del orden. En prioridad: `desc` = Alta > Media > Baja; `asc` = Baja > Media > Alta. |

### Respuestas:

#### HTML (Renderizado Jinja2: `tasks/index.html`):
- **Código**: `200 OK`
- **Contexto suministrado a la plantilla**:
  - `tasks`: Lista de objetos `Task` del usuario que satisfacen los filtros y el orden especificado.
  - `categories`: Lista de todas las categorías activas del usuario para poblar el dropdown de filtrado y creación.
  - `current_status`: Estado actualmente filtrado.
  - `current_category_id`: ID de categoría actualmente filtrado.
  - `current_sort_by`: Criterio de orden actual.
  - `current_order`: Sentido de orden actual.
  - Cada elemento en `tasks` expone directamente las propiedades:
    - `.priority`: `"high"`, `"medium"`, `"low"`.
    - `.category`: Objeto `Category` asociado o `None`.
    - `.is_overdue`: Booleano calculado por el servidor (`True` si `due_date < fecha_hoy_utc` y `status != 'completed'`).

#### JSON (si `Accept: application/json`):
- **Código**: `200 OK`
- **Cuerpo**:
  ```json
  [
    {
      "id": 101,
      "user_id": 10,
      "title": "Entregar informe financiero",
      "description": "Consolidar balance trimestral",
      "due_date": "2026-09-28",
      "status": "pending",
      "priority": "high",
      "category_id": 1,
      "category_name": "Trabajo",
      "is_overdue": true,
      "created_at": "2026-09-20T10:00:00Z",
      "updated_at": "2026-09-20T10:00:00Z"
    },
    {
      "id": 102,
      "user_id": 10,
      "title": "Comprar insumos",
      "description": null,
      "due_date": "2026-10-15",
      "status": "pending",
      "priority": "medium",
      "category_id": null,
      "category_name": null,
      "is_overdue": false,
      "created_at": "2026-09-29T11:00:00Z",
      "updated_at": "2026-09-29T11:00:00Z"
    }
  ]
  ```

---

## 2. Modificar Prioridad de una Tarea (HU-07)

Permite al propietario cambiar de forma inmediata la prioridad de una tarea existente.

- **Ruta**: `/tasks/<int:task_id>/priority`
- **Método**: `POST` (o `PATCH /tasks/<int:task_id>/priority` en API)
- **Autenticación**: Obligatoria (`@login_required`)

### Payload de Entrada:
| Campo | Tipo | Obligatorio | Valores Permitidos |
|---|---|---|---|
| `priority` | `string` | Sí | `"high"`, `"medium"`, `"low"` |

### Respuestas:

#### Éxito (HTML):
- **Código**: `302 Found` (Redirección a `/tasks/` con mensaje flash de confirmación).

#### Éxito (JSON):
- **Código**: `200 OK`
- **Cuerpo**:
  ```json
  {
    "id": 101,
    "priority": "high",
    "message": "Prioridad actualizada correctamente."
  }
  ```

#### Errores:
- **400 Bad Request** (Prioridad inválida):
  ```json
  {
    "error": "Prioridad inválida. Debe ser 'high', 'medium' o 'low'."
  }
  ```
- **404 Not Found** (Tarea no existe o pertenece a otro usuario):
  ```json
  {
    "error": "Tarea no encontrada."
  }
  ```

---

## 3. Asignar o Cambiar Categoría de una Tarea (HU-08)

Asocia una tarea a una categoría específica o la desvincula para dejarla sin categoría.

- **Ruta**: `/tasks/<int:task_id>/category`
- **Método**: `POST` (o `PATCH /tasks/<int:task_id>/category`)
- **Autenticación**: Obligatoria (`@login_required`)

### Payload de Entrada:
| Campo | Tipo | Obligatorio | Descripción |
|---|---|---|---|
| `category_id` | `int` o `null` / vacío | No | ID de la categoría a vincular. Si viene vacío o nulo, la tarea queda sin categoría. |

### Respuestas:

#### Éxito (HTML):
- **Código**: `302 Found` (Redirección a `/tasks/`).

#### Éxito (JSON):
- **Código**: `200 OK`
- **Cuerpo**:
  ```json
  {
    "id": 101,
    "category_id": 2,
    "category_name": "Personal",
    "message": "Categoría de la tarea actualizada."
  }
  ```

#### Errores:
- **400 Bad Request** (Categoría no pertenece al usuario autenticado):
  ```json
  {
    "error": "La categoría indicada no existe o no pertenece a su usuario."
  }
  ```
- **404 Not Found** (Tarea inexistente o ajena).

---

## 4. Extensión de Creación y Edición de Tareas

Los endpoints preexistentes de creación (`POST /tasks/create` o `POST /tasks/`) y edición (`POST /tasks/<int:task_id>/edit`) aceptan ahora los campos adicionales opcionales:
- `priority`: Opcional. Si se omite en la creación, se establece por defecto `"medium"`.
- `category_id`: Opcional. Si se omite, se establece `None`. Se valida pertenencia al usuario autenticado.
