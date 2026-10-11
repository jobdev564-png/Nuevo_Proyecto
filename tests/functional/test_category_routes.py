def _login_as(client, email="catuser@example.com", password="Password123!"):
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


# --- Incremento 3 / HU-08: Categorías (US2) ---

def test_list_categories_requires_auth(client):
    """Sin sesión → 401 en JSON."""
    resp = client.get("/categories/", headers={"Accept": "application/json"})
    assert resp.status_code == 401


def test_create_and_list_categories(client):
    """Crear categoría (201) y listar solo las propias."""
    _login_as(client, "owner@example.com")

    resp = client.post(
        "/categories/",
        data={"name": "Trabajo", "description": "Proyectos"},
        headers={"Accept": "application/json"},
    )
    assert resp.status_code == 201
    assert resp.get_json()["data"]["name"] == "Trabajo"

    listing = client.get("/categories/", headers={"Accept": "application/json"})
    assert listing.status_code == 200
    assert [c["name"] for c in listing.get_json()["data"]] == ["Trabajo"]


def test_create_category_validation_errors(client):
    """Nombre vacío → 400; duplicado propio → 409."""
    _login_as(client, "dup@example.com")

    bad = client.post(
        "/categories/",
        data={"name": "   "},
        headers={"Accept": "application/json"},
    )
    assert bad.status_code == 400

    ok = client.post(
        "/categories/",
        data={"name": "Estudio"},
        headers={"Accept": "application/json"},
    )
    assert ok.status_code == 201

    dup = client.post(
        "/categories/",
        data={"name": "estudio"},
        headers={"Accept": "application/json"},
    )
    assert dup.status_code == 409


def test_delete_category_unlinks_tasks(client):
    """Eliminar categoría desvincula tareas sin borrarlas."""
    _login_as(client, "deleter@example.com")

    cat = client.post(
        "/categories/",
        data={"name": "Temp"},
        headers={"Accept": "application/json"},
    ).get_json()["data"]

    t1 = client.post(
        "/tasks",
        data={"title": "Una"},
        headers={"Accept": "application/json"},
    ).get_json()["data"]
    client.post(
        f"/tasks/{t1['id']}/category",
        data={"category_id": str(cat["id"])},
        headers={"Accept": "application/json"},
    )

    resp = client.post(
        f"/categories/{cat['id']}/delete",
        headers={"Accept": "application/json"},
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["data"]["unlinked_tasks"] == 1

    tasks = client.get("/tasks", headers={"Accept": "application/json"})
    found = [t for t in tasks.get_json()["data"]["tasks"] if t["id"] == t1["id"]]
    assert len(found) == 1
    assert found[0]["category_id"] is None


def test_delete_foreign_category_not_found(client):
    """Eliminar categoría ajena → 404."""
    _login_as(client, "victim@example.com")
    cat_id = client.post(
        "/categories/",
        data={"name": "Privada"},
        headers={"Accept": "application/json"},
    ).get_json()["data"]["id"]

    client.post("/auth/logout", headers={"Accept": "application/json"})
    _login_as(client, "attacker@example.com")
    resp = client.post(
        f"/categories/{cat_id}/delete",
        headers={"Accept": "application/json"},
    )
    assert resp.status_code == 404


def test_assign_foreign_category_rejected(client):
    """Asignar categoría ajena a tarea propia → 400/404."""
    _login_as(client, "victim2@example.com")
    cat_id = client.post(
        "/categories/",
        data={"name": "Privada"},
        headers={"Accept": "application/json"},
    ).get_json()["data"]["id"]

    client.post("/auth/logout", headers={"Accept": "application/json"})
    _login_as(client, "attacker2@example.com")
    task_id = client.post(
        "/tasks",
        data={"title": "Mía"},
        headers={"Accept": "application/json"},
    ).get_json()["data"]["id"]

    resp = client.post(
        f"/tasks/{task_id}/category",
        data={"category_id": str(cat_id)},
        headers={"Accept": "application/json"},
    )
    assert resp.status_code in (400, 404)
