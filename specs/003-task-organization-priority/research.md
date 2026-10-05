# Research & Decisions: 003-task-organization-priority

**Feature**: 003-task-organization-priority (Organización y Priorización de Tareas: HU-07, HU-08, HU-09)  
**Date**: 2026-10-01  
**Status**: Completed  

---

## 1. Extensión del Modelo Task y Representación de Prioridades (HU-07)

### Decisión
Extender el modelo `Task` en `src/taskcontrol/models/task.py` agregando la columna:
```python
priority = db.Column(db.String(10), nullable=False, default="medium", server_default="medium")
```
Los valores permitidos son estrictamente tres: `"high"`, `"medium"`, `"low"`.
El valor por defecto es `"medium"` (presentado como "Media" en la capa de presentación).
Para el ordenamiento en SQLAlchemy, se implementará una expresión CASE:
```python
priority_order = db.case(
    {"high": 1, "medium": 2, "low": 3},
    value=Task.priority
)
```
Si el orden es descendente (`desc`), se ordenará por urgencia (`high` -> `medium` -> `low`), aplicando como desempate secundario determinista `Task.due_date.asc()` y `Task.created_at.desc()`.

### Razón de ser
- Garantiza total compatibilidad con SQLite (desarrollo/test) y PostgreSQL (producción), evitando las fricciones habituales de tipos ENUM nativos en SQLite durante migraciones con Alembic.
- La especificación de `server_default="medium"` asegura que la migración pueble automáticamente las tareas ya existentes en la base de datos de incrementos 1 y 2 sin registros nulos ni fallos de restricción.
- La expresión CASE proporciona un ordenamiento lexicográfico controlado en la base de datos relacional sin necesidad de ordenar colecciones en memoria de Python.

### Alternativas Evaluadas y Rechazadas
- **Columna numérica de prioridad (`priority: 1, 2, 3`)**: Rechazada porque expone constantes mágicas en la API/contrato y disminuye la claridad semántica de los modelos.
- **Tipo `db.Enum` nativo**: Rechazado debido a limitaciones conocidas de SQLite al alterar columnas enum con Alembic y para mantener la máxima simplicidad según el Principio V (YAGNI).

---

## 2. Entidad Category y Regla de Desvinculación Segura (HU-08)

### Decisión
Crear una entidad independiente `Category` en `src/taskcontrol/models/category.py` con su correspondiente servicio `CategoryService` en `src/taskcontrol/services/category_service.py` y blueprint en `src/taskcontrol/routes/categories.py`.
Campos del modelo `Category`:
- `id`: Entero autoincremental, clave primaria.
- `user_id`: Entero, clave foránea obligatoria a `users.id`, indexado.
- `name`: String(50), obligatorio, no vacío.
- `description`: Text, opcional.
- `created_at`: DateTime UTC con valor por defecto.
- Restricción de tabla: `UniqueConstraint("user_id", "name", name="uq_user_category_name")`.

En el modelo `Task`, la relación se define mediante:
```python
category_id = db.Column(
    db.Integer,
    db.ForeignKey("categories.id", ondelete="SET NULL"),
    nullable=True,
    index=True
)
category = db.relationship("Category", backref=db.backref("tasks", lazy="dynamic"))
```

**Mecanismo de Desvinculación Segura al Eliminar Categoría**:
1. A nivel de base de datos: Clave foránea con `ondelete="SET NULL"`.
2. A nivel de servicio de dominio (`CategoryService.delete_category`): Antes de eliminar la fila de la categoría, se ejecuta explícitamente:
   ```python
   Task.query.filter_by(category_id=category_id).update({Task.category_id: None})
   db.session.delete(category)
   db.session.commit()
   ```
   Seguido del registro de auditoría `CATEGORY_DELETED`.

### Razón de ser
- Cumple a rajatabla el requisito no negociable de que eliminar una categoría jamás elimine tareas en cascada.
- La desvinculación a nivel de servicio protege contra configuraciones de SQLite donde las claves foráneas no tienen soporte CASCADE/SET NULL habilitado en tiempo de ejecución (`PRAGMA foreign_keys = OFF`), brindando defensa en profundidad.
- La unicidad por `(user_id, name)` asegura que los usuarios organicen sus categorías sin nombres repetidos, pero permite que distintos usuarios tengan categorías con el mismo nombre (ej. ambos pueden tener "Trabajo").

### Alternativas Evaluadas y Rechazadas
- **Eliminación en cascada (`ondelete="CASCADE"`)**: Terminantemente prohibida por los requerimientos del incremento.
- **Relación Muchos a Muchos (M:N con tabla intermedia de etiquetas/tags)**: Rechazada porque la especificación indica explícitamente que una tarea pertenece a lo sumo a una categoría. Introducir M:N violaría el Principio V (YAGNI).
- **Categorías globales compartidas**: Rechazadas porque violan el aislamiento por usuario (Principio VII).

---

## 3. Cálculo Centralizado en Backend del Indicador de Tareas Vencidas (HU-09)

### Decisión
El cálculo del estado de vencimiento se resuelve exclusivamente en el backend y **nunca se persiste como una columna de base de datos**.
Se implementará:
1. Como `@property` y método derivado en el modelo `Task`:
   ```python
   @property
   def is_overdue(self) -> bool:
       if self.status == "completed" or getattr(self, "is_deleted", False):
           return False
       if not self.due_date:
           return False
       return self.due_date < datetime.now(timezone.utc).date()
   ```
2. Integrado automáticamente en `task.to_dict()` para respuestas JSON / contratos API:
   ```python
   "is_overdue": self.is_overdue
   ```
3. En el renderizado Jinja2 del servidor, la plantilla accede a `task.is_overdue` y renderiza directamente la clase CSS y badge de vencimiento, sin lógica condicional en JavaScript.

### Razón de ser
- Cumple el Principio III (contrato explícito) y la directriz taxativa de HU-09: previene discrepancias horarias causadas por navegadores desconfigurados o zonas horarias dispares del cliente.
- No persistir el indicador en la base de datos elimina la necesidad de procesos por lotes periódicos (cron jobs diarios) para mantener sincronizada la base de datos, lo que violaría la simplicidad del monolito (Principio I y V).
- Excluye con precisión matemática y reglas de dominio a las tareas completadas o eliminadas lógicamente, garantizando que nunca se marquen como vencidas.

### Alternativas Evaluadas y Rechazadas
- **Columna persistida `is_overdue = Column(Boolean)`**: Rechazada porque genera inconsistencia inmediata al cambiar el día a medianoche a menos que se mantenga un worker externo continuo.
- **Cálculo en JavaScript (`new Date() > new Date(task.due_date)`)**: Rechazado tajantemente por la especificación y el Principio VII/III por generar inconsistencias y bugs de zona horaria.

---

## 4. Extensión del Endpoint de Listado de Tareas sin Regresiones (HU-02 + HU-07 + HU-08)

### Decisión
Extender `TaskService.get_user_tasks` para aceptar parámetros acumulativos:
```python
def get_user_tasks(
    user_id: int,
    status: Optional[str] = None,
    category_id: Optional[Union[int, str]] = None,
    sort_by: Optional[str] = None,
    order: str = "desc"
) -> List[Task]:
```
Lógica de filtrado y ordenamiento en el servicio:
- Si `status` se especifica: filtra `Task.status == status`.
- Si `category_id` es un entero: filtra `Task.category_id == category_id`.
- Si `category_id == "none"` o `"uncategorized"`: filtra `Task.category_id.is_(None)`.
- Si `sort_by == "priority"`:
  - Ordena por la expresión CASE de prioridad (`high` -> `medium` -> `low` si `order == 'desc'`), con desempate determinista por `Task.due_date.asc()` y `Task.id.desc()`.
- Si no se especifica `sort_by`: mantiene el orden por defecto preexistente (`Task.created_at.desc()`).

En la ruta `GET /tasks`:
- Lee los query parameters de `request.args`: `status`, `category_id`, `sort_by`, `order`.
- Pasa los parámetros sanitizados a `TaskService.get_user_tasks`.
- Pasa la lista de categorías del usuario al contexto Jinja2 (`categories = CategoryService.get_user_categories(user_id)`) para poblar el dropdown de filtro y modales de asignación.

### Razón de ser
- Garantiza total compatibilidad hacia atrás: cualquier llamada sin `category_id` ni `sort_by` funciona exactamente como en los Incrementos 1 y 2.
- Permite la combinación ortogonal de cualquier combinación de filtros (ej. `status=pending` AND `category_id=3` AND `sort_by=priority`).

---

## 5. Estrategia de Migraciones con Flask-Migrate (Principio VI)

### Decisión
Generar una migración versionada formal con Flask-Migrate / Alembic.
En el archivo de migración resultante:
```python
def upgrade():
    # 1. Crear tabla categories
    op.create_table(
        'categories',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=50), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'name', name='uq_user_category_name')
    )
    op.create_index(op.f('ix_categories_user_id'), 'categories', ['user_id'], unique=False)

    # 2. Modificar tabla tasks con soporte batch para SQLite
    with op.batch_alter_table('tasks', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('priority', sa.String(length=10), nullable=False, server_default='medium')
        )
        batch_op.add_column(
            sa.Column('category_id', sa.Integer(), nullable=True)
        )
        batch_op.create_index(batch_op.f('ix_tasks_category_id'), ['category_id'], unique=False)
        batch_op.create_foreign_key(
            'fk_tasks_category_id_categories',
            'categories',
            ['category_id'],
            ['id'],
            ondelete='SET NULL'
        )
```

### Razón de ser
- El uso de `batch_alter_table` garantiza que SQLite recree la tabla adecuadamente en desarrollo sin errores de sintaxis DDL.
- `server_default='medium'` evita violaciones de integridad referencial en tareas preexistentes.
