def _login_as(client, email="lifecycle@example.com", password="Password123!"):
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


def _create_task(client, title="Tarea ciclo de vida"):
    resp = client.post(
        "/tasks",
        data={"title": title},
        headers={"Accept": "application/json"},
    )
    assert resp.status_code == 201
    return resp.get_json()["data"]["id"]


# --- HU-05: Eliminación lógica ---

def test_delete_task_success(client):
    """POST /tasks/<id>/delete → 200 con is_deleted:true (HU-05)."""
    _login_as(client, "deluser@example.com")
    task_id = _create_task(client)

    resp = client.post(
        f"/tasks/{task_id}/delete", headers={"Accept": "application/json"}
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "success"
    assert data["data"]["id"] == task_id
    assert data["data"]["is_deleted"] is True
    assert data["data"]["deleted_at"] is not None


def test_delete_task_excluded_from_list(client):
    """Tras eliminar, GET /tasks ya no la incluye (SC-001)."""
    _login_as(client, "deluser2@example.com")
    task_id = _create_task(client)
    client.post(f"/tasks/{task_id}/delete", headers={"Accept": "application/json"})

    resp = client.get("/tasks", headers={"Accept": "application/json"})
    assert resp.status_code == 200
    ids = [t["id"] for t in resp.get_json()["data"]["tasks"]]
    assert task_id not in ids


def test_double_delete_rejected(client):
    """Segunda eliminación → 404 TASK_ALREADY_DELETED (FR-004)."""
    _login_as(client, "deluser3@example.com")
    task_id = _create_task(client)
    client.post(f"/tasks/{task_id}/delete", headers={"Accept": "application/json"})

    resp = client.post(
        f"/tasks/{task_id}/delete", headers={"Accept": "application/json"}
    )
    assert resp.status_code == 404
    assert resp.get_json()["code"] == "TASK_ALREADY_DELETED"


def test_delete_task_unauthenticated_fails(client):
    """Sin sesión → 401 (Principio VII)."""
    resp = client.post("/tasks/1/delete", headers={"Accept": "application/json"})
    assert resp.status_code == 401


def test_delete_other_user_task_rejected(client):
    """Eliminar tarea ajena → 404 sin filtrar propiedad (FR-021/SC-007)."""
    _login_as(client, "owner@example.com")
    task_id = _create_task(client)

    with client.application.test_client() as intruder:
        intruder.post(
            "/auth/register",
            data={"email": "intruder@example.com", "password": "Password123!"},
            headers={"Accept": "application/json"},
        )
        intruder.post(
            "/auth/login",
            data={"email": "intruder@example.com", "password": "Password123!"},
            headers={"Accept": "application/json"},
        )
        resp = intruder.post(
            f"/tasks/{task_id}/delete", headers={"Accept": "application/json"}
        )
        assert resp.status_code == 404
        assert resp.get_json()["code"] in ("TASK_NOT_FOUND", "TASK_ALREADY_DELETED")


def test_status_change_blocked_on_deleted(client):
    """POST /status sobre eliminada → 404/400 (FR-005)."""
    _login_as(client, "deluser4@example.com")
    task_id = _create_task(client)
    client.post(f"/tasks/{task_id}/delete", headers={"Accept": "application/json"})

    resp = client.post(
        f"/tasks/{task_id}/status",
        data={"status": "in_progress"},
        headers={"Accept": "application/json"},
    )
    assert resp.status_code in (400, 404)


# --- HU-06: Reapertura de completadas ---

def _complete_task(client, task_id):
    resp = client.post(
        f"/tasks/{task_id}/status",
        data={"status": "completed"},
        headers={"Accept": "application/json"},
    )
    assert resp.status_code == 200


def test_reopen_completed_success(client):
    """POST /tasks/<id>/reopen → 200 completed→pending (HU-06)."""
    _login_as(client, "reopenuser@example.com")
    task_id = _create_task(client)
    _complete_task(client, task_id)

    resp = client.post(
        f"/tasks/{task_id}/reopen", headers={"Accept": "application/json"}
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "success"
    assert data["data"]["previous_status"] == "completed"
    assert data["data"]["current_status"] == "pending"


def test_reopen_non_completed_rejected(client):
    """Reapertura sobre pendiente → 400 INVALID_STATE_TRANSITION (FR-010)."""
    _login_as(client, "reopenuser2@example.com")
    task_id = _create_task(client)

    resp = client.post(
        f"/tasks/{task_id}/reopen", headers={"Accept": "application/json"}
    )
    assert resp.status_code == 400
    assert resp.get_json()["code"] == "INVALID_STATE_TRANSITION"


def test_reopen_deleted_rejected(client):
    """Reapertura sobre eliminada → 404 (FR-010)."""
    _login_as(client, "reopenuser3@example.com")
    task_id = _create_task(client)
    _complete_task(client, task_id)
    client.post(f"/tasks/{task_id}/delete", headers={"Accept": "application/json"})

    resp = client.post(
        f"/tasks/{task_id}/reopen", headers={"Accept": "application/json"}
    )
    assert resp.status_code == 404


def test_status_from_completed_still_blocked(client):
    """POST /status pending desde completed → sigue 400 (contrato Inc.1)."""
    _login_as(client, "reopenuser4@example.com")
    task_id = _create_task(client)
    _complete_task(client, task_id)

    resp = client.post(
        f"/tasks/{task_id}/status",
        data={"status": "pending"},
        headers={"Accept": "application/json"},
    )
    assert resp.status_code == 400
    assert resp.get_json()["code"] == "INVALID_STATE_TRANSITION"
