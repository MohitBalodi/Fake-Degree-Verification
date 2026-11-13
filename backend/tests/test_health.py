from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_ok() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_openapi_is_served() -> None:
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert response.json()["info"]["version"] == "0.1.0"


def test_unknown_route_uses_error_envelope() -> None:
    response = client.get("/api/v1/does-not-exist")
    assert response.status_code == 404
    assert set(response.json()["error"]) >= {"code", "message"}
