# Feature Specification: 003-task-assignment-notifications

**Feature Branch**: `003-task-assignment-notifications`

**Created**: 2026-10-02

**Status**: Draft

**Input**: User description: "Especifica el cuarto incremento funcional de TaskControl: colaboración entre usuarios. Este incremento cubre HU-10 y HU-11 del backlog, y asume que los Incrementos 1 a 3 ya están implementados. Alcance funcional: 1. Asignación de tareas (HU-10): un usuario puede asignar una tarea propia a otro usuario existente del sistema (nunca a un correo que no esté registrado). El usuario asignado ve esa tarea en su propio listado de tareas, de la misma forma que ve las suyas propias — define si el listado distingue visualmente entre 'mis tareas creadas' y 'tareas asignadas a mí', o si se presentan sin distinción. El cambio de asignación queda registrado en el log de auditoría. 2. Notificación interna de asignación (HU-11): cuando a un usuario se le asigna una tarea, recibe una notificación dentro de la aplicación (no por correo ni push externo) que puede consultar sin tener que revisar manualmente el listado completo de tareas. Define cómo se marca una notificación como leída y si persiste tras leerse o se descarta. Fuera de alcance explícito de este incremento: interacción sin recarga de página y drag-and-drop (HU-15, HU-16), que se especifican en el incremento final. Esta especificación debe ser consistente con la constitución del proyecto: toda reasignación queda auditada con actor y timestamp (Principio VIII), y la verificación de que solo se puede asignar a usuarios existentes se valida en el backend, no solo en un selector del frontend (Principio VII)."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Asignar tarea propia a otro usuario existente (HU-10) (Priority: P1)

Como usuario autenticado, quiero asignar una tarea propia a otro usuario registrado del sistema, para delegar trabajo sabiendo que solo puede recibirla alguien con cuenta existente.

**Why this priority**: Es el núcleo de la colaboración (Épica 3). Sin asignación no existe delegación ni notificación posterior. Materializa el Principio VII (validación en backend de que el destinatario existe) y el Principio VIII (auditoría de cada reasignación con actor y timestamp).

**Independent Test**: Puede probarse creando dos usuarios (A y B), creando una tarea como A, asignándola a B por su correo registrado, y verificando que B la ve en su listado con los mismos datos (título, estado, fecha límite) mientras que el intento de asignar al mismo u otro correo no registrado es rechazado sin mutar la tarea y sin generar evento de auditoría.

**Acceptance Scenarios**:

1. **Given** un usuario autenticado A con una tarea propia activa (no eliminada), **When** A asigna la tarea al correo de un usuario existente B, **Then** la tarea queda asignada a B, B la ve en su propio listado con título, estado y fecha límite igual que sus tareas propias, y se genera un registro de auditoría con actor = A, acción `TASK_ASSIGNED`, entidad = tarea y timestamp UTC.
2. **Given** un usuario autenticado A con una tarea propia, **When** A intenta asignarla a un correo que no corresponde a ningún usuario registrado, **Then** el sistema rechaza la operación con error controlado, la asignación no cambia, no se genera evento `TASK_ASSIGNED` y no se crea ninguna notificación.
3. **Given** un usuario autenticado A intentando asignar una tarea que no le pertenece (propiedad de B) o que está eliminada lógicamente, **When** envía la solicitud de asignación, **Then** el sistema rechaza la operación por falta de autorización o estado inválido (403/404/400) sin alterar la tarea ni generar auditoría de asignación.
4. **Given** una tarea ya asignada a B, **When** el usuario actualmente responsable (B) o el asignador original según regla de autorización la reasigna a un tercer usuario existente C, **Then** la tarea pasa a ser visible en el listado de C, deja de estar asignada a B, y cada cambio genera su propio evento `TASK_ASSIGNED` con su actor y timestamp correspondientes.
5. **Given** el listado de tareas de un usuario que contiene tareas creadas por él y tareas que otros le asignaron, **When** visualiza el listado, **Then** cada tarea asignada por otro muestra una distinción visual (etiqueta "Asignada a mí" con nombre o correo del asignador) y el listado ofrece un filtro para ver "Todas / Creadas por mí / Asignadas a mí", manteniendo por defecto la vista unificada ordenable y filtrable por estado igual que en HU-02.

---

### User Story 2 - Recibir y gestionar notificación interna de asignación (HU-11) (Priority: P2)

Como usuario asignado, quiero recibir una notificación dentro de la aplicación cuando se me asigna una tarea, para enterarme sin tener que revisar manualmente todo el listado de tareas.

**Why this priority**: Cierra el ciclo de delegación desde la perspectiva del receptor. Es de prioridad Could en el backlog pero forma parte inseparable de este incremento colaborativo: sin aviso interno, el asignado solo descubriría la tarea por inspección manual.

**Independent Test**: Puede probarse asignando una tarea de A a B y verificando que al siguiente acceso de B (con recarga de página, sin necesidad de JS asíncrono) existe un indicador visible de notificación pendiente (contador o sección "Notificaciones"), que al abrirla muestra qué tarea fue asignada, quién la asignó y cuándo, y que tras marcarla como leída el contador de pendientes disminuye sin que la notificación desaparezca del historial.

**Acceptance Scenarios**:

1. **Given** una asignación exitosa de una tarea a B, **When** B accede a la aplicación, **Then** ve sin revisar el listado completo que tiene una notificación pendiente (indicador de no leídas) que identifica la tarea asignada, quién se la asignó y la fecha de asignación.
2. **Given** un usuario con una notificación no leída, **When** la marca explícitamente como leída (acción "marcar como leída" individual o "marcar todas como leídas"), **Then** la notificación cambia a estado leída, deja de contar como pendiente, pero persiste visible en el historial de notificaciones (no se elimina físicamente).
3. **Given** un usuario con notificaciones ya leídas, **When** consulta su historial de notificaciones, **Then** sigue viendo las notificaciones leídas diferenciadas visualmente (atenuadas o con marca "leída") junto a los datos de la tarea y el asignador.
4. **Given** un intento de asignación rechazado (correo inexistente, tarea ajena o eliminada), **When** se completa el rechazo, **Then** no se genera ninguna notificación para ningún usuario.

---

### Edge Cases

- **Asignación a uno mismo**: Asignar una tarea al propio correo del solicitante se rechaza o se trata como operación sin efecto (sin generar `TASK_ASSIGNED` ni notificación duplicada), informando que la tarea ya le pertenece.
- **Correo con mayúsculas/espacios o formato inválido**: El identificador del destinatario se normaliza (recorte de espacios, comparación insensible a mayúsculas) y si tras normalizar no existe usuario, se rechaza igual que un correo no registrado; un formato de correo inválido se rechaza por validación sin consultar asignaciones.
- **Tarea eliminada o completada**: Una tarea eliminada lógicamente no puede asignarse; una tarea completada sí puede asignarse (transfiere el pendiente de revisión), salvo que el equipo decida bloquearlo — en este spec se permite y queda auditado.
- **Reasignaciones concurrentes**: Si dos peticiones intentan asignar la misma tarea a destinatarios distintos de forma simultánea, solo una prevalece; cada intento exitoso genera exactamente un evento `TASK_ASSIGNED` y una sola notificación al asignado final efectivo.
- **Usuario destinatario eliminado o inexistente al momento de validar**: La validación de existencia se hace en el backend en el momento de la asignación (Principio VII); si el usuario no existe, la operación falla aunque el frontend ofreciera un selector con ese valor manipulado.
- **Notificación huérfana**: Si la tarea asignada se elimina lógicamente después de notificar, la notificación persiste en el historial pero al intentar navegar a la tarea se informa que ya no está disponible.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El sistema DEBE permitir a un usuario autenticado asignar una tarea propia activa (no eliminada) a otro usuario registrado, identificado por su correo.
- **FR-002**: El sistema DEBE validar en el backend que el correo destinatario corresponde a un usuario existente en el momento de la asignación, sin confiar en selectores o validaciones del frontend (Principio VII).
- **FR-003**: El sistema DEBE rechazar con error controlado cualquier intento de asignación a un correo no registrado, sin mutar la tarea, sin generar evento de auditoría `TASK_ASSIGNED` y sin generar notificación.
- **FR-004**: El sistema DEBE impedir la asignación de tareas ajenas (no propias / no asignadas actualmente al solicitante) y de tareas eliminadas lógicamente, respondiendo con error de autorización o estado inválido sin alterar datos.
- **FR-005**: Tras una asignación exitosa, el sistema DEBE mostrar la tarea en el listado del usuario asignado con los mismos atributos que sus tareas propias (título, estado, fecha límite) y con las mismas capacidades de filtrado por estado y ordenación ya existentes.
- **FR-006**: El listado de tareas DEBE distinguir visualmente las tareas asignadas por otro usuario mediante una etiqueta "Asignada a mí" con la identidad del asignador (nombre o correo), y DEBE ofrecer un filtro "Todas / Creadas por mí / Asignadas a mí".
- **FR-007**: El modelo de asignación DEBE ser de transferencia de responsabilidad a un único responsable: tras asignar a B, la tarea pertenece a B (aparece en su listado y deja de pertenecer al listado del asignador), y cada reasignación posterior transfiere del mismo modo con su propia auditoría.
- **FR-008**: El sistema DEBE registrar en el log de auditoría un evento con acción `TASK_ASSIGNED` por cada asignación o reasignación exitosa, incluyendo obligatoriamente `actor_id` (quien asigna), `action` = `TASK_ASSIGNED`, `entity_id` (tarea), `timestamp` UTC ISO-8601, más detalles no confidenciales (asignador previo y nuevo asignado).
- **FR-009**: El sistema DEBE generar automáticamente una notificación interna dirigida al nuevo asignado por cada asignación exitosa, con referencia a la tarea, identidad del asignador y fecha de asignación.
- **FR-010**: El sistema DEBE exponer las notificaciones dentro de la aplicación (sección o página de notificaciones consultable con recarga de página clásica, sin exigir HU-15/HU-16), con un indicador de notificaciones no leídas visible sin revisar el listado completo de tareas.
- **FR-011**: El sistema DEBE permitir marcar una notificación como leída mediante acción explícita individual y mediante acción "marcar todas como leídas"; al marcarse, la notificación DEBE persistir en el historial en estado leída (no eliminarse físicamente) y dejar de contar como pendiente.
- **FR-012**: Las notificaciones leídas DEBEN seguir visibles en el historial, diferenciadas visualmente de las no leídas, con los datos de tarea, asignador y fecha.
- **FR-013**: El sistema NO DEBE generar notificaciones por intentos de asignación fallidos, ni enviar notificaciones por correo electrónico o push externo en este incremento.
- **FR-014**: El sistema DEBE exigir autenticación y autorización en cada endpoint de asignación y de notificaciones, verificadas en el backend (Principio VII).

### Exclusiones Explícitas (Fuera de Alcance)

- Interacción sin recarga de página para asignar o completar tareas (HU-15).
- Reordenamiento visual mediante arrastrar y soltar / persistencia de orden (HU-16).
- Asignación múltiple simultánea (varios responsables por tarea) o roles diferenciados (observador, editor): cada tarea tiene un único responsable.
- Envío de notificaciones por correo electrónico, push externo o integraciones de terceros.
- Eliminación o borrado de notificaciones por el usuario (solo se contempla marcar como leída; el descarte queda fuera de este incremento).
- Papelera de reciclaje o restauración de tareas eliminadas; categorías (HU-08), vencimientos calculados (HU-09) y prioridades (HU-07) salvo que ya existan de incrementos previos.

### Key Entities

- **User**: Identidad del sistema.
  - Atributos clave: Identificador único (`id`), correo electrónico (`email`, único), hash de contraseña (`password_hash`), fecha de creación (`created_at`).
  - Relaciones: Es responsable de múltiples `Task` asignadas, recibe múltiples `Notification`, protagoniza eventos `AuditLog`.
- **Task**: Unidad de trabajo delegable con responsable único.
  - Atributos clave: Identificador único (`id`), responsable actual (`owner_id` / `assignee_id` — transfiere en cada asignación), referencia al creador original si se distingue del responsable (`created_by`), título (`title`), descripción (`description`), fecha límite (`due_date`), estado (`status`: `pending`, `in_progress`, `completed`), marca de eliminación lógica (`is_deleted`), marcas de tiempo (`created_at`, `updated_at`).
  - Relaciones: Pertenece a un `User` responsable; genera eventos `AuditLog` y `Notification` en cada asignación.
- **Notification**: Aviso interno de asignación.
  - Atributos clave: Identificador único (`id`), destinatario (`user_id`), tarea referida (`task_id`), asignador (`assigned_by`), fecha de creación (`created_at`), estado de lectura (`is_read` / `read_at`).
  - Relaciones: Pertenece a un `User` destinatario y referencia a una `Task`.
- **AuditLog**: Registro inmutable de trazabilidad (Principio VIII).
  - Atributos clave: Identificador único (`id`), actor (`actor_id`), acción (`action`: incluye `TASK_ASSIGNED` además de las ya existentes), entidad (`entity_id`), timestamp UTC (`timestamp`), detalles (`details`: previo y nuevo responsable, sin secretos).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: El 100% de las asignaciones a correos registrados transfiere la tarea al listado del asignado en su siguiente carga, con título, estado y fecha límite idénticos a los de origen.
- **SC-002**: El 100% de los intentos de asignación a correos no registrados son rechazados sin mutar la tarea, sin auditoría `TASK_ASSIGNED` y sin notificación (tasa de asignación fantasma = 0%).
- **SC-003**: El 100% de las asignaciones y reasignaciones exitosas genera exactamente un evento `TASK_ASSIGNED` con los 4 campos obligatorios (`actor_id`, `action`, `entity_id`, `timestamp`).
- **SC-004**: El 100% de las asignaciones exitosas genera exactamente una notificación interna visible para el nuevo asignado sin necesidad de inspeccionar manualmente el listado completo.
- **SC-005**: El 100% de las notificaciones marcadas como leídas persiste en el historial en estado leída y deja de contar como pendiente (0% de eliminaciones físicas al marcar como leída).
- **SC-006**: Un usuario con tareas propias y asignadas distingue el 100% de las asignadas mediante etiqueta "Asignada a mí" y puede filtrar "Todas / Creadas por mí / Asignadas a mí" con resultados correctos en cada filtro.
- **SC-007**: El 100% de los intentos de asignar tareas ajenas o eliminadas es rechazado sin filtrar datos ni alterar el estado original.

## Assumptions

- La asignación es transferencia de responsabilidad a un único responsable (no co-propiedad): la tarea deja de listarse para el asignador y pasa al asignado. El creador original puede conservarse como dato informativo (`created_by`) pero no otorga visibilidad por sí solo.
- La distinción visual elegida es lista unificada con etiqueta "Asignada a mí" + filtro de origen, en lugar de dos listas separadas, para reutilizar filtros y ordenación existentes (HU-02) con el menor cambio de interfaz.
- Las notificaciones persisten tras leerse (modelo historial con flag `is_read`/`read_at`) en lugar de descartarse, para conservar evidencia de delegación y permitir auditoría desde la perspectiva del receptor.
- El identificador del destinatario es el correo electrónico del usuario (único del sistema); la comparación es insensible a mayúsculas y tolera espacios laterales.
- Asignarse una tarea a uno mismo se considera operación sin efecto y se rechaza con mensaje informativo, sin auditoría ni notificación.
- Las notificaciones se consultan con recarga de página clásica (renderizado de servidor); el indicador de pendientes y el historial no requieren JavaScript asíncrono (HU-15/HU-16 quedan para el incremento final).
- No se contempla en este incremento el borrado de notificaciones por el usuario ni su caducidad automática.
