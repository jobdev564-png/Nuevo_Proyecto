# Feature Specification: 003-task-organization-priority

**Feature Branch**: `incremento3`

**Created**: 2026-10-01

**Status**: Draft

**Input**: User description: "Especifica el tercer incremento funcional de TaskControl: organización y priorización de tareas. Este incremento cubre HU-07, HU-08 y HU-09 del backlog, y asume que los Incrementos 1 y 2 ya están implementados. Alcance funcional: 1. Prioridad de tareas (HU-07): toda tarea tiene una prioridad (alta, media, baja) con un valor por defecto definido explícitamente. El listado de tareas (ya existente desde HU-02) se puede ordenar por prioridad, además de los filtros por estado ya existentes. Un usuario puede cambiar la prioridad de una tarea propia en cualquier momento. 2. Categorías o proyectos (HU-08): un usuario puede crear categorías para agrupar tareas relacionadas. Una tarea pertenece a máximo una categoría (o a ninguna). Eliminar una categoría no elimina las tareas que pertenecían a ella — quedan sin categoría, nunca se eliminan en cascada. 3. Indicación de tareas vencidas (HU-09): el sistema calcula si una tarea está vencida (fecha límite superada y no completada) y lo expone en el listado. Este cálculo se hace exclusivamente en el backend, nunca en JavaScript, para evitar inconsistencias por zona horaria del cliente. Una tarea eliminada o completada nunca se marca como vencida aunque su fecha límite haya pasado. Fuera de alcance explícito de este incremento: asignación y notificaciones (HU-10, HU-11), interacción sin recarga de página y drag-and-drop (HU-15, HU-16). Esta especificación debe ser consistente con la constitución del proyecto: separación de capas al introducir el nuevo concepto de categoría como entidad propia (Principio II), y cálculo de vencimiento resuelto en el backend como parte del contrato de datos que recibe el frontend (Principio III)."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Priorización de Tareas y Ordenamiento (HU-07) (Priority: P1)

Como usuario autenticado, quiero asignar y modificar un nivel de prioridad (alta, media o baja) a mis tareas y disponer de la capacidad de ordenar mi listado por dicho criterio, para identificar y atender primero el trabajo más crítico o urgente.

**Why this priority**: Es la base del valor de priorización en la gestión de tareas. Permite al usuario clasificar su carga de trabajo y tomar decisiones operativas inmediatas según la importancia relativa de cada tarea.

**Independent Test**: Puede probarse creando tareas con diferentes prioridades (y verificando que al no especificarla se asigne "media"), listando las tareas ordenadas por prioridad (alta > media > baja), y actualizando la prioridad de una tarea existente comprobando la persistencia del cambio y su correspondiente registro de auditoría.

**Acceptance Scenarios**:

1. **Given** un usuario autenticado que crea una tarea sin especificar prioridad, **When** el sistema procesa la creación, **Then** la tarea se almacena con la prioridad por defecto "media" (`medium`) y se refleja así en el listado.
2. **Given** un usuario autenticado que crea o edita una tarea seleccionando explícitamente una prioridad válida ("alta", "media" o "baja"), **When** guarda la tarea, **Then** el sistema almacena la prioridad seleccionada y audita el cambio en caso de modificación.
3. **Given** un listado de tareas con distintas prioridades, **When** el usuario solicita ordenar por prioridad, **Then** el sistema presenta las tareas agrupadas u ordenadas respetando la jerarquía de prioridad (alta > media > baja, o viceversa según el sentido solicitado), manteniendo activos los filtros de estado aplicados.
4. **Given** una tarea con prioridad asignada, **When** el usuario propietario actualiza su prioridad en cualquier momento, **Then** el nuevo valor se actualiza inmediatamente y se registra un evento de auditoría con la acción correspondiente.
5. **Given** una solicitud de creación o edición con un valor de prioridad no reconocido (distinto de "alta", "media", "baja"), **When** se envía al sistema, **Then** la operación es rechazada con un mensaje de validación claro.

---

### User Story 2 - Agrupación en Categorías y Desvinculación Segura (HU-08) (Priority: P2)

Como usuario autenticado, quiero crear categorías para clasificar tareas afines y asociar cada tarea a máximo una categoría (o ninguna), teniendo la certeza de que si elimino una categoría, sus tareas asociadas permanecerán intactas en el sistema sin borrarse en cascada.

**Why this priority**: Proporciona estructura organizacional a mediano y largo plazo para proyectos o áreas de trabajo, garantizando la integridad referencial y evitando pérdidas accidentales de datos.

**Independent Test**: Puede probarse creando una categoría propia, vinculando una o más tareas a ella, comprobando que una tarea pertenezca a lo sumo a una categoría, y eliminando la categoría para verificar que las tareas vinculadas continúen existiendo con su atributo de categoría en nulo ("sin categoría").

**Acceptance Scenarios**:

1. **Given** un usuario autenticado, **When** crea una categoría indicando un nombre válido y no duplicado para su cuenta, **Then** la categoría se crea exitosamente asociada a su usuario y se genera un registro de auditoría (`CATEGORY_CREATED`).
2. **Given** un usuario que intenta crear una categoría con un nombre que ya utiliza en otra de sus categorías, **When** envía la solicitud, **Then** el sistema rechaza la creación indicando que el nombre de la categoría ya existe para su cuenta.
3. **Given** una tarea nueva o existente, **When** el usuario le asigna una categoría propia, **Then** la tarea queda vinculada a dicha categoría (máximo una) y se audita el cambio si es una edición.
4. **Given** una tarea asociada a una categoría, **When** el usuario edita la tarea para remover la categoría, **Then** la tarea queda clasificada como "sin categoría" sin alterar sus demás atributos.
5. **Given** una categoría que contiene varias tareas asociadas, **When** el usuario propietario elimina la categoría, **Then** la categoría es eliminada, pero todas las tareas que le pertenecían permanecen íntegras en el sistema con su categoría desvinculada ("sin categoría"), y se audita la eliminación (`CATEGORY_DELETED`).
6. **Given** una categoría perteneciente a otro usuario, **When** un usuario intenta verla, asignarla a una tarea propia o eliminarla, **Then** el sistema deniega la operación con error de autorización o no encontrado.

---

### User Story 3 - Indicación Determinista de Tareas Vencidas desde el Backend (HU-09) (Priority: P3)

Como usuario autenticado, quiero que el sistema calcule e indique claramente en el listado qué tareas se encuentran vencidas (con fecha límite rebasada y no completadas), basándose en un cálculo centralizado en el servidor para evitar discrepancias por zonas horarias o configuraciones locales del cliente.

**Why this priority**: Otorga visibilidad inmediata de retrasos y compromisos vencidos sin riesgo de desincronización horaria entre el cliente y el servidor.

**Independent Test**: Puede probarse creando tareas con fecha límite en el pasado en estados "pendiente", "en progreso" y "completada", y verificando que el contrato de salida del servidor devuelva el indicador de vencida (`is_overdue = true`) únicamente para aquellas pendientes o en progreso, y `is_overdue = false` para tareas completadas, eliminadas o sin fecha límite.

**Acceptance Scenarios**:

1. **Given** una tarea con fecha límite estrictamente anterior a la fecha actual del sistema en estado "pendiente" o "en progreso", **When** se consulta el listado o detalle de tareas, **Then** el backend resuelve y expone `is_overdue = true`, y la interfaz muestra una advertencia visual clara de vencimiento.
2. **Given** una tarea cuya fecha límite está en el pasado pero su estado es "completada", **When** se evalúa su condición, **Then** el backend resuelve `is_overdue = false` y la interfaz no la señala como vencida.
3. **Given** una tarea que no tiene fecha límite configurada (nula), **When** se evalúa su condición, **Then** el backend resuelve `is_overdue = false`.
4. **Given** una tarea cuya fecha límite es el día de hoy, **When** se evalúa durante el transcurso del día, **Then** el backend resuelve `is_overdue = false` (no está vencida hasta que el día haya transcurrido por completo).
5. **Given** una tarea eliminada lógicamente, **When** se evalúa en el sistema, **Then** bajo ninguna circunstancia se marca como vencida (`is_overdue = false`).
6. **Given** la renderización del listado en el cliente, **When** se despliega la interfaz de usuario, **Then** el frontend consume directamente el indicador booleano provisto por el backend sin realizar cálculos de fechas en JavaScript.

---

### User Story 4 - Consulta Integrada: Filtrado por Categoría y Estado con Orden por Prioridad (Priority: P3)

Como usuario autenticado, quiero combinar el filtrado por categoría (incluyendo tareas "sin categoría") y por estado, junto con el ordenamiento por prioridad, para focalizar mi sesión de trabajo exactamente en las tareas relevantes para mi contexto actual.

**Why this priority**: Integra armónicamente las capacidades de las historias HU-02, HU-07 y HU-08 en una vista consolidada y eficiente.

**Independent Test**: Puede probarse aplicando filtros cruzados (estado "pendiente" + categoría específica + orden por prioridad) y validando que el conjunto de resultados cumpla estrictamente todas las condiciones simultáneas.

**Acceptance Scenarios**:

1. **Given** un conjunto diverso de tareas, **When** el usuario filtra por una categoría específica y selecciona ordenamiento por prioridad, **Then** el sistema presenta únicamente las tareas asociadas a esa categoría ordenadas jerárquicamente por su prioridad.
2. **Given** un usuario que selecciona el filtro especial "Sin categoría", **When** se procesa la consulta, **Then** se muestran únicamente aquellas tareas del usuario que no tienen ninguna categoría vinculada.
3. **Given** un usuario que selecciona simultáneamente filtro por estado ("en progreso"), filtro por categoría y orden por prioridad, **When** se consulta el listado, **Then** el resultado satisface los tres criterios de manera combinada.

---

### Edge Cases

- **Eliminación concurrente de categoría durante asignación**: Si un usuario intenta asignar una categoría que acaba de ser eliminada en otra pestaña o sesión, el sistema debe capturar el error y rechazar la asignación de forma controlada o asignarla como "sin categoría" con notificación informativa.
- **Categoría homónima entre usuarios distintos**: Dos usuarios diferentes deben poder crear categorías con el mismo nombre (ej. "Trabajo") sin colisión; la restricción de unicidad es estrictamente por usuario (`user_id` + `name`).
- **Fecha límite en el límite del huso horario**: La comparación de fecha límite se realiza contra la fecha calendario del servidor (UTC o zona base de referencia del sistema), asegurando consistencia independientemente de la zona horaria del navegador del cliente.
- **Desempate en ordenamiento por prioridad**: Cuando dos o más tareas comparten el mismo nivel de prioridad, el sistema aplica un criterio de orden secundario determinista (fecha límite más próxima primero, o fecha de creación más reciente) para evitar que el orden cambie aleatoriamente entre peticiones.
- **Asignación de categoría ajena (IDOR)**: Si un usuario manipula la petición enviando el identificador de una categoría perteneciente a otro usuario, el backend debe rechazar la operación (error de validación o no encontrado) impidiendo vincular tareas a categorías de terceros.
- **Tareas eliminadas lógicamente**: Si una tarea se encuentra eliminada, no debe figurar en el listado por defecto ni marcarse como vencida, y no se debe permitir la mutación de su prioridad o categoría.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El sistema DEBE soportar exactamente tres niveles de prioridad para las tareas: alta (`high`), media (`medium`) y baja (`low`).
- **FR-002**: El sistema DEBE asignar automáticamente la prioridad media (`medium`) como valor por defecto a toda tarea creada cuando no se indique una prioridad explícita.
- **FR-003**: El sistema DEBE validar que la prioridad asignada a una tarea pertenezca estrictamente al conjunto permitido (`high`, `medium`, `low`), rechazando cualquier otro valor con un mensaje de validación descriptivo.
- **FR-004**: El sistema DEBE permitir al usuario propietario modificar la prioridad de una tarea propia existente en cualquier momento.
- **FR-005**: El sistema DEBE permitir ordenar el listado de tareas por su nivel de prioridad en sentido descendente (alta > media > baja) o ascendente (baja > media > alta).
- **FR-006**: El sistema DEBE aplicar un criterio de desempate determinista secundario (fecha límite ascendente o fecha de creación) cuando varias tareas posean el mismo nivel de prioridad.
- **FR-007**: El ordenamiento por prioridad DEBE poder combinarse de forma simultánea con los filtros existentes por estado (`pending`, `in_progress`, `completed`).
- **FR-008**: El sistema DEBE permitir a los usuarios autenticados crear categorías proporcionando un nombre obligatorio (longitud máxima de 50 caracteres, no vacío) y una descripción opcional.
- **FR-009**: El sistema DEBE garantizar la unicidad del nombre de categoría por usuario, impidiendo que un mismo usuario tenga dos categorías con nombres idénticos (insensible a mayúsculas/minúsculas).
- **FR-010**: El sistema DEBE permitir al usuario autenticado listar y visualizar exclusivamente sus propias categorías creadas.
- **FR-011**: El sistema DEBE permitir al usuario autenticado asociar una tarea propia a un máximo de una categoría, o mantenerla sin categoría asignada.
- **FR-012**: El sistema DEBE verificar estrictamente en el backend que la categoría asignada a una tarea pertenezca al mismo usuario autenticado propietario de la tarea, denegando el uso de categorías de terceros.
- **FR-013**: El sistema DEBE permitir filtrar el listado de tareas por una categoría específica del usuario o por la condición especial "sin categoría".
- **FR-014**: El sistema DEBE permitir al usuario autenticado eliminar una categoría propia.
- **FR-015**: Al eliminarse una categoría, el sistema DEBE desvincular automáticamente todas las tareas asociadas (estableciendo su categoría en nula), y bajo ninguna circunstancia DEBE eliminar las tareas en cascada ni modificar sus demás propiedades.
- **FR-016**: El sistema DEBE calcular en el backend el indicador de vencimiento (`is_overdue`) para cada tarea expuesta en listados y detalles.
- **FR-017**: Una tarea DEBE resolverse como vencida (`is_overdue = true`) si y solo si: posee fecha límite asignada, su fecha límite es estrictamente anterior a la fecha actual de referencia del servidor, y su estado actual NO es "completada" (`completed`) ni está eliminada.
- **FR-018**: Si una tarea tiene fecha límite pasada pero su estado es "completada" o está eliminada, el sistema DEBE resolverla obligatoriamente como no vencida (`is_overdue = false`).
- **FR-019**: Si una tarea no tiene fecha límite asignada, el sistema DEBE resolverla obligatoriamente como no vencida (`is_overdue = false`).
- **FR-020**: El indicador `is_overdue` DEBE formar parte integral del contrato de datos entregado por el backend a la capa de presentación, quedando prohibido delegar o recalcular esta lógica en JavaScript del lado cliente.
- **FR-021**: El sistema DEBE registrar un log de auditoría estructurado para cada operación de mutación relacionada con la organización y priorización:
  - `CATEGORY_CREATED`: Al crear una categoría.
  - `CATEGORY_DELETED`: Al eliminar una categoría.
  - `TASK_PRIORITY_CHANGED`: Al modificar la prioridad de una tarea.
  - `TASK_CATEGORY_CHANGED`: Al asignar, modificar o remover la categoría de una tarea.
  Cada registro de auditoría debe contener obligatoriamente `actor_id`, `action`, `entity_id` y `timestamp` ISO-8601 UTC.

### Exclusiones Explícitas (Fuera de Alcance)

- Asignación de tareas a otros usuarios (`HU-10`).
- Notificaciones internas o alertas dentro de la aplicación (`HU-11`).
- Interacción asíncrona sin recarga de página para marcar tareas completadas (`HU-15`).
- Reordenamiento visual manual mediante arrastrar y soltar (drag-and-drop) (`HU-16`).
- Asignación de múltiples categorías o etiquetas (tags múltiples) a una misma tarea.
- Categorías compartidas o colaborativas entre usuarios.

### Key Entities

- **Category**: Representa un contenedor organizativo o proyecto creado por un usuario para agrupar tareas afines.
  - Atributos: `id` (identificador único), `user_id` (referencia obligatoria al usuario propietario), `name` (cadena obligatoria, máximo 50 caracteres, única por usuario), `description` (texto opcional), `created_at` (marca de tiempo UTC).
- **Task (Ampliación)**: Representa la unidad de trabajo del dominio con atributos extendidos para priorización, categorización y estado temporal.
  - Atributos extendidos/relevantes: `id`, `user_id` (propietario), `title`, `description`, `due_date`, `status` (`pending`, `in_progress`, `completed`), `priority` (cadena/enum: `high`, `medium`, `low`; valor por defecto: `medium`), `category_id` (referencia opcional/nula a `Category`, con política de desvinculación `SET NULL` ante borrado de la categoría), `is_overdue` (propiedad calculada en backend: booleano), `created_at`, `updated_at`.
- **AuditLog**: Registro inmutable para observabilidad y trazabilidad de mutaciones en el sistema (ampliado con acciones `CATEGORY_CREATED`, `CATEGORY_DELETED`, `TASK_PRIORITY_CHANGED`, `TASK_CATEGORY_CHANGED`).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: El 100% de las tareas creadas sin especificación explícita de prioridad se inicializan automáticamente con la prioridad "media".
- **SC-002**: El ordenamiento del listado por prioridad organiza las tareas de manera consistente y determinista en menos de 1 segundo para cuentas con hasta 500 tareas.
- **SC-003**: Cero tareas eliminadas accidentalmente al borrar una categoría: el 100% de las tareas vinculadas a una categoría eliminada permanecen en el sistema con su categoría establecida en "sin categoría" (`category_id = null`).
- **SC-004**: Cero inconsistencias de cálculo de vencimiento debidas a la configuración horaria del cliente: el 100% de las evaluaciones de vencimiento son calculadas en el servidor antes de ser enviadas a la interfaz.
- **SC-005**: El 100% de los intentos de asociar una tarea con una categoría perteneciente a otro usuario son rechazados por el backend con código de error de cliente o autorización.
- **SC-006**: El 100% de las mutaciones de categorías y modificaciones de prioridad o categoría de tareas generan un registro de auditoría conforme al Principio VIII de la constitución.
- **SC-007**: La cobertura de pruebas automatizadas para la lógica de prioridades, categorías y cálculo de vencimiento en la capa de servicios alcanza el 100% antes de la habilitación de rutas HTTP.

## Assumptions

- **Niveles de prioridad**: Se definen exactamente tres niveles de prioridad (`high`, `medium`, `low`) representados internamente en inglés para consistencia de código y expuestos al usuario en español ("Alta", "Media", "Baja").
- **Criterio de orden jerárquico**: Por defecto, el ordenamiento descendente de prioridad posiciona primero "Alta", luego "Media" y finalmente "Baja".
- **Desempate en ordenamiento**: Para tareas con idéntica prioridad, el desempate secundario se realiza por fecha límite más próxima (ascendente) y, en caso de empate o ausencia de fecha, por fecha de creación más reciente (descendente).
- **Aislamiento de categorías**: Las categorías son privadas y exclusivas de cada usuario. No existen categorías globales ni categorías compartidas entre múltiples usuarios en este incremento.
- **Relación 1 a N**: Una tarea solo puede pertenecer a cero o una categoría. No se soportan etiquetas múltiples ni subcategorías jerárquicas.
- **Regla de vencimiento**: La condición de vencida evalúa si la fecha límite es estrictamente anterior a la fecha actual del sistema en UTC (`due_date < current_date`). Si la fecha límite es igual a la fecha actual, la tarea no está vencida.
- **Estado previo del sistema**: Se asume que los Incrementos 1 y 2 están plenamente funcionales (autenticación de usuarios, ciclo de vida de tareas y eliminación lógica/reapertura).
