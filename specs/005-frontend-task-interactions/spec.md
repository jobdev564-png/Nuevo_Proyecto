# Feature Specification: Interacción fluida del listado de tareas

**Feature Branch**: `005-frontend-task-interactions`

**Created**: 2026-10-11

**Status**: Draft

**Input**: User description: "Especifica el quinto y último incremento funcional de TaskControl: mejoras de interacción en el frontend mediante JavaScript. Este incremento cubre HU-15 y HU-16 del backlog, y asume que todos los incrementos anteriores (1 a 4) ya están implementados y expuestos como endpoints HTTP con contrato definido. Alcance funcional: 1. Completar tareas sin recargar la página (HU-15): desde el listado de tareas, un usuario marca una tarea como completada mediante una interacción de JavaScript que llama al endpoint de cambio de estado ya existente (del Incremento 1), sin recargar la página completa. Si la petición al backend falla, la interfaz revierte el cambio visual mostrado y presenta un mensaje de error al usuario — nunca debe quedar la interfaz mostrando un estado que el backend no confirmó. 2. Reordenar tareas arrastrándolas (HU-16): un usuario reordena visualmente sus tareas en el listado mediante arrastrar y soltar (drag and drop). El nuevo orden se persiste en el backend inmediatamente después de soltar el elemento, de forma que si el usuario recarga la página el orden se mantiene. Como este es el incremento final de JavaScript, no introduce ningún endpoint nuevo de backend — reutiliza exclusivamente los contratos ya definidos en incrementos anteriores (cambio de estado) y requiere, como único elemento nuevo de backend, un campo de orden persistente por tarea para HU-16. Esta especificación debe ser consistente con la constitución del proyecto: no se introduce ningún framework SPA (React, Vue, Angular) salvo justificación explícita, manteniéndose en JavaScript vanilla o una librería ligera de interactividad (restricción técnica del stack), y toda llamada al backend sigue el contrato de endpoints ya documentado (Principio III)."

## Clarifications

### Session 2026-10-11

- Q: ¿Qué transiciones de estado debe permitir la acción rápida de completar sin recarga? → A: Salto directo (pendiente→completada y en progreso→completada en un gesto).
- Q: ¿Cómo convive el orden manual por arrastre con los filtros por estado y el orden por prioridad? → A: Orden por vista (el arrastre reordena solo la vista filtrada actual; cada vista conserva su propio orden).
- Q: ¿Qué alternativa sin arrastre debe existir para reordenar con teclado o lector de pantalla? → A: Botones subir/bajar por fila operables por teclado además del arrastre.
- Q: ¿Dónde aparecen las tareas nuevas y qué pasa con las completadas en el orden manual? → A: Nuevas al final; las completadas conservan su posición en el orden.
- Q: ¿Debe auditarse cada persistencia del orden manual de tareas? → A: Sí, cada persistencia de orden genera un registro de auditoría estructurado.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Marcar tarea como completada sin recargar la página (HU-15) (Priority: P1)

Un usuario autenticado visualiza su listado de tareas y marca una tarea pendiente o en progreso como completada mediante un control en la propia fila del listado. El cambio se refleja de inmediato en la fila (estado actualizado) sin recargar la página completa, y queda confirmado por el sistema.

**Why this priority**: Es la mejora de fluidez de mayor valor diario (Should según MoSCoW y backlog): elimina recargas completas en la acción más frecuente del listado y es prerrequisito de credibilidad para el resto de interacciones dinámicas.

**Independent Test**: Puede probarse de forma aislada abriendo el listado con al menos una tarea no completada, accionando el control de completar y verificando que el estado visible cambia sin recarga completa y que tras recargar manualmente la página el estado completado persiste.

**Acceptance Scenarios**:

1. **Given** un usuario autenticado con una tarea en estado pendiente o en progreso visible en el listado, **When** acciona el control de completar de esa tarea, **Then** la fila muestra la tarea como completada sin recargar la página completa y el cambio persiste al recargar.
2. **Given** un usuario autenticado que acaba de accionar completar sobre una tarea, **When** el sistema confirma la operación, **Then** la tarea deja de aparecer bajo el filtro de pendientes (si el filtro está activo) o refleja su nuevo estado en el listado actual.
3. **Given** un usuario autenticado que acciona completar sobre una tarea, **When** la petición al sistema falla (p. ej. error de red, sesión expirada, transición no permitida), **Then** la interfaz revierte el cambio visual al estado anterior y muestra un mensaje de error comprensible, sin dejar la fila en un estado no confirmado.
4. **Given** un usuario que intenta completar una tarea ya completada o eliminada, **When** acciona el control correspondiente, **Then** el sistema no produce un cambio de estado inválido e informa del resultado (mensaje o ausencia de acción duplicada).

---

### User Story 2 - Reordenar tareas arrastrando y soltando (HU-16) (Priority: P2)

Un usuario autenticado reordena su listado de tareas arrastrando una fila y soltándola en una nueva posición. El listado muestra el nuevo orden inmediatamente y el sistema lo conserva, de modo que al recargar la página el orden se mantiene.

**Why this priority**: Es una mejora de organización visual (Could según MoSCoW): aporta valor de priorización personal pero no altera el dominio central; depende de que el listado base exista y es demostrable de forma independiente de HU-15.

**Independent Test**: Puede probarse de forma aislada abriendo el listado con al menos tres tareas, arrastrando una a otra posición, soltándola y verificando visualmente el nuevo orden; tras recargar la página, el orden se mantiene idéntico.

**Acceptance Scenarios**:

1. **Given** un usuario autenticado con al menos dos tareas visibles en el listado, **When** arrastra una tarea a una nueva posición y la suelta, **Then** el listado muestra inmediatamente el nuevo orden y tras recargar la página el orden persiste.
2. **Given** un usuario que ha reordenado sus tareas, **When** otro usuario autenticado distinto consulta su propio listado, **Then** el orden del segundo usuario no se ve afectado (el orden es personal por usuario).
3. **Given** un usuario que arrastra una tarea pero la suelta fuera de una posición válida (o cancela el arrastre), **When** termina la interacción, **Then** el listado conserva el orden anterior sin cambios persistidos ni errores.

---

### Edge Cases

- ¿Qué ocurre cuando la petición de completar falla a mitad de una secuencia rápida de clics sobre la misma tarea (doble accionamiento)? El sistema debe evitar estados duplicados o contradictorios: solo un cambio confirmado prevalece y la interfaz refleja el estado confirmado.
- ¿Cómo se comporta el listado si la sesión expira justo al completar o reordenar? La interfaz revierte/mantiene el estado anterior y comunica que es necesario volver a iniciar sesión, sin mostrar un éxito falso.
- ¿Qué ocurre si el usuario intenta completar una tarea que otro flujo ya eliminó o que no le pertenece? La operación se rechaza, la fila refleja la realidad (mensaje y/o actualización del listado) y no se muestra un estado falso.
- ¿Cómo se maneja el reordenamiento cuando la persistencia del nuevo orden falla (error de red o validación)? El listado revierte al orden anterior confirmado y muestra un mensaje de error.
- ¿Qué ocurre con tareas nuevas creadas después de un reordenamiento personalizado? Aparecen en una posición determinista y documentada (p. ej. al final del orden personal) sin romper el orden previamente guardado.
- ¿Cómo se comporta el arrastre con listados filtrados (por estado) o con una sola tarea visible? El reordenamiento solo aplica al conjunto visible cuando tiene sentido; con una sola tarea no hay cambio observable ni error.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El sistema MUST permitir al usuario marcar una tarea propia no completada como completada directamente desde el listado, sin recargar la página completa. La acción rápida acepta tanto pendiente→completada como en progreso→completada en un solo gesto (salto directo aclarado 2026-10-11).
- **FR-002**: El sistema MUST reflejar el nuevo estado de la tarea en la fila del listado inmediatamente solo como estado provisional hasta recibir confirmación, y como estado definitivo tras la confirmación.
- **FR-003**: Si la operación de completar no es confirmada por el sistema (fallo de red, error del servidor, transición no permitida, falta de autorización), el sistema MUST revertir automáticamente la fila a su estado anterior y MUST mostrar un mensaje de error comprensible al usuario.
- **FR-004**: El sistema MUST impedir que la interfaz muestre de forma estable un estado de tarea que no haya sido confirmado (nunca estado falso confirmado).
- **FR-005**: El sistema MUST reutilizar para HU-15 exclusivamente el contrato de cambio de estado ya definido en incrementos anteriores; no se introduce ninguna operación nueva de completado.
- **FR-006**: El sistema MUST permitir al usuario reordenar visualmente sus tareas del listado mediante arrastrar y soltar.
- **FR-007**: El sistema MUST mostrar el nuevo orden inmediatamente tras soltar el elemento arrastrado.
- **FR-008**: El sistema MUST persistir el nuevo orden de tareas inmediatamente después de soltar el elemento, de modo que una recarga posterior de la página muestre el mismo orden. El orden manual aplica a la vista filtrada actual (orden por vista aclarado 2026-10-11) y no altera el orden de otras vistas.
- **FR-009**: El sistema MUST mantener el orden de forma personal por usuario: el reordenamiento de un usuario no altera el orden visible de ningún otro usuario.
- **FR-010**: Si la persistencia del nuevo orden falla, el sistema MUST revertir el listado al orden anterior confirmado y MUST mostrar un mensaje de error comprensible.
- **FR-011**: Cada tarea MUST poseer una posición de orden persistente que determine su lugar en el listado del propietario; toda tarea nueva recibe una posición determinista sin romper el orden existente. Regla aclarada 2026-10-11: las tareas nuevas aparecen al final del orden y las tareas completadas conservan su posición.
- **FR-012**: Toda mutación introducida o reutilizada por este incremento (cambio de estado, cambio de orden) MUST quedar registrada en el log de auditoría estructurado con actor, acción, entidad y marca temporal, conforme a la constitución. Aclarado 2026-10-11: cada persistencia del orden manual genera su registro de auditoría.
- **FR-013**: Toda operación de completar o reordenar MUST verificar en el servidor que el solicitante está autenticado y autorizado sobre la tarea (propietario o asignado con permiso), sin confiar en controles solo visibles u ocultos en el cliente.
- **FR-014**: Las entradas asociadas a completar y reordenar MUST validarse en el servidor (identidad de la tarea, transición de estado permitida, posiciones de orden válidas) e ignorar valores manipulados desde el cliente.
- **FR-015**: La interacción dinámica MUST degradarse de forma segura sin funcionalidad extendida del navegador: el usuario siempre puede completar y consultar sus tareas mediante el flujo base con recarga, y el arrastre no es la única vía para operar el listado. Cada fila ofrece además controles de subir/bajar operables por teclado como alternativa accesible al arrastre (aclarado 2026-10-11).

### Key Entities

- **Tarea**: Trabajo pendiente del usuario; atributos relevantes para este incremento: identificador, estado del ciclo de vida (pendiente, en progreso, completada), posición de orden personal dentro del listado del propietario, propietario/asignado.
- **Orden personal del listado**: Secuencia de tareas de un usuario definida por las posiciones de orden persistentes de sus tareas; determina el orden de presentación y se conserva entre sesiones.
- **Registro de auditoría**: Evidencia de cada mutación (completado, reordenamiento) con actor, acción, entidad afectada y marca temporal.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Un usuario marca una tarea como completada desde el listado y ve el resultado sin recarga completa de la página en al menos el 95% de los intentos en condiciones normales de red.
- **SC-002**: En el 100% de los intentos fallidos de completado, la fila vuelve a su estado anterior y el usuario ve un mensaje de error (cero estados falsos confirmados en pruebas de fallo).
- **SC-003**: Un usuario reordena 5 tareas mediante arrastre y tras recargar la página el orden se conserva idéntico en el 100% de las repeticiones de la prueba.
- **SC-004**: El tiempo percibido desde que el usuario acciona completar o suelta el elemento arrastrado hasta ver el resultado visual es inferior a 2 segundos en condiciones normales de red.
- **SC-005**: El 90% de los usuarios que prueban ambas interacciones por primera vez logra completar una tarea sin recarga y reordenar el listado sin ayuda adicional.

## Assumptions

- Los incrementos 1 a 4 están implementados y sus contratos de endpoints (incluido el cambio de estado pendiente → en progreso → completada con reapertura explícita) están documentados y disponibles; este incremento no redefine dichos contratos.
- Existe autenticación con sesión activa y el concepto de tarea propia (propietario o asignado visible en su listado) según HU-02, HU-12 y HU-13.
- Cada usuario parte de un orden inicial determinista (p. ej. creación o identificador) antes de su primer reordenamiento manual; la especificación de posición inicial exacta se fija en planificación sin alterar el alcance.
- El listado base renderizado en servidor sigue disponible como degradación si la interacción dinámica no puede ejecutarse; la mejora dinámica no sustituye los flujos base.
- La interactividad se implementa dentro de la restricción de stack de la constitución (sin marcos SPA pesados salvo justificación aprobada); la elección concreta de técnica se decide en planificación.
- El único cambio estructural de persistencia admitido por esta especificación es la adición del campo de posición de orden por tarea mediante migración versionada; cualquier otro cambio de esquema queda fuera de alcance.
- Los mensajes de error son comprensibles para usuarios no técnicos y no exponen detalles internos del sistema.
- Fuera de alcance: edición en línea de otros campos, creación de tareas sin recarga, notificaciones en tiempo real entre usuarios, orden colaborativo compartido y gestos táctiles avanzados más allá del arrastre básico utilizable con puntero.

## Trazabilidad

- Historias cubiertas: HU-15 (Should, Épica 5), HU-16 (Could, Épica 5) según `.specify/memory/backlog.md`.
- Incremento: 5 de 5 (final); incrementos 1–4 asumidos como base con contratos definidos.
- Principios constitucionales aplicables: I (monolito), II (capas: presentación dinámica sobre rutas y servicios), III (contrato explícito reutilizado, sin operaciones implícitas), IV (pruebas para transiciones y orden), VI (migración versionada para el campo de orden), VII (validación y autorización en servidor), VIII (auditoría de mutaciones).
