from fastapi.testclient import TestClient

from app.main import app


def test_health_returns_ok() -> None:
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_not_found_uses_standard_error_response() -> None:
    with TestClient(app) as client:
        response = client.get("/not-found")

    assert response.status_code == 404
    assert response.json() == {
        "error": {"code": "not_found", "message": "Not Found"}
    }

