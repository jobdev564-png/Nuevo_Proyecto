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


# --- US3: Creación de Tareas ---

def test_create_task_unauthenticated_fails(client):
    """Verifica 401 Unauthorized sin sesión activa."""
    response = client.post(
        "/tasks",
        data={"title": "Tarea no autorizada"},
        headers={"Accept": "application/json"},
    )
    assert response.status_code == 401


def test_create_task_authenticated_success(client):
    """Verifica creación de tarea con sesión activa."""
    _login_as(client, "createuser@example.com")

    response = client.post(
        "/tasks",
        data={
            "title": "Aprender Spec Kit",
            "description": "Monolito y principios",
            "due_date": "2026-10-20",
        },
        headers={"Accept": "application/json"},
    )
    assert response.status_code == 201
    data = response.get_json()
    assert data["status"] == "success"
    assert data["data"]["title"] == "Aprender Spec Kit"
    assert data["data"]["status"] == "pending"


def test_create_task_validation_error(client):
    """Verifica error 400 Bad Request si el título está vacío."""
    _login_as(client, "emptyuser@example.com")

    response = client.post(
        "/tasks",
        data={"title": "   "},
        headers={"Accept": "application/json"},
    )
    assert response.status_code == 400
    data = response.get_json()
    assert data["code"] == "VALIDATION_ERROR"


# --- US4: Listado y Filtrado de Tareas ---

def test_list_tasks_authenticated(client):
    """Verifica listado exclusivo de tareas del usuario y soporte de filtros."""
    _login_as(client, "listuser@example.com")

    client.post(
        "/tasks",
        data={"title": "Tarea Pendiente"},
        headers={"Accept": "application/json"},
    )
    res2 = client.post(
        "/tasks",
        data={"title": "Tarea Para Completar"},
        headers={"Accept": "application/json"},
    )
    t2_id = res2.get_json()["data"]["id"]

    client.post(
        f"/tasks/{t2_id}/status",
        data={"status": "completed"},
        headers={"Accept": "application/json"},
    )

    # 1. Listar todas
    response_all = client.get("/tasks", headers={"Accept": "application/json"})
    assert response_all.status_code == 200
    assert response_all.get_json()["data"]["count"] == 2

    # 2. Filtrar por completadas
    response_completed = client.get(
        "/tasks?status=completed", headers={"Accept": "application/json"}
    )
    assert response_completed.status_code == 200
    assert response_completed.get_json()["data"]["count"] == 1


# --- US5: Cambio de Estado de Tareas ---

def test_update_task_status_route(client):
    """Verifica transición de estado válida y rechazo de reapertura."""
    _login_as(client, "statususer@example.com")

    res = client.post(
        "/tasks",
        data={"title": "Tarea Ciclo"},
        headers={"Accept": "application/json"},
    )
    task_id = res.get_json()["data"]["id"]

    # pending -> in_progress
    resp = client.post(
        f"/tasks/{task_id}/status",
        data={"status": "in_progress"},
        headers={"Accept": "application/json"},
    )
    assert resp.status_code == 200
    assert resp.get_json()["data"]["current_status"] == "in_progress"

    # in_progress -> completed
    resp = client.post(
        f"/tasks/{task_id}/status",
        data={"status": "completed"},
        headers={"Accept": "application/json"},
    )
    assert resp.status_code == 200
    assert resp.get_json()["data"]["current_status"] == "completed"

    # completed -> pending (BLOQUEADO en este incremento)
    resp = client.post(
        f"/tasks/{task_id}/status",
        data={"status": "pending"},
        headers={"Accept": "application/json"},
    )
    assert resp.status_code == 400
    assert resp.get_json()["code"] == "INVALID_STATE_TRANSITION"


# --- US6: Edición de Tareas ---

def test_edit_task_route(client):
    """Verifica edición de título y descripción con validación de permisos."""
    _login_as(client, "edituser@example.com")

    res = client.post(
        "/tasks",
        data={"title": "Tarea Original"},
        headers={"Accept": "application/json"},
    )
    task_id = res.get_json()["data"]["id"]

    # Edición exitosa
    resp = client.post(
        f"/tasks/{task_id}/edit",
        data={"title": "Tarea Editada", "description": "Nueva descripción"},
        headers={"Accept": "application/json"},
    )
    assert resp.status_code == 200
    assert resp.get_json()["data"]["title"] == "Tarea Editada"

    # Título vacío falla con 400
    resp_empty = client.post(
        f"/tasks/{task_id}/edit",
        data={"title": ""},
        headers={"Accept": "application/json"},
    )
    assert resp_empty.status_code == 400


# --- Incremento 3 / HU-07: Prioridad de Tareas (US1) ---

def test_update_priority_route_success(client):
    """POST /tasks/<id>/priority actualiza y persiste la prioridad."""
    _login_as(client, "priorityuser@example.com")

    res = client.post(
        "/tasks",
        data={"title": "Priorizable", "priority": "low"},
        headers={"Accept": "application/json"},
    )
    assert res.status_code == 201
    task_id = res.get_json()["data"]["id"]

    resp = client.post(
        f"/tasks/{task_id}/priority",
        data={"priority": "high"},
        headers={"Accept": "application/json"},
    )
    assert resp.status_code == 200
    assert resp.get_json()["data"]["priority"] == "high"


def test_update_priority_route_invalid_value(client):
    """Prioridad no reconocida → 400 con mensaje de validación."""
    _login_as(client, "badpriority@example.com")

    res = client.post(
        "/tasks",
        data={"title": "Base"},
        headers={"Accept": "application/json"},
    )
    task_id = res.get_json()["data"]["id"]

    resp = client.post(
        f"/tasks/{task_id}/priority",
        data={"priority": "urgentísima"},
        headers={"Accept": "application/json"},
    )
    assert resp.status_code == 400
    assert "Prioridad inválida" in resp.get_json()["message"]


def test_update_priority_route_not_found(client):
    """Tarea inexistente o ajena → 404."""
    _login_as(client, "nopriority@example.com")

    resp = client.post(
        "/tasks/999999/priority",
        data={"priority": "high"},
        headers={"Accept": "application/json"},
    )
    assert resp.status_code == 404


def test_list_tasks_sorted_by_priority(client):
    """GET /tasks?sort_by=priority&order=desc ordena alta → baja."""
    _login_as(client, "sortuser@example.com")

    for title, prio in [("Baja", "low"), ("Alta", "high"), ("Media", "medium")]:
        resp = client.post(
            "/tasks",
            data={"title": title, "priority": prio},
            headers={"Accept": "application/json"},
        )
        assert resp.status_code == 201

    resp = client.get(
        "/tasks?sort_by=priority&order=desc",
        headers={"Accept": "application/json"},
    )
    assert resp.status_code == 200
    tasks = resp.get_json()["data"]["tasks"]
    assert [t["priority"] for t in tasks] == ["high", "medium", "low"]


def test_create_task_default_priority_is_medium(client):
    """Crear sin prioridad devuelve 'medium' en el contrato."""
    _login_as(client, "defaultprio@example.com")

    resp = client.post(
        "/tasks",
        data={"title": "Sin prioridad"},
        headers={"Accept": "application/json"},
    )
    assert resp.status_code == 201
    assert resp.get_json()["data"]["priority"] == "medium"


# --- Incremento 3 / HU-09: Tareas Vencidas (US3) ---

def test_task_list_exposes_is_overdue(client):
    """El contrato JSON incluye is_overdue calculado en backend (FR-016/020)."""
    _login_as(client, "overdue@example.com")
    from datetime import date, timedelta

    past = (date.today() - timedelta(days=3)).isoformat()
    client.post(
        "/tasks",
        data={"title": "Informe Atrasado", "due_date": past},
        headers={"Accept": "application/json"},
    )
    done = client.post(
        "/tasks",
        data={"title": "Entregable Listo", "due_date": past},
        headers={"Accept": "application/json"},
    ).get_json()["data"]
    client.post(
        f"/tasks/{done['id']}/status",
        data={"status": "completed"},
        headers={"Accept": "application/json"},
    )

    resp = client.get("/tasks", headers={"Accept": "application/json"})
    assert resp.status_code == 200
    by_title = {t["title"]: t for t in resp.get_json()["data"]["tasks"]}
    assert "is_overdue" in by_title["Informe Atrasado"]
    assert by_title["Informe Atrasado"]["is_overdue"] is True
    assert by_title["Entregable Listo"]["is_overdue"] is False


# --- Incremento 3 / US4: Consulta integrada estado + categoría + prioridad ---

def _us4_seed(client):
    _login_as(client, "combo@example.com")
    work = client.post(
        "/categories/",
        data={"name": "Work"},
        headers={"Accept": "application/json"},
    ).get_json()["data"]
    ids = {}
    for title, prio, cat in [
        ("W alta pend", "high", work["id"]),
        ("W baja pend", "low", work["id"]),
        ("S alta pend", "high", None),
        ("W alta prog", "high", work["id"]),
    ]:
        payload = {"title": title, "priority": prio}
        if cat is not None:
            payload["category_id"] = str(cat)
        r = client.post("/tasks", data=payload, headers={"Accept": "application/json"})
        ids[title] = r.get_json()["data"]["id"]
    client.post(
        f"/tasks/{ids['W alta prog']}/status",
        data={"status": "in_progress"},
        headers={"Accept": "application/json"},
    )
    return work, ids


def test_combined_category_and_priority_order(client):
    """Filtro por categoría + orden por prioridad (US4 escenario 1)."""
    work, _ = _us4_seed(client)
    resp = client.get(
        f"/tasks?category_id={work['id']}&sort_by=priority&order=desc&status=pending",
        headers={"Accept": "application/json"},
    )
    tasks = resp.get_json()["data"]["tasks"]
    assert [t["title"] for t in tasks] == ["W alta pend", "W baja pend"]


def test_filter_uncategorized(client):
    """category_id=none devuelve solo tareas sin categoría (US4 escenario 2)."""
    _us4_seed(client)
    resp = client.get(
        "/tasks?category_id=none",
        headers={"Accept": "application/json"},
    )
    tasks = resp.get_json()["data"]["tasks"]
    assert len(tasks) == 1
    assert tasks[0]["title"] == "S alta pend"
    assert tasks[0]["category_id"] is None


def test_triple_combination_status_category_priority(client):
    """Triple combinación estado + categoría + orden (US4 escenario 3)."""
    work, _ = _us4_seed(client)
    resp = client.get(
        f"/tasks?status=in_progress&category_id={work['id']}&sort_by=priority&order=desc",
        headers={"Accept": "application/json"},
    )
    tasks = resp.get_json()["data"]["tasks"]
    assert [t["title"] for t in tasks] == ["W alta prog"]


def test_list_backward_compatible_without_new_params(client):
    """Sin nuevos parámetros el listado conserva el comportamiento legado."""
    _login_as(client, "legacy@example.com")
    client.post("/tasks", data={"title": "Legada"}, headers={"Accept": "application/json"})
    resp = client.get("/tasks", headers={"Accept": "application/json"})
    assert resp.status_code == 200
    tasks = resp.get_json()["data"]["tasks"]
    assert len(tasks) == 1
    assert tasks[0]["priority"] == "medium"


# --- Incremento 5 US1: Contrato fetch de completado (HU-15, T011) ---

def test_status_direct_jump_via_fetch_contract(client):
    """POST /tasks/<id>/status con JSON {"status": "completed"}: salto directo + envoltorio."""
    _login_as(client, "fetchjump@example.com")

    res = client.post(
        "/tasks",
        json={"title": "Tarea Fetch"},
        headers={"Accept": "application/json"},
    )
    task_id = res.get_json()["data"]["id"]

    # Salto directo pending -> completed vía fetch JSON
    resp = client.post(
        f"/tasks/{task_id}/status",
        json={"status": "completed"},
        headers={"Accept": "application/json"},
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "success"
    assert body["data"]["current_status"] == "completed"

    # Idempotencia: completar una tarea ya completada no produce cambio válido
    again = client.post(
        f"/tasks/{task_id}/status",
        json={"status": "completed"},
        headers={"Accept": "application/json"},
    )
    assert again.status_code == 400
    assert again.get_json()["code"] == "INVALID_STATE_TRANSITION"


def test_status_foreign_task_returns_neutral_404(client):
    """Tarea ajena → 404 neutro TASK_NOT_FOUND (sin revelar propiedad)."""
    _login_as(client, "owner5@example.com")
    res = client.post(
        "/tasks",
        json={"title": "Tarea Ajena"},
        headers={"Accept": "application/json"},
    )
    foreign_id = res.get_json()["data"]["id"]

    other = client.__class__(client.application)
    _login_as(other, "intruder5@example.com")
    resp = other.post(
        f"/tasks/{foreign_id}/status",
        json={"status": "completed"},
        headers={"Accept": "application/json"},
    )
    assert resp.status_code == 404
    assert resp.get_json()["code"] == "TASK_NOT_FOUND"


# --- Incremento 5 US2: Contrato POST /tasks/reorder (HU-16, T019) ---

def _reorder_seed(client, email="reorder@example.com"):
    _login_as(client, email)
    ids = []
    for title in ["R1", "R2", "R3"]:
        res = client.post(
            "/tasks",
            json={"title": title},
            headers={"Accept": "application/json"},
        )
        ids.append(res.get_json()["data"]["id"])
    return ids


def test_reorder_route_persists_and_audits(client):
    """POST /tasks/reorder → 200 con envoltorio y orden persistido tras recarga."""
    ids = _reorder_seed(client)
    new_order = [ids[2], ids[0], ids[1]]
    resp = client.post(
        "/tasks/reorder",
        json={"ordered_ids": new_order, "view": "all"},
        headers={"Accept": "application/json"},
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "success"
    assert body["data"]["ordered_ids"] == new_order

    listing = client.get("/tasks", headers={"Accept": "application/json"})
    assert [t["id"] for t in listing.get_json()["data"]["tasks"]] == new_order


def test_reorder_route_rejects_bad_payload_and_requires_session(client):
    """Lote vacío/duplicado → 400; sin sesión → 401."""
    ids = _reorder_seed(client, "reorder2@example.com")

    empty = client.post(
        "/tasks/reorder",
        json={"ordered_ids": []},
        headers={"Accept": "application/json"},
    )
    assert empty.status_code == 400

    dupe = client.post(
        "/tasks/reorder",
        json={"ordered_ids": [ids[0], ids[0]]},
        headers={"Accept": "application/json"},
    )
    assert dupe.status_code == 400

    anon = client.__class__(client.application)
    nosess = anon.post(
        "/tasks/reorder",
        json={"ordered_ids": ids},
        headers={"Accept": "application/json"},
    )
    assert nosess.status_code == 401
    assert nosess.get_json()["code"] == "UNAUTHORIZED"


def test_reorder_route_foreign_id_is_neutral_404(client):
    """Id de otro usuario → 404 TASK_NOT_FOUND neutro."""
    ids = _reorder_seed(client, "reorder3@example.com")
    other = client.__class__(client.application)
    foreign = _reorder_seed(other, "reorder4@example.com")
    resp = client.post(
        "/tasks/reorder",
        json={"ordered_ids": ids + [foreign[0]]},
        headers={"Accept": "application/json"},
    )
    assert resp.status_code == 404
    assert resp.get_json()["code"] == "TASK_NOT_FOUND"
