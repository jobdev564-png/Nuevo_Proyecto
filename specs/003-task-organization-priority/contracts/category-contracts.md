# Contratos de Endpoints: Gestión de Categorías (HU-08)

**Feature**: 003-task-organization-priority  
**Módulo**: `src/taskcontrol/routes/categories.py` (Blueprint: `categories_bp`, url_prefix: `/categories`)  

Todos los endpoints requieren autenticación activa mediante sesión de Flask (`session['user_id']`). En caso de no estar autenticado, las peticiones HTML redirigen a `/auth/login` y las peticiones JSON devuelven HTTP `401 Unauthorized`.

---

## 1. Listar Categorías

Permite al usuario autenticado consultar la lista completa de sus categorías para gestión o selección en formularios.

- **Ruta**: `/categories/`
- **Método**: `GET`
- **Autenticación**: Obligatoria (`@login_required`)

### Parámetros de Solicitud:
- Ninguno.

### Respuestas:

#### HTML (Renderizado Jinja2: `categories/index.html`):
- **Código**: `200 OK`
- **Contexto**:
  - `categories`: Lista de objetos `Category` del usuario autenticado ordenados por `name ASC`.

#### JSON (si `Accept: application/json`):
- **Código**: `200 OK`
- **Cuerpo**:
  ```json
  [
    {
      "id": 1,
      "user_id": 10,
      "name": "Trabajo",
      "description": "Proyectos laborales y entregables",
      "created_at": "2026-10-01T14:30:00Z"
    },
    {
      "id": 2,
      "user_id": 10,
      "name": "Personal",
      "description": null,
      "created_at": "2026-10-01T15:00:00Z"
    }
  ]
  ```

---

## 2. Crear Categoría

Crea una nueva categoría asociada al usuario en sesión.

- **Ruta**: `/categories/`
- **Método**: `POST`
- **Autenticación**: Obligatoria (`@login_required`)

### Payload de Entrada (Formulario o JSON):
| Campo | Tipo | Obligatorio | Regla de Validación |
|---|---|---|---|
| `name` | `string` | Sí | Longitud entre 1 y 50 caracteres. No puede estar vacío ni contener solo espacios. Único por usuario. |
| `description` | `string` | No | Texto descriptivo opcional. |

### Respuestas:

#### Éxito (HTML):
- **Código**: `302 Found` (Redirección a `/categories/` o `/tasks/` con flash message de éxito).

#### Éxito (JSON):
- **Código**: `201 Created`
- **Cuerpo**:
  ```json
  {
    "id": 3,
    "user_id": 10,
    "name": "Estudio",
    "description": "Cursos y lecturas técnicas",
    "created_at": "2026-10-01T18:00:00Z"
  }
  ```

#### Errores:
- **400 Bad Request** (Nombre vacío o > 50 caracteres):
  ```json
  {
    "error": "El nombre de la categoría es obligatorio y debe tener como máximo 50 caracteres."
  }
  ```
- **409 Conflict** (Nombre duplicado para el mismo usuario):
  ```json
  {
    "error": "Ya existe una categoría con ese nombre en su cuenta."
  }
  ```

---

## 3. Eliminar Categoría

Elimina una categoría propia y desvincula automáticamente todas las tareas asociadas (dejándolas con `category_id = null`). **Bajo ninguna circunstancia se eliminan tareas**.

- **Ruta**: `/categories/<int:category_id>/delete`
- **Método**: `POST` (o `DELETE /categories/<int:category_id>` en API REST)
- **Autenticación**: Obligatoria (`@login_required`)

### Parámetros de Ruta:
- `category_id`: Identificador de la categoría a eliminar.

### Respuestas:

#### Éxito (HTML):
- **Código**: `302 Found` (Redirección a `/categories/` con mensaje flash: *"Categoría eliminada. Las tareas asociadas ahora están sin categoría."*).

#### Éxito (JSON):
- **Código**: `200 OK`
- **Cuerpo**:
  ```json
  {
    "message": "Categoría eliminada exitosamente. Las tareas asociadas fueron desvinculadas.",
    "deleted_category_id": 3,
    "unlinked_tasks": 5
  }
  ```

#### Errores:
- **404 Not Found** (La categoría no existe o pertenece a otro usuario):
  ```json
  {
    "error": "Categoría no encontrada."
  }
  ```
