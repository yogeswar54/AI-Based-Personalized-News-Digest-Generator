import os

os.environ.setdefault("MONGODB_URI", "mongodb://localhost:27017")
os.environ.setdefault("DATABASE_NAME", "personalized_news_digest_test")

from bson import ObjectId
from fastapi.testclient import TestClient

from app.database import mongodb as mongo_module
from app.api.v1 import routes as health_routes
from app.main import app


class FakeCollection:
    def __init__(self) -> None:
        self.docs: dict[str, dict] = {}

    def create_index(self, *args, **kwargs):
        return None

    def insert_one(self, document: dict):
        document_id = ObjectId()
        document["_id"] = document_id
        self.docs[str(document_id)] = document
        return type("InsertResult", (), {"inserted_id": document_id})()

    def find_one(self, query: dict):
        if "email" in query:
            for document in self.docs.values():
                if document.get("email") == query["email"]:
                    return document
            return None
        if "_id" in query:
            key = str(query["_id"])
            return self.docs.get(key)
        return None

    def update_one(self, query: dict, update: dict):
        document = self.find_one(query)
        if document is None:
            return None
        document.update(update["$set"])
        return None


class FakeDatabase:
    def __getitem__(self, key: str):
        if not hasattr(self, "collections"):
            self.collections = {"users": FakeCollection()}
        return self.collections[key]


def patch_fake_database(monkeypatch):
    fake_database = FakeDatabase()
    monkeypatch.setattr(mongo_module, "get_database", lambda: fake_database)
    monkeypatch.setattr("app.services.user_service.get_database", lambda: fake_database)
    return fake_database


def test_health_check(monkeypatch) -> None:
    monkeypatch.setattr(health_routes, "is_mongodb_available", lambda: False)
    with TestClient(app) as client:
        response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "degraded",
        "message": "Personalized News Digest API is running",
        "dependencies": {"mongodb": "unavailable"},
    }
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"


def test_readiness_check_requires_mongodb(monkeypatch) -> None:
    monkeypatch.setattr(health_routes, "is_mongodb_available", lambda: False)
    with TestClient(app) as client:
        response = client.get("/api/v1/health/ready")

    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"


def test_readiness_check_reports_connected_database(monkeypatch) -> None:
    monkeypatch.setattr(health_routes, "is_mongodb_available", lambda: True)
    with TestClient(app) as client:
        response = client.get("/api/v1/health/ready")

    assert response.status_code == 200
    assert response.json()["dependencies"]["mongodb"] == "connected"


def test_root_endpoint() -> None:
    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert response.json()["status"] == "success"


def test_not_found_uses_standard_error_response() -> None:
    with TestClient(app) as client:
        response = client.get("/missing")

    assert response.status_code == 404
    assert response.json() == {"status": "error", "message": "Not Found"}


def test_register_user_success(monkeypatch) -> None:
    patch_fake_database(monkeypatch)
    payload = {
        "full_name": "Test User",
        "email": "test.user@example.com",
        "password": "strongpass1",
        "confirm_password": "strongpass1",
    }

    with TestClient(app) as client:
        response = client.post("/api/v1/auth/register", json=payload)

    assert response.status_code == 201
    assert response.json()["message"] == "User registered successfully"


def test_register_duplicate_email(monkeypatch) -> None:
    patch_fake_database(monkeypatch)
    payload = {
        "full_name": "Test User",
        "email": "duplicate@example.com",
        "password": "strongpass1",
        "confirm_password": "strongpass1",
    }

    with TestClient(app) as client:
        first = client.post("/api/v1/auth/register", json=payload)
        second = client.post("/api/v1/auth/register", json=payload)

    assert first.status_code == 201
    assert second.status_code == 409


def test_login_and_profile_access(monkeypatch) -> None:
    patch_fake_database(monkeypatch)
    register_payload = {
        "full_name": "Profile User",
        "email": "profile@example.com",
        "password": "strongpass1",
        "confirm_password": "strongpass1",
    }

    with TestClient(app) as client:
        client.post("/api/v1/auth/register", json=register_payload)
        login_response = client.post(
            "/api/v1/auth/login",
            json={"email": "profile@example.com", "password": "strongpass1"},
        )
        me_response = client.get("/api/v1/auth/me")
        profile_response = client.get("/api/v1/users/profile")

    assert login_response.status_code == 200
    assert login_response.json()["message"] == "Login successful"
    assert me_response.status_code == 200
    assert profile_response.status_code == 200


def test_invalid_password_and_email_validation(monkeypatch) -> None:
    patch_fake_database(monkeypatch)
    with TestClient(app) as client:
        weak_password = client.post(
            "/api/v1/auth/register",
            json={
                "full_name": "Bad User",
                "email": "bad@example.com",
                "password": "short",
                "confirm_password": "short",
            },
        )
        invalid_email = client.post(
            "/api/v1/auth/register",
            json={
                "full_name": "Bad User",
                "email": "bad-email",
                "password": "strongpass1",
                "confirm_password": "strongpass1",
            },
        )

    assert weak_password.status_code == 422
    assert invalid_email.status_code == 422


def test_interest_update_requires_auth(monkeypatch) -> None:
    patch_fake_database(monkeypatch)
    with TestClient(app) as client:
        response = client.put(
            "/api/v1/users/interests",
            json={"interests": ["Technology", "Sports"]},
            headers={"Origin": "http://localhost:5173"},
        )

    assert response.status_code == 401


def test_interest_update_for_authenticated_user(monkeypatch) -> None:
    patch_fake_database(monkeypatch)
    register_payload = {
        "full_name": "Interest User",
        "email": "interests@example.com",
        "password": "strongpass1",
        "confirm_password": "strongpass1",
    }

    with TestClient(app) as client:
        client.post("/api/v1/auth/register", json=register_payload)
        client.post(
            "/api/v1/auth/login",
            json={"email": "interests@example.com", "password": "strongpass1"},
        )
        response = client.put(
            "/api/v1/users/interests",
            json={"interests": ["Technology", "Sports"]},
            headers={"Origin": "http://localhost:5173"},
        )
        categories_response = client.get("/api/v1/interests/categories")

    assert response.status_code == 200
    assert response.json()["interests"] == ["Technology", "Sports"]
    assert categories_response.status_code == 200
    assert "Technology" in categories_response.json()["categories"]


def test_cookie_authenticated_mutation_rejects_untrusted_origin(monkeypatch) -> None:
    patch_fake_database(monkeypatch)
    payload = {
        "full_name": "CSRF User",
        "email": "csrf@example.com",
        "password": "strongpass1",
        "confirm_password": "strongpass1",
    }

    with TestClient(app) as client:
        client.post("/api/v1/auth/register", json=payload)
        client.post(
            "/api/v1/auth/login",
            json={"email": payload["email"], "password": payload["password"]},
        )
        response = client.put(
            "/api/v1/users/interests",
            json={"interests": ["Technology"]},
            headers={"Origin": "https://attacker.example"},
        )

    assert response.status_code == 403


def test_password_byte_limit_is_validated_before_bcrypt() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/register",
            json={
                "full_name": "Unicode User",
                "email": "unicode@example.com",
                "password": "é" * 40,
                "confirm_password": "é" * 40,
            },
        )

    assert response.status_code == 422
