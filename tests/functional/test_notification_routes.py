"""Tests funcionales de rutas de notificaciones (HU-11).

TDD (Principio IV): deben FALLAR antes de implementar el blueprint
/notifications (GET, POST /<id>/read, POST /read-all).
"""


def _login_as(client, email="user@example.com", password="Password123!"):
    client.post(
        "/auth/register",
        data={"email": email, "password": password},
        headers={"Accept": "application/json"},
    )
    client.post(
        "/auth/login",
        data={"email": email, "password": password},
        headers={"Accept": "application/json"},
    )


def _assign_to(client, email, title="Preparar informe"):
    res = client.post(
        "/tasks",
        json={"title": title},
        headers={"Accept": "application/json"},
    )
    assert res.status_code == 201, res.get_json()
    task_id = res.get_json()["data"]["id"]
    res = client.post(
        f"/tasks/{task_id}/assign",
        json={"email": email},
        headers={"Accept": "application/json"},
    )
    assert res.status_code == 200, res.get_json()
    return task_id


def test_notifications_require_session(client):
    """Sin sesión, los endpoints de notificaciones responden 401."""
    assert client.get(
        "/notifications", headers={"Accept": "application/json"}
    ).status_code == 401
    assert client.post(
        "/notifications/1/read", headers={"Accept": "application/json"}
    ).status_code == 401
    assert client.post(
        "/notifications/read-all", headers={"Accept": "application/json"}
    ).status_code == 401


def test_list_notifications_with_unread_count(client):
    """GET /notifications expone items + unread_count tras asignación."""
    _login_as(client, "notifa@ejemplo.com")
    client.post(
        "/auth/register",
        data={"email": "notifb@ejemplo.com", "password": "Password123!"},
        headers={"Accept": "application/json"},
    )
    _assign_to(client, "notifb@ejemplo.com")
    client.post(
        "/auth/login",
        data={"email": "notifb@ejemplo.com", "password": "Password123!"},
        headers={"Accept": "application/json"},
    )
    res = client.get(
        "/notifications", headers={"Accept": "application/json"}
    )
    assert res.status_code == 200
    body = res.get_json()["data"]
    assert body["unread_count"] == 1
    assert len(body["notifications"]) == 1
    item = body["notifications"][0]
    assert item["is_read"] is False
    assert item["assigned_by_email"] == "notifa@ejemplo.com"
    assert item["task_id"] is not None


def test_mark_one_as_read_persists(client):
    """POST /<id>/read marca leída; persiste visible y baja el contador."""
    _login_as(client, "leida@ejemplo.com")
    client.post(
        "/auth/register",
        data={"email": "leidab@ejemplo.com", "password": "Password123!"},
        headers={"Accept": "application/json"},
    )
    _assign_to(client, "leidab@ejemplo.com")
    client.post(
        "/auth/login",
        data={"email": "leidab@ejemplo.com", "password": "Password123!"},
        headers={"Accept": "application/json"},
    )
    nid = client.get(
        "/notifications", headers={"Accept": "application/json"}
    ).get_json()["data"]["notifications"][0]["id"]
    res = client.post(
        f"/notifications/{nid}/read",
        headers={"Accept": "application/json"},
    )
    assert res.status_code == 200
    assert res.get_json()["data"]["is_read"] is True
    body = client.get(
        "/notifications", headers={"Accept": "application/json"}
    ).get_json()["data"]
    assert body["unread_count"] == 0
    assert len(body["notifications"]) == 1
    assert body["notifications"][0]["is_read"] is True


def test_mark_read_html_redirects(client):
    """Rama HTML de marcar leída: 302 hacia /notifications."""
    _login_as(client, "rhtmla@ejemplo.com")
    client.post(
        "/auth/register",
        data={"email": "rhtmlb@ejemplo.com", "password": "Password123!"},
    )
    _assign_to(client, "rhtmlb@ejemplo.com")
    client.post(
        "/auth/login",
        data={"email": "rhtmlb@ejemplo.com", "password": "Password123!"},
    )
    nid = client.get(
        "/notifications", headers={"Accept": "application/json"}
    ).get_json()["data"]["notifications"][0]["id"]
    res = client.post(f"/notifications/{nid}/read")
    assert res.status_code == 302
    assert "/notifications" in res.headers["Location"]


def test_mark_all_as_read(client):
    """POST /read-all marca pendientes en lote con marked_count."""
    _login_as(client, "alla@ejemplo.com")
    client.post(
        "/auth/register",
        data={"email": "allb@ejemplo.com", "password": "Password123!"},
        headers={"Accept": "application/json"},
    )
    _assign_to(client, "allb@ejemplo.com", "T1")
    _assign_to(client, "allb@ejemplo.com", "T2")
    client.post(
        "/auth/login",
        data={"email": "allb@ejemplo.com", "password": "Password123!"},
        headers={"Accept": "application/json"},
    )
    res = client.post(
        "/notifications/read-all", headers={"Accept": "application/json"}
    )
    assert res.status_code == 200
    assert res.get_json()["data"]["marked_count"] == 2
    body = client.get(
        "/notifications", headers={"Accept": "application/json"}
    ).get_json()["data"]
    assert body["unread_count"] == 0
    assert len(body["notifications"]) == 2


def test_mark_foreign_notification_404(client):
    """Leer notificación ajena: 404 NOTIFICATION_NOT_FOUND."""
    _login_as(client, "extranaa@ejemplo.com")
    client.post(
        "/auth/register",
        data={"email": "extranab@ejemplo.com", "password": "Password123!"},
        headers={"Accept": "application/json"},
    )
    client.post(
        "/auth/register",
        data={"email": "extranac@ejemplo.com", "password": "Password123!"},
        headers={"Accept": "application/json"},
    )
    _assign_to(client, "extranab@ejemplo.com")
    client.post(
        "/auth/login",
        data={"email": "extranac@ejemplo.com", "password": "Password123!"},
        headers={"Accept": "application/json"},
    )
    res = client.post(
        "/notifications/1/read", headers={"Accept": "application/json"}
    )
    assert res.status_code == 404
    assert res.get_json()["code"] == "NOTIFICATION_NOT_FOUND"
