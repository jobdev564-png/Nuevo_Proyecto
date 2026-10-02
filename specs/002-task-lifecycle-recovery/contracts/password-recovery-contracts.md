# Contratos HTTP: Recuperación de contraseña (HU-14)

**Blueprint**: `auth_bp` (`/auth`) — extiende `specs/001-basic-tasks-auth/contracts/auth-contracts.md` sin modificarlo.
**Rutas públicas** (sin sesión). Principio VII: validación en backend, hash seguro, cero secretos en BD/logs.
**Correo en desarrollo**: simulado por `logging` (ver `research.md` R-04); el contrato no expone el token en ninguna respuesta HTTP.

---

## 1. Solicitar restablecimiento

### `POST /auth/password-reset-request`

- **Método**: `POST`
- **Ruta**: `/auth/password-reset-request`
- **Autenticación**: pública.
- **Headers**: `Content-Type: application/json` o `application/x-www-form-urlencoded`.
- **Payload entrada**:
  ```json
  { "email": "usuario@ejemplo.com" }
  ```
  Validación: formato email básico; si el formato es inválido se responde igual que si fuera válido (neutralidad total) salvo cuerpo ausente → `400 VALIDATION_ERROR` solo cuando falta el campo `email` por completo.
- **Efecto si el correo existe**: genera `PasswordResetToken` (60 min, un solo uso, invalida previos) + `AuditLog(PASSWORD_RESET_REQUESTED)` sin secretos + emite enlace simulado por log del servidor.
- **Efecto si no existe**: ningún token, ningún correo, ninguna auditoría con PII.
- **Respuestas (idénticas exista o no)**:
  - `200 OK` (JSON) / `200` + render de confirmación (HTML):
    ```json
    { "status": "success", "message": "Si el correo se encuentra registrado en el sistema, se han enviado las instrucciones de restablecimiento" }
    ```
  - `400 Bad Request` — solo si falta el campo `email`:
    ```json
    { "status": "error", "code": "VALIDATION_ERROR", "message": "El correo electrónico es obligatorio" }
    ```
- **Anti-enumeración**: mismo código, mismo mensaje y misma forma de respuesta en ambos casos; no se devuelve `404` ni `409` nunca en este endpoint.

---

## 2. Confirmar restablecimiento con token

### `POST /auth/password-reset-confirm`

- **Método**: `POST`
- **Ruta**: `/auth/password-reset-confirm`
- **Autenticación**: pública (el token es la credencial).
- **Payload entrada**:
  ```json
  { "token": "<token_urlsafe_recibido_por_correo_o_log>", "new_password": "NuevaClave123!" }
  ```
  Validaciones backend: `token` no vacío (cualquier formato malformado → `INVALID_OR_EXPIRED_TOKEN`, nunca 500); `new_password` con las mismas reglas que registro (mínimo 8 caracteres, no vacía).
- **Efecto en éxito**: `user.password_hash` actualizado (hash seguro) + `token.used_at=now` (irreversible) + `AuditLog(PASSWORD_RESET_COMPLETED)` sin secretos + invalidación de sesión previa (el blueprint limpia `session`; si se usa sesión server-side, rotarla).
- **Respuestas**:
  - `200 OK`:
    ```json
    { "status": "success", "message": "Contraseña restablecida correctamente. Inicia sesión con tu nueva contraseña", "data": { "email": "usuario@ejemplo.com" } }
    ```
  - `400 Bad Request` — token inválido/expirado/consumido/manipulado:
    ```json
    { "status": "error", "code": "INVALID_OR_EXPIRED_TOKEN", "message": "El enlace es inválido, ya fue utilizado o ha expirado" }
    ```
  - `400 Bad Request` — contraseña débil:
    ```json
    { "status": "error", "code": "VALIDATION_ERROR", "message": "La contraseña debe tener al menos 8 caracteres" }
    ```
  - `410 Gone` (alternativa admisible): si el equipo prefiere distinguir expirado de inválido a nivel HTTP, usar `410` con el mismo `code`. El plan acepta `400` como canónico para simplicidad (YAGNI); no exponer si expiró vs. consumido en el mensaje (evita oráculo).
- **Seguridad**: límite de intentos por IP opcional (fuera de alcance MVP); no loguear `token` ni `new_password` en ningún nivel.
