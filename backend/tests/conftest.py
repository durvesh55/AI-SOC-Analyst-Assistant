"""Test fixtures. Tests use an in-memory MongoDB (mongomock) so no real database is touched."""
import mongomock
import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.database import get_db, init_db
from app.main import app
from app.security import hash_password
from app.utils import utcnow

ADMIN_PW = "Admin#Pass123"
ANALYST_PW = "Analyst#Pass123"


@pytest.fixture(autouse=True)
def fast_hashing():
    s = get_settings()
    old, s.bcrypt_rounds = s.bcrypt_rounds, 4
    yield
    s.bcrypt_rounds = old


@pytest.fixture()
def db():
    client = mongomock.MongoClient()
    database = client["soc_test"]
    init_db(database)
    return database


@pytest.fixture()
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


def _make_user(db, username, role, password):
    now = utcnow()
    doc = {"username": username, "email": f"{username}@test.local", "full_name": username.title(),
           "password_hash": hash_password(password), "role": role, "is_active": True,
           "created_at": now, "updated_at": now, "last_login": None}
    doc["_id"] = db.users.insert_one(doc).inserted_id
    return doc


def login(client, identifier, password):
    r = client.post("/api/auth/login", json={"identifier": identifier, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def admin(db, client):
    user = _make_user(db, "admin", "Admin", ADMIN_PW)
    return {"user": user, "headers": auth(login(client, "admin", ADMIN_PW))}


@pytest.fixture()
def analyst(db, client):
    user = _make_user(db, "analyst1", "Analyst", ANALYST_PW)
    return {"user": user, "headers": auth(login(client, "analyst1", ANALYST_PW))}


@pytest.fixture()
def analyst2(db, client):
    user = _make_user(db, "analyst2", "Analyst", ANALYST_PW)
    return {"user": user, "headers": auth(login(client, "analyst2", ANALYST_PW))}


ALERT = {
    "title": "Multiple failed SSH logins",
    "description": "47 failed login attempts for root",
    "severity": "High",
    "category": "Brute Force",
    "source_ip": "203.0.113.5",
    "hostname": "srv-01",
}


@pytest.fixture()
def make_alert(client):
    def _make(headers, **overrides):
        r = client.post("/api/alerts", json={**ALERT, **overrides}, headers=headers)
        assert r.status_code == 201, r.text
        return r.json()
    return _make
