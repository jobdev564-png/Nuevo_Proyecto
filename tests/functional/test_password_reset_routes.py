NEUTRAL = "Si el correo se encuentra registrado en el sistema, se han enviado las instrucciones de restablecimiento"


def _register(client, email="pwuser@example.com", password="Password123!"):
    return client.post(
        "/auth/register",
        data={"email": email, "password": password},
        headers={"Accept": "application/json"},
    )


def test_request_existing_and_unknown_identical(client):
    """Ambas ramas → mismo 200 neutro; nunca 404/409 (FR-012/SC-004)."""
    _register(client)
    for email in ("pwuser@example.com", "fantasma@example.com"):
        resp = client.post(
            "/auth/password-reset-request",
            json={"email": email},
            headers={"Accept": "application/json"},
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["status"] == "success"
        assert body["message"] == NEUTRAL
        assert "token" not in body.get("data", {})


def test_request_missing_email_400(client):
    """Sin campo email → 400 VALIDATION_ERROR (contrato)."""
    resp = client.post(
        "/auth/password-reset-request",
        json={},
        headers={"Accept": "application/json"},
    )
    assert resp.status_code == 400
    assert resp.get_json()["code"] == "VALIDATION_ERROR"


def _get_token_for(client, email):
    """Recupera el token vía hook de testing (solo entorno testing)."""
    from flask import current_app
    with client.application.app_context():
        svc = current_app.extensions.get("password_reset_testing")
        assert svc is not None, "hook de testing no disponible"
        return svc(email)


def test_confirm_success_and_login_with_new_password(client):
    """Confirm válido → 200 + login con nueva clave (FR-015)."""
    _register(client)
    client.post(
        "/auth/password-reset-request",
        json={"email": "pwuser@example.com"},
        headers={"Accept": "application/json"},
    )
    token = _get_token_for(client, "pwuser@example.com")

    resp = client.post(
        "/auth/password-reset-confirm",
        json={"token": token, "new_password": "NuevaClave123!"},
        headers={"Accept": "application/json"},
    )
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "success"

    login = client.post(
        "/auth/login",
        data={"email": "pwuser@example.com", "password": "NuevaClave123!"},
        headers={"Accept": "application/json"},
    )
    assert login.status_code == 200


def test_confirm_reuse_rejected(client):
    """Reutilizar token → 400 INVALID_OR_EXPIRED_TOKEN (FR-016)."""
    _register(client)
    client.post(
        "/auth/password-reset-request",
        json={"email": "pwuser@example.com"},
        headers={"Accept": "application/json"},
    )
    token = _get_token_for(client, "pwuser@example.com")
    client.post(
        "/auth/password-reset-confirm",
        json={"token": token, "new_password": "NuevaClave123!"},
        headers={"Accept": "application/json"},
    )

    resp = client.post(
        "/auth/password-reset-confirm",
        json={"token": token, "new_password": "OtraClave123!"},
        headers={"Accept": "application/json"},
    )
    assert resp.status_code == 400
    assert resp.get_json()["code"] == "INVALID_OR_EXPIRED_TOKEN"


def test_confirm_malformed_and_weak_password(client):
    """Token manipulado → INVALID_OR_EXPIRED_TOKEN; clave débil → VALIDATION_ERROR."""
    _register(client)
    client.post(
        "/auth/password-reset-request",
        json={"email": "pwuser@example.com"},
        headers={"Accept": "application/json"},
    )
    token = _get_token_for(client, "pwuser@example.com")

    bad = client.post(
        "/auth/password-reset-confirm",
        json={"token": "!!!manipulado!!!", "new_password": "NuevaClave123!"},
        headers={"Accept": "application/json"},
    )
    assert bad.status_code == 400
    assert bad.get_json()["code"] == "INVALID_OR_EXPIRED_TOKEN"

    weak = client.post(
        "/auth/password-reset-confirm",
        json={"token": token, "new_password": "corta"},
        headers={"Accept": "application/json"},
    )
    assert weak.status_code == 400
    assert weak.get_json()["code"] == "VALIDATION_ERROR"
