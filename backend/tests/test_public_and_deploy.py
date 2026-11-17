"""Public landing-page endpoint, invite-code registration, production safety, create_admin."""
import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.create_admin import create_admin
from app.main import app
from app.routers import public

REG = {"username": "invitee", "email": "invitee@example.com", "full_name": "In Vitee", "password": "Str0ngPass1"}


@pytest.fixture(autouse=True)
def clear_limiter():
    public._hits.clear()
    yield
    public._hits.clear()


def test_public_suggest_works_without_login(client):
    r = client.post("/api/public/mitre-suggest",
                    json={"title": "Failed logins", "description": "password spray against ssh", "category": "Brute Force"})
    assert r.status_code == 200
    top = r.json()["suggestions"][0]
    assert top["technique_id"] == "T1110" and "validated by an analyst" in top["disclaimer"]


def test_public_suggest_validation(client):
    assert client.post("/api/public/mitre-suggest", json={}).status_code == 422
    assert client.post("/api/public/mitre-suggest", json={"title": "x" * 201}).status_code == 422
    assert client.post("/api/public/mitre-suggest", json={"description": "d" * 2001}).status_code == 422
    assert client.post("/api/public/mitre-suggest", json={"title": "ok", "category": "Aliens"}).status_code == 422


def test_public_suggest_is_rate_limited(client):
    for _ in range(public.LIMIT):
        assert client.post("/api/public/mitre-suggest", json={"title": "port scan nmap"}).status_code == 200
    assert client.post("/api/public/mitre-suggest", json={"title": "port scan nmap"}).status_code == 429


def test_public_endpoint_touches_no_database(client, db):
    client.post("/api/public/mitre-suggest", json={"title": "mimikatz"})
    assert db.audit_logs.count_documents({}) == 0 and db.users.count_documents({}) == 0


def test_invite_code_enforced_when_configured(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "registration_invite_code", "let-me-in-123")
    assert client.get("/api/meta").json()["registration_invite_required"] is True
    assert client.post("/api/auth/register", json=REG).status_code == 403
    assert client.post("/api/auth/register", json={**REG, "invite_code": "wrong"}).status_code == 403
    assert client.post("/api/auth/register", json={**REG, "invite_code": "let-me-in-123"}).status_code == 201


def test_registration_open_when_no_invite_code(client):
    assert client.get("/api/meta").json()["registration_invite_required"] is False
    assert client.post("/api/auth/register", json=REG).status_code == 201


def test_production_refuses_weak_secret(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "environment", "production")
    monkeypatch.setattr(s, "jwt_secret", "dev-only-insecure-secret-change-me")
    with pytest.raises(RuntimeError):
        with TestClient(app):
            pass


def test_production_accepts_strong_secret(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "environment", "production")
    monkeypatch.setattr(s, "jwt_secret", "x" * 48)
    with TestClient(app):  # startup succeeds (a Mongo init failure is only logged)
        pass


def test_create_admin(db, client):
    uid = create_admin(db, "Boss", "boss@example.com", "The Boss", "Str0ngPass1")
    user = db.users.find_one({"username": "boss"})
    assert str(user["_id"]) == uid and user["role"] == "Admin" and user["password_hash"].startswith("$2")
    r = client.post("/api/auth/login", json={"identifier": "boss", "password": "Str0ngPass1"})
    assert r.status_code == 200 and r.json()["user"]["role"] == "Admin"


def test_create_admin_rejects_weak_password(db):
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        create_admin(db, "boss", "boss@example.com", "Boss", "short")
