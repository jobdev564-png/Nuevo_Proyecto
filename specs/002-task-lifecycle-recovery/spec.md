# Feature Specification: 002-task-lifecycle-recovery

**Feature Branch**: `002-task-lifecycle-recovery`

**Created**: 2026-10-01

**Status**: Draft

**Input**: User description: "Especifica el segundo incremento funcional de TaskControl: cierre de la gestión básica de tareas y recuperación de acceso. Este incremento cubre HU-05, HU-06 y HU-14 del backlog, y asume que el Incremento 1 (registro, login/logout, creación, listado, cambio de estado y edición de tareas) ya está implementado y en producción."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Eliminación Lógica de Tareas (HU-05) (Priority: P1)

Como usuario autenticado, quiero eliminar una tarea propia que ya no es relevante, de modo que desaparezca de mi listado habitual sin que se borre físicamente el registro ni se pierda su historial de auditoría.

**Why this priority**: Completa el ciclo de vida básico de la tarea permitiendo mantener el listado organizado y sin elementos descartados, al tiempo que cumple de forma estricta con el Principio VI de la constitución del proyecto preservando la integridad referencial y el histórico inmutable de auditoría.

**Independent Test**: Puede probarse creando una tarea, ejecutando la solicitud de eliminación y comprobando que la tarea ya no aparezca en el listado principal del usuario, al tiempo que se verifica en la base de datos que el registro persiste con su marca de eliminación lógica y que se ha generado un evento de auditoría con la acción `TASK_DELETED`.

**Acceptance Scenarios**:

1. **Given** un usuario autenticado con una tarea activa propia en su listado, **When** el usuario confirma la eliminación de la tarea, **Then** la tarea es marcada como eliminada lógicamente, deja de listarse en la vista principal de tareas y se genera un registro en el log de auditoría con actor, acción `TASK_DELETED`, identificador de la tarea y timestamp UTC.
2. **Given** una tarea propia que ya fue eliminada lógicamente con anterioridad, **When** se intenta solicitar nuevamente su eliminación, **Then** el sistema rechaza la solicitud indicando que la tarea ya está eliminada o no se encuentra disponible, impidiendo duplicación de auditoría o mutaciones inválidas.
3. **Given** un usuario autenticado intentando eliminar una tarea que pertenece a otro usuario, **When** envía la solicitud de eliminación, **Then** el sistema rechaza la operación por falta de autorización (código 403 Forbidden o 404 Not Found) y la tarea ajena permanece inalterada.
4. **Given** una tarea eliminada lógicamente, **When** se examina la persistencia del sistema, **Then** el registro de la tarea y todos los eventos previos asociados en el log de auditoría se conservan intactos sin borrado físico.
5. **Given** una tarea eliminada lógicamente, **When** el usuario intenta editar sus datos o cambiar su estado mediante acciones ordinarias, **Then** el sistema rechaza la operación informando que no se pueden modificar tareas eliminadas.

---

### User Story 2 - Reapertura de Tareas Completadas (HU-06) (Priority: P2)

Como usuario autenticado, quiero reabrir una tarea que había marcado como completada por error, para reactivarla en mi flujo de trabajo sin perder su historial y dejando trazabilidad explícita de la reapertura.

**Why this priority**: Proporciona tolerancia a errores humanos operativos en el seguimiento de tareas, asegurando trazabilidad formal bajo el Principio VIII de la constitución al distinguir de manera inequívoca una reapertura de una creación inicial o de un cambio de estado ordinario.

**Independent Test**: Puede probarse completando una tarea propia, ejecutando la acción de reapertura y verificando que su estado retorne a activo ("pendiente") y que en el log de auditoría figure una entrada específica con la acción `TASK_REOPENED`.

**Acceptance Scenarios**:

1. **Given** un usuario autenticado con una tarea propia en estado "completada", **When** el usuario solicita reabrir la tarea, **Then** el estado de la tarea cambia a "pendiente" (activo), vuelve a aparecer como pendiente en el listado y se registra en auditoría un evento con acción `TASK_REOPENED`.
2. **Given** una tarea en estado "pendiente" o "en progreso", **When** el usuario intenta ejecutar la acción de reapertura, **Then** el sistema deniega la acción indicando que solo las tareas completadas son susceptibles de ser reabiertas.
3. **Given** una tarea que fue eliminada lógicamente, **When** se intenta reabrir, **Then** el sistema bloquea la acción impidiendo reactivar tareas eliminadas.
4. **Given** una tarea completada perteneciente a otro usuario, **When** un usuario intenta reabrirla, **Then** el sistema deniega la operación con error de autorización (403 Forbidden o 404 Not Found) sin alterar el estado de la tarea ajena.

---

### User Story 3 - Recuperación Segura de Contraseña (HU-14) (Priority: P1)

Como usuario que ha olvidado su contraseña, quiero solicitar el restablecimiento mediante mi correo electrónico registrado, recibiendo un mecanismo temporal y seguro de recuperación que no permita reutilizaciones y sin que el sistema filtre qué correos existen registrados.

**Why this priority**: Es crítico para la autonomía del usuario y la continuidad del acceso a la plataforma. Cumple con el Principio VII (Seguridad por defecto), protegiendo la privacidad de los usuarios registrados frente a ataques de enumeración y asegurando credenciales de un solo uso con caducidad estricta.

**Independent Test**: Puede probarse solicitando la recuperación con un correo existente y con uno inexistente, verificando que la respuesta visible sea idéntica y no discriminatoria. Para el correo existente, se utiliza el enlace/token recibido para cambiar la contraseña, verificando que la nueva contraseña funcione para iniciar sesión, que el token quede invalidado tras el primer uso y que se rechace si está expirado o ya consumido.

**Acceptance Scenarios**:

1. **Given** un usuario en el formulario de recuperación de contraseña que introduce un correo registrado en el sistema, **When** envía la solicitud, **Then** el sistema genera un token de un solo uso con expiración (60 minutos), registra el evento `PASSWORD_RESET_REQUESTED` y presenta un mensaje neutral confirmando el envío de instrucciones sin revelar la existencia previa del correo.
2. **Given** una persona que introduce un correo no registrado en el sistema, **When** envía la solicitud de recuperación, **Then** el sistema no genera token ni envía mensaje, pero presenta exactamente el mismo mensaje neutral y tiempo de respuesta homogéneo que si el correo existiera, imposibilitando la enumeración de cuentas.
3. **Given** un token de recuperación válido y vigente, **When** el usuario ingresa una nueva contraseña que cumple con los requisitos mínimos de seguridad, **Then** la contraseña se almacena de forma segura (hasheada), el token se invalida de inmediato impidiendo reutilización, se registra en auditoría `PASSWORD_RESET_COMPLETED` y el usuario puede iniciar sesión con la nueva credencial.
4. **Given** un token de recuperación que ya fue consumido exitosamente en un restablecimiento previo, **When** se intenta utilizar nuevamente dicho token, **Then** el sistema rechaza la solicitud indicando que el enlace es inválido o ya fue utilizado.
5. **Given** un token de recuperación cuya vigencia ha expirado (más de 60 minutos), **When** se intenta utilizar para cambiar la contraseña, **Then** el sistema rechaza la solicitud indicando que el enlace ha expirado y requiere una nueva solicitud.
6. **Given** un usuario que solicita múltiples veces restablecer su contraseña, **When** se genera un nuevo token de recuperación, **Then** los tokens generados con anterioridad para ese mismo usuario quedan automáticamente invalidados.

---

### Edge Cases

- **Enumeración de usuarios por temporización o respuesta HTTP**: La respuesta visible y el código HTTP ante solicitudes de recuperación de contraseña deben ser estrictamente idénticos para correos existentes e inexistentes, evitando diferencias medibles de tiempo que permitan inferir la existencia del usuario.
- **Tokens manipulados, truncados o vacíos**: Cualquier token con formato incorrecto, caracteres inesperados o manipulado maliciosamente debe ser rechazado de forma segura sin producir errores internos no controlados ni divulgar trazas del sistema.
- **Intentos de reapertura concurrente**: Si dos peticiones simultáneas intentan reabrir la misma tarea completada, solo una debe registrar el evento `TASK_REOPENED` y la otra debe manejarse limpiamente indicando que la tarea ya no está completada.
- **Acciones sobre tareas eliminadas (soft deleted)**: Cualquier petición de lectura por identificador directo, edición (`HU-04`), cambio de estado ordinario (`HU-03`) o reapertura (`HU-06`) sobre una tarea con eliminación lógica debe ser rechazada (código 404 Not Found o 400 Bad Request) para usuarios estándar.
- **Invalidación de sesiones previas tras restablecimiento**: Cuando un usuario restablece su contraseña con éxito, cualquier sesión web activa previamente para dicha cuenta debe ser invalidada para evitar accesos indebidos de sesiones abiertas en otros navegadores o dispositivos.
- **Formato y validación de nueva contraseña**: La validación de longitud y fortaleza de la contraseña en el restablecimiento debe ser idéntica a la aplicada durante el registro de usuarios (`HU-12`).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El sistema DEBE permitir a un usuario autenticado solicitar la eliminación de cualquiera de sus tareas propias.
- **FR-002**: La eliminación de tareas DEBE implementarse de manera lógica (soft delete), preservando permanentemente el registro en la base de datos y garantizando que bajo ninguna circunstancia se ejecute un borrado físico.
- **FR-003**: El sistema DEBE excluir de forma predeterminada las tareas eliminadas lógicamente de los listados de tareas activas del usuario y de los conteos habituales de pendientes.
- **FR-004**: El sistema DEBE impedir la eliminación de una tarea que ya se encuentre previamente en estado de eliminación lógica, respondiendo con un error controlado sin alterar los datos existentes.
- **FR-005**: El sistema DEBE bloquear cualquier operación de edición de contenido (`HU-04`) y de cambio ordinario de estado (`HU-03`) sobre tareas que hayan sido eliminadas lógicamente.
- **FR-006**: El sistema DEBE registrar en el log de auditoría un evento con acción `TASK_DELETED` ante cada eliminación lógica de tarea, registrando el identificador del usuario actor, la entidad afectada y la marca temporal UTC.
- **FR-007**: El sistema DEBE permitir a un usuario autenticado reabrir una tarea propia que se encuentre en estado "completada".
- **FR-008**: Al reabrir una tarea completada, el sistema DEBE actualizar su estado al estado activo inicial ("pendiente").
- **FR-009**: El sistema DEBE registrar en el log de auditoría un evento con la acción explícita `TASK_REOPENED`, diferenciándolo claramente tanto de la creación inicial de la tarea (`TASK_CREATED`) como de un cambio de estado ordinario (`STATUS_CHANGED`).
- **FR-010**: El sistema DEBE rechazar cualquier intento de reapertura sobre tareas que no se encuentren en estado "completada" (por ejemplo, tareas en estado "pendiente", "en progreso" o eliminadas lógicamente).
- **FR-011**: El sistema DEBE permitir a cualquier usuario solicitar la recuperación de acceso mediante el ingreso de su correo electrónico.
- **FR-012**: El sistema DEBE emitir la misma respuesta neutral y genérica ("Si el correo se encuentra registrado en el sistema, se han enviado las instrucciones de restablecimiento") tanto si el correo existe como si no existe en el sistema, imposibilitando la enumeración de cuentas de usuario.
- **FR-013**: Cuando el correo pertenezca a un usuario registrado, el sistema DEBE generar un token de restablecimiento criptográficamente seguro, aleatorio, de un solo uso y con tiempo de vigencia limitado a 60 minutos.
- **FR-014**: El sistema DEBE invalidar automáticamente cualquier token de recuperación emitido previamente para el mismo usuario al generarse una nueva solicitud.
- **FR-015**: El sistema DEBE permitir a un usuario con un token de recuperación válido y vigente establecer una nueva contraseña.
- **FR-016**: El sistema DEBE invalidar de forma inmediata e irreversible el token de recuperación una vez consumido con éxito para cambiar la contraseña, asegurando que no pueda ser reutilizado.
- **FR-017**: El sistema DEBE rechazar solicitudes de restablecimiento de contraseña que utilicen tokens expirados, ya utilizados, alterados o inexistentes.
- **FR-018**: El sistema DEBE aplicar sobre la nueva contraseña exactamente las mismas validaciones de seguridad (longitud y caracteres no vacíos) requeridas en el registro de usuarios.
- **FR-019**: El sistema DEBE almacenar la nueva contraseña exclusivamente mediante un hash criptográfico seguro, sin guardar secretos o contraseñas en texto plano en ningún componente de persistencia o código.
- **FR-020**: El sistema DEBE registrar en el log de auditoría los eventos de seguridad `PASSWORD_RESET_REQUESTED` y `PASSWORD_RESET_COMPLETED`, asegurando que ningún secreto, token o contraseña sea expuesto en el registro.
- **FR-021**: El sistema DEBE validar autorización en toda operación sobre tareas, bloqueando cualquier intento de eliminar o reabrir tareas pertenecientes a otros usuarios con código de error de acceso prohibido o no encontrado.

### Exclusiones Explícitas (Fuera de Alcance)

- Asignación de prioridad a las tareas (`HU-07`).
- Clasificación de tareas en categorías o proyectos (`HU-08`).
- Detección visual y cálculo de tareas vencidas (`HU-09`).
- Asignación de tareas a otros usuarios y notificaciones internas (`HU-10`, `HU-11`).
- Completar tareas mediante llamadas asíncronas sin recarga de página (`HU-15`).
- Reordenamiento visual mediante arrastrar y soltar (drag and drop) (`HU-16`).
- Funcionalidad de papelera de reciclaje o restauración ("deshacer eliminación") de tareas eliminadas lógicamente.

### Key Entities

- **User**: Representa la identidad y cuenta del usuario en la plataforma.
  - Atributos clave: Identificador único (`id`), correo electrónico (`email`), contraseña almacenada en hash seguro (`password_hash`), fecha y hora de creación (`created_at`).
  - Relaciones: Posee múltiples tareas (`Task`), registros de auditoría (`AuditLog`) y tokens de restablecimiento (`PasswordResetToken`).
- **Task**: Representa la unidad de trabajo gestionada por el usuario.
  - Atributos clave: Identificador único (`id`), referencia al usuario propietario (`user_id`), título (`title`), descripción (`description`), fecha límite (`due_date`), estado del ciclo de vida (`status`: `pending`, `in_progress`, `completed`), indicador de eliminación lógica (`is_deleted`), fecha y hora de eliminación lógica (`deleted_at`), marcas de tiempo de creación y actualización (`created_at`, `updated_at`).
  - Relaciones: Pertenece a un `User`, está asociada a múltiples registros de `AuditLog`.
- **AuditLog**: Registro inmutable de eventos del sistema para observabilidad y trazabilidad (Principio VIII).
  - Atributos clave: Identificador único (`id`), actor que ejecutó la acción (`actor_id`), nombre unívoco de la acción ejecutada (`action`: `TASK_CREATED`, `STATUS_CHANGED`, `TASK_UPDATED`, `TASK_DELETED`, `TASK_REOPENED`, `PASSWORD_RESET_REQUESTED`, `PASSWORD_RESET_COMPLETED`), entidad afectada (`entity_id`), marca de tiempo en UTC (`timestamp`), detalles estructurados no confidenciales (`details`).
- **PasswordResetToken**: Credencial temporal de un solo uso para la recuperación de acceso.
  - Atributos clave: Identificador único (`id`), referencia al usuario (`user_id`), hash de verificación del token de recuperación (`token_hash`), fecha y hora de expiración (`expires_at`), fecha y hora de consumo efectivo (`used_at`), fecha y hora de generación (`created_at`).
  - Relaciones: Pertenece a un `User`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: El 100% de las tareas eliminadas desaparecen inmediatamente del listado visible por defecto del usuario, manteniéndose el 100% de sus registros físicos e historial en base de datos.
- **SC-002**: El 100% de las operaciones de eliminación lógica generan un registro de auditoría con acción `TASK_DELETED` y los 4 campos obligatorios (`actor_id`, `action`, `entity_id`, `timestamp`).
- **SC-003**: En el 100% de las reaperturas de tareas completadas, el sistema genera un registro de auditoría con la acción unívoca `TASK_REOPENED`, logrando una diferenciación del 100% respecto a creaciones (`TASK_CREATED`) y transiciones comunes (`STATUS_CHANGED`).
- **SC-004**: Tasa de fuga de información de correos registrados en recuperación de contraseña = 0% (el mensaje y tiempo de respuesta visible no permiten diferenciar correos existentes de inexistentes).
- **SC-005**: El 100% de los tokens de recuperación quedan completamente invalidados tras su primer uso exitoso o una vez transcurridos 60 minutos desde su generación (0% de reutilización permitida).
- **SC-006**: Cero almacenamiento o registro de credenciales o tokens en texto plano en la base de datos o en los registros de auditoría (100% de apego al Principio VII).
- **SC-007**: El 100% de las peticiones para eliminar o reabrir tareas de terceros son rechazadas sin filtrar datos ni alterar el estado original.

## Assumptions

- El tiempo estándar de expiración para los tokens de restablecimiento de contraseña es de 60 minutos contados a partir de su generación.
- La reapertura de una tarea completada devuelve la tarea al estado activo inicial ("pendiente").
- En entornos locales o de desarrollo sin servicio de correo externo configurado, la emisión del token o enlace de recuperación puede ser simulada o registrada en la consola de ejecución sin exponer secretos públicamente.
- Las tareas marcadas con eliminación lógica no disponen en este incremento de una interfaz de usuario para ser listadas ni restauradas (la restauración queda fuera de alcance para futuros incrementos si se requiere).
- Las reglas de validación de contraseñas para el restablecimiento son las mismas que para el registro de usuarios implementado en el Incremento 1.
