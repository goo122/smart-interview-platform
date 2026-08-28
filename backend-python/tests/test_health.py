from fastapi.testclient import TestClient

from app.main import app


class BrokenDatabase:
    def connect(self) -> "BrokenDatabase":
        return self

    async def __aenter__(self) -> "BrokenDatabase":
        raise RuntimeError("database unavailable")

    async def __aexit__(self, *_args: object) -> None:
        return None


class BrokenRedis:
    async def ping(self) -> bool:
        raise RuntimeError("redis unavailable")


def test_health_returns_ok() -> None:
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_live_health_does_not_require_database_or_redis() -> None:
    with TestClient(app) as client:
        response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_health_is_safe_when_dependencies_are_unavailable() -> None:
    with TestClient(app) as client:
        response = client.get("/health/ready")

    assert response.status_code in {200, 503}
    assert response.json().keys() == {"status"}
    if response.status_code == 503:
        assert response.json() == {"status": "not_ready"}


def test_live_stays_up_when_database_is_down() -> None:
    with TestClient(app) as client:
        original_engine = app.state.database_engine
        original_redis = app.state.redis
        app.state.database_engine = BrokenDatabase()
        app.state.redis = BrokenRedis()
        try:
            live_response = client.get("/health/live")
            ready_response = client.get("/health/ready")
        finally:
            app.state.database_engine = original_engine
            app.state.redis = original_redis

    assert live_response.status_code == 200
    assert ready_response.status_code == 503
    assert ready_response.json() == {"status": "not_ready"}


def test_not_found_uses_standard_error_response() -> None:
    with TestClient(app) as client:
        response = client.get("/not-found")

    assert response.status_code == 404
    assert response.json() == {
        "error": {"code": "not_found", "message": "Not Found"}
    }
