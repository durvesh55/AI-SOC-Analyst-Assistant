"""Authorization (RBAC) for admin-only features and ownership rules."""
from tests.conftest import auth, login


def test_analyst_cannot_use_admin_endpoints(client, analyst):
    assert client.get("/api/users", headers=analyst["headers"]).status_code == 403
    r = client.post("/api/users", headers=analyst["headers"],
                    json={"username": "evil", "email": "e@e.com", "full_name": "E", "password": "Passw0rd123", "role": "Admin"})
    assert r.status_code == 403
    uid = str(analyst["user"]["_id"])
    assert client.patch(f"/api/users/{uid}", json={"role": "Admin"}, headers=analyst["headers"]).status_code == 403


def test_admin_user_management(client, admin):
    r = client.post("/api/users", headers=admin["headers"],
                    json={"username": "bob", "email": "bob@example.com", "full_name": "Bob", "password": "Passw0rd123", "role": "Admin"})
    assert r.status_code == 201 and r.json()["role"] == "Admin"
    bob = r.json()["id"]
    r = client.patch(f"/api/users/{bob}", json={"role": "Analyst"}, headers=admin["headers"])
    assert r.status_code == 200 and r.json()["role"] == "Analyst"
    users = client.get("/api/users", headers=admin["headers"]).json()
    assert users["total"] == 2 and all("password_hash" not in u for u in users["items"])


def test_admin_cannot_demote_or_disable_self(client, admin):
    uid = str(admin["user"]["_id"])
    assert client.patch(f"/api/users/{uid}", json={"role": "Analyst"}, headers=admin["headers"]).status_code == 400
    assert client.patch(f"/api/users/{uid}", json={"is_active": False}, headers=admin["headers"]).status_code == 400


def test_user_update_unknown_or_invalid_id(client, admin):
    assert client.patch("/api/users/not-an-id", json={"role": "Analyst"}, headers=admin["headers"]).status_code == 404
    assert client.patch("/api/users/" + "a" * 24, json={"role": "Analyst"}, headers=admin["headers"]).status_code == 404
    assert client.patch(f"/api/users/{admin['user']['_id']}", json={"role": "Boss"}, headers=admin["headers"]).status_code == 422


def test_assignable_list_available_to_analyst_without_sensitive_fields(client, admin, analyst):
    r = client.get("/api/users/assignable", headers=analyst["headers"])
    assert r.status_code == 200
    assert {u["username"] for u in r.json()} == {"admin", "analyst1"}
    assert all(set(u) == {"id", "username", "full_name", "role"} for u in r.json())
