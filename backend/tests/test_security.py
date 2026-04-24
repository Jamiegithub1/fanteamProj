from fastapi.testclient import TestClient

from app.main import app


def test_protected_endpoint_requires_auth() -> None:
    client = TestClient(app)

    response = client.get("/projections")

    assert response.status_code == 401


def test_auth_check_accepts_env_credentials() -> None:
    client = TestClient(app)

    response = client.get("/auth/check", auth=("admin", "change-me"))

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "username": "admin"}
