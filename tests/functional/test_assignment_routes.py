"""Tests funcionales de rutas de asignación y listado con origin (HU-10).

TDD (Principio IV): deben FALLAR antes de implementar
POST /tasks/<id>/assign y GET /tasks?origin=.
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


def _create_task(client, title="Preparar informe"):
    res = client.post(
        "/tasks",
        json={"title": title},
        headers={"Accept": "application/json"},
    )
    assert res.status_code == 201, res.get_json()
    return res.get_json()["data"]["id"]


def test_assign_requires_session(client):
    """Sin sesión, asignar responde 401."""
    res = client.post(
        "/tasks/1/assign",
        json={"email": "b@ejemplo.com"},
        headers={"Accept": "application/json"},
    )
    assert res.status_code == 401


def test_assign_success_json(client):
    """Asignación exitosa: 200 con nuevo responsable y auditoría implícita."""
    _login_as(client, "asigna@ejemplo.com")
    client.post(
        "/auth/register",
        data={"email": "destino@ejemplo.com", "password": "Password123!"},
        headers={"Accept": "application/json"},
    )
    task_id = _create_task(client)
    res = client.post(
        f"/tasks/{task_id}/assign",
        json={"email": "destino@ejemplo.com"},
        headers={"Accept": "application/json"},
    )
    assert res.status_code == 200, res.get_json()
    body = res.get_json()
    assert body["status"] == "success"
    assert body["data"]["id"] == task_id
    assert body["data"]["assigned_to_email"] == "destino@ejemplo.com"
    assert body["data"]["new_owner_id"] != body["data"]["previous_owner_id"]


def test_assign_success_html_redirects(client):
    """Rama HTML: 302 hacia /tasks con flash."""
    _login_as(client, "asignahtml@ejemplo.com")
    client.post(
        "/auth/register",
        data={"email": "destinohtml@ejemplo.com", "password": "Password123!"},
    )
    task_id = _create_task(client)
    res = client.post(
        f"/tasks/{task_id}/assign",
        data={"email": "destinohtml@ejemplo.com"},
    )
    assert res.status_code == 302
    assert "/tasks" in res.headers["Location"]


def test_assign_unregistered_email_404(client):
    """Correo no registrado: 404 USER_NOT_FOUND."""
    _login_as(client, "rechazo@ejemplo.com")
    task_id = _create_task(client)
    res = client.post(
        f"/tasks/{task_id}/assign",
        json={"email": "fantasma@ejemplo.com"},
        headers={"Accept": "application/json"},
    )
    assert res.status_code == 404
    assert res.get_json()["code"] == "USER_NOT_FOUND"


def test_assign_foreign_or_deleted_404(client):
    """Tarea ajena o eliminada: 404 TASK_NOT_FOUND sin distinguir."""
    _login_as(client, "propietaria@ejemplo.com")
    task_id = _create_task(client)
    client.post(
        "/auth/register",
        data={"email": "ajena@ejemplo.com", "password": "Password123!"},
        headers={"Accept": "application/json"},
    )
    client.post(
        "/auth/login",
        data={"email": "ajena@ejemplo.com", "password": "Password123!"},
        headers={"Accept": "application/json"},
    )
    res = client.post(
        f"/tasks/{task_id}/assign",
        json={"email": "propietaria@ejemplo.com"},
        headers={"Accept": "application/json"},
    )
    assert res.status_code == 404
    assert res.get_json()["code"] == "TASK_NOT_FOUND"


def test_assign_to_self_400(client):
    """Auto-asignación: 400 ASSIGN_TO_SELF."""
    _login_as(client, "auto@ejemplo.com")
    task_id = _create_task(client)
    res = client.post(
        f"/tasks/{task_id}/assign",
        json={"email": "auto@ejemplo.com"},
        headers={"Accept": "application/json"},
    )
    assert res.status_code == 400
    assert res.get_json()["code"] == "ASSIGN_TO_SELF"


def test_assign_invalid_email_400(client):
    """Email ausente o malformado: 400 VALIDATION_ERROR."""
    _login_as(client, "formato@ejemplo.com")
    task_id = _create_task(client)
    res = client.post(
        f"/tasks/{task_id}/assign",
        json={"email": "no-es-email"},
        headers={"Accept": "application/json"},
    )
    assert res.status_code == 400
    assert res.get_json()["code"] == "VALIDATION_ERROR"


def test_tasks_origin_filter_and_compatibility(client):
    """GET /tasks?origin= clasifica; sin origin o inválido ≡ all."""
    _login_as(client, "origena@ejemplo.com")
    client.post(
        "/auth/register",
        data={"email": "origenb@ejemplo.com", "password": "Password123!"},
        headers={"Accept": "application/json"},
    )
    delegated_id = _create_task(client, "Delegada")
    client.post(
        f"/tasks/{delegated_id}/assign",
        json={"email": "origenb@ejemplo.com"},
        headers={"Accept": "application/json"},
    )
    client.post(
        "/auth/login",
        data={"email": "origenb@ejemplo.com", "password": "Password123!"},
        headers={"Accept": "application/json"},
    )
    own_id = _create_task(client, "Propia")

    def _ids(origin=None):
        url = "/tasks"
        if origin is not None:
            url += f"?origin={origin}"
        res = client.get(url, headers={"Accept": "application/json"})
        assert res.status_code == 200
        return {t["id"] for t in res.get_json()["data"]["tasks"]}

    assert _ids("assigned") == {delegated_id}
    assert _ids("mine") == {own_id}
    assert _ids("all") == {delegated_id, own_id}
    assert _ids() == {delegated_id, own_id}
    assert _ids("bogus") == {delegated_id, own_id}


def test_assignee_item_exposes_assignment_fields(client):
    """El item asignado expone created_by/assigned/assigned_by_email."""
    _login_as(client, "exponea@ejemplo.com")
    client.post(
        "/auth/register",
        data={"email": "exponeb@ejemplo.com", "password": "Password123!"},
        headers={"Accept": "application/json"},
    )
    task_id = _create_task(client, "Con campos")
    client.post(
        f"/tasks/{task_id}/assign",
        json={"email": "exponeb@ejemplo.com"},
        headers={"Accept": "application/json"},
    )
    client.post(
        "/auth/login",
        data={"email": "exponeb@ejemplo.com", "password": "Password123!"},
        headers={"Accept": "application/json"},
    )
    res = client.get(
        "/tasks?origin=assigned", headers={"Accept": "application/json"}
    )
    items = res.get_json()["data"]["tasks"]
    assert len(items) == 1
    assert items[0]["assigned"] is True
    assert items[0]["assigned_by_email"] == "exponea@ejemplo.com"
