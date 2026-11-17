"""Authentication, token handling, RBAC on user management, unauthorized access."""
import jwt
import pytest

from app.config import get_settings
from tests.conftest import ADMIN_PW, auth, login

REG = {"username": "NewUser", "email": "New@Example.com", "full_name": "New User", "password": "Str0ngPass1"}


def test_register_creates_analyst_and_hides_hash(client):
    r = client.post("/api/auth/register", json=REG)
    assert r.status_code == 201
    body = r.json()
    assert body["role"] == "Analyst" and body["username"] == "newuser" and body["email"] == "new@example.com"
    assert "password_hash" not in body and "password" not in body


def test_register_cannot_self_assign_admin(client):
    r = client.post("/api/auth/register", json={**REG, "role": "Admin"})
    assert r.status_code == 201 and r.json()["role"] == "Analyst"


def test_register_duplicate_rejected(client):
    client.post("/api/auth/register", json=REG)
    assert client.post("/api/auth/register", json=REG).status_code == 409


@pytest.mark.parametrize("pw", ["short1", "alllettersnodigit", "12345678", "x" * 80 + "1"])
def test_register_weak_password_rejected(client, pw):
    r = client.post("/api/auth/register", json={**REG, "password": pw})
    assert r.status_code == 422
    assert pw not in r.text  # the submitted value must never be echoed back


def test_register_bad_username_and_email(client):
    assert client.post("/api/auth/register", json={**REG, "username": "a b!"}).status_code == 422
    assert client.post("/api/auth/register", json={**REG, "email": "not-an-email"}).status_code == 422


def test_password_is_hashed_in_database(client, db):
    client.post("/api/auth/register", json=REG)
    stored = db.users.find_one({"username": "newuser"})["password_hash"]
    assert stored != REG["password"] and stored.startswith("$2")


def test_login_success_by_username_and_email(client, admin):
    for ident in ("admin", "ADMIN@test.local"):
        r = client.post("/api/auth/login", json={"identifier": ident, "password": ADMIN_PW})
        assert r.status_code == 200
        assert r.json()["token_type"] == "bearer" and r.json()["user"]["role"] == "Admin"


def test_login_wrong_password_and_unknown_user_same_error(client, admin):
    a = client.post("/api/auth/login", json={"identifier": "admin", "password": "wrong-pass1"})
    b = client.post("/api/auth/login", json={"identifier": "ghost", "password": "wrong-pass1"})
    assert a.status_code == b.status_code == 401
    assert a.json() == b.json()  # no user enumeration


def test_login_lockout_after_repeated_failures(client, admin):
    for _ in range(10):
        client.post("/api/auth/login", json={"identifier": "admin", "password": "bad-password1"})
    r = client.post("/api/auth/login", json={"identifier": "admin", "password": ADMIN_PW})
    assert r.status_code == 429


def test_protected_endpoints_require_token(client):
    for method, url in [("get", "/api/alerts"), ("get", "/api/cases"), ("get", "/api/dashboard"),
                        ("get", "/api/audit-logs"), ("get", "/api/users"), ("get", "/api/auth/me")]:
        r = getattr(client, method)(url)
        assert r.status_code == 401, url


def test_invalid_and_tampered_token_rejected(client, admin):
    assert client.get("/api/auth/me", headers=auth("garbage")).status_code == 401
    token = admin["headers"]["Authorization"].split()[1]
    forged = jwt.encode(jwt.decode(token, options={"verify_signature": False}), "wrong-secret", algorithm="HS256")
    assert client.get("/api/auth/me", headers=auth(forged)).status_code == 401


def test_expired_token_rejected(client, admin):
    s = get_settings()
    payload = jwt.decode(admin["headers"]["Authorization"].split()[1], options={"verify_signature": False})
    payload["exp"] = payload["iat"] - 10
    expired = jwt.encode(payload, s.jwt_secret, algorithm=s.jwt_algorithm)
    r = client.get("/api/auth/me", headers=auth(expired))
    assert r.status_code == 401 and "expired" in r.json()["detail"].lower()


def test_logout_revokes_token(client, admin):
    assert client.get("/api/auth/me", headers=admin["headers"]).status_code == 200
    assert client.post("/api/auth/logout", headers=admin["headers"]).status_code == 200
    r = client.get("/api/auth/me", headers=admin["headers"])
    assert r.status_code == 401


def test_role_in_token_cannot_be_forged(client, analyst):
    """Even a validly-signed token claiming Admin is ignored: role is read from the database."""
    s = get_settings()
    payload = jwt.decode(analyst["headers"]["Authorization"].split()[1], options={"verify_signature": False})
    payload["role"] = "Admin"
    forged = jwt.encode(payload, s.jwt_secret, algorithm=s.jwt_algorithm)
    assert client.get("/api/users", headers=auth(forged)).status_code == 403


def test_disabled_user_loses_access(client, admin, analyst):
    uid = str(analyst["user"]["_id"])
    r = client.patch(f"/api/users/{uid}", json={"is_active": False}, headers=admin["headers"])
    assert r.status_code == 200
    assert client.get("/api/auth/me", headers=analyst["headers"]).status_code == 401
    r = client.post("/api/auth/login", json={"identifier": "analyst1", "password": "Analyst#Pass123"})
    assert r.status_code == 403


def test_change_password_flow(client, analyst):
    r = client.post("/api/auth/change-password", headers=analyst["headers"],
                    json={"current_password": "wrong-current1", "new_password": "BrandNew#Pass9"})
    assert r.status_code == 400
    r = client.post("/api/auth/change-password", headers=analyst["headers"],
                    json={"current_password": "Analyst#Pass123", "new_password": "BrandNew#Pass9"})
    assert r.status_code == 200
    assert client.get("/api/auth/me", headers=analyst["headers"]).status_code == 401  # old token revoked
    login(client, "analyst1", "BrandNew#Pass9")


def test_profile_update(client, analyst):
    r = client.patch("/api/auth/me", json={"full_name": "Renamed Person"}, headers=analyst["headers"])
    assert r.status_code == 200 and r.json()["full_name"] == "Renamed Person"


def test_validation_error_does_not_leak_internals(client):
    r = client.post("/api/auth/login", json={"identifier": "x"})
    assert r.status_code == 422
    assert all(set(e) == {"loc", "msg"} for e in r.json()["detail"])
