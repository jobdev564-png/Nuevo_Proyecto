# Quickstart & Verification Guide: 003-task-organization-priority

**Feature**: 003-task-organization-priority (Organización, Priorización e Indicación de Tareas Vencidas)  
**Date**: 2026-10-01  
**Status**: Draft  

---

## 1. Prerrequisitos y Preparación del Entorno

1. Python 3.11+ instalado en el sistema.
2. Entorno virtual activo con las dependencias del proyecto instaladas:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```
3. Base de datos con las migraciones actualizadas:
   ```powershell
   flask --app src.taskcontrol db upgrade
   ```

---

## 2. Ejecución de Pruebas Automatizadas Bloqueantes (Principio IV)

Para validar la conformidad constitucional previa a la integración, ejecuta la suite de pruebas unitarias y de servicios:

```powershell
pytest tests/services/test_task_service.py tests/services/test_category_service.py -v
```

### Escenarios Críticos Verificados por las Pruebas:
- **Prioridad por defecto**: Tarea creada sin prioridad adquiere automáticamente `'medium'`.
- **Ordenamiento jerárquico**: Listado ordenado por prioridad devuelve `high` -> `medium` -> `low` con desempate determinista.
- **Desvinculación segura de categorías**: Al borrar una categoría, sus tareas conservan sus datos y pasan a `category_id = None` (cero eliminaciones en cascada).
- **Aislamiento multiusuario**: Imposibilidad de asignar categorías ajenas a tareas propias.
- **Cálculo de vencimiento**:
  - Tarea con fecha pasada y estado `pending` -> `is_overdue == True`.
  - Tarea con fecha pasada y estado `completed` -> `is_overdue == False`.
  - Tarea sin fecha límite -> `is_overdue == False`.
  - Tarea con fecha límite del día de hoy -> `is_overdue == False`.

---

## 3. Escenarios de Validación Manual End-to-End

### Escenario A: Gestión de Prioridades y Ordenamiento (HU-07)
1. Iniciar la aplicación:
   ```powershell
   python -m flask --app src.taskcontrol run --port 5000
   ```
2. Iniciar sesión con un usuario de prueba en `http://127.0.0.1:5000/auth/login`.
3. Crear 3 tareas:
   - Tarea 1: Título "Tarea Urgente", prioridad seleccionada "Alta".
   - Tarea 2: Título "Tarea Normal", sin seleccionar prioridad (debe crearse como "Media").
   - Tarea 3: Título "Tarea Secundaria", prioridad seleccionada "Baja".
4. En el panel principal, seleccionar en el desplegable de orden: **"Prioridad (Mayor a Menor)"**.
5. **Resultado Esperado**: Las tareas aparecen en el orden: Tarea Urgente (Alta), Tarea Normal (Media), Tarea Secundaria (Baja).

---

### Escenario B: Categorización y Regla de Desvinculación Segura (HU-08)
1. Acceder a la sección de categorías (`/categories/`) y crear una categoría llamada "Operaciones".
2. Asignar la categoría "Operaciones" a la "Tarea Urgente".
3. Verificar en el listado que la "Tarea Urgente" muestra la etiqueta "Operaciones".
4. Filtrar por la categoría "Operaciones": solo la "Tarea Urgente" es mostrada.
5. Volver a `/categories/` y eliminar la categoría "Operaciones".
6. Regresar al listado general de tareas (`/tasks/`).
7. **Resultado Esperado**: La "Tarea Urgente" sigue existiendo en el sistema intacta, figurando ahora como "Sin categoría". Ninguna tarea fue eliminada.

---

### Escenario C: Indicador Centralizado de Tarea Vencida (HU-09)
1. Crear una tarea "Informe Atrasado" con fecha límite de hace 3 días y estado "Pendiente".
2. Crear otra tarea "Entregable Listo" con fecha límite de hace 3 días y estado "Completada".
3. Consultar el listado principal de tareas.
4. **Resultado Esperado**:
   - "Informe Atrasado" muestra un badge visible y destacado de **"Vencida"**.
   - "Entregable Listo" **NO** muestra distintivo de vencida a pesar de que su fecha límite ya pasó, respetando la regla de negocio.

---

## 4. Trazabilidad y Referencias

- Contratos de API:
  - [category-contracts.md](file:///C:/Users/SALAS/Documents/Nuevo_Proyecto/specs/003-task-organization-priority/contracts/category-contracts.md)
  - [task-organization-contracts.md](file:///C:/Users/SALAS/Documents/Nuevo_Proyecto/specs/003-task-organization-priority/contracts/task-organization-contracts.md)
- Modelo de Datos: [data-model.md](file:///C:/Users/SALAS/Documents/Nuevo_Proyecto/specs/003-task-organization-priority/data-model.md)
- Decisiones Arquitectónicas: [research.md](file:///C:/Users/SALAS/Documents/Nuevo_Proyecto/specs/003-task-organization-priority/research.md)
