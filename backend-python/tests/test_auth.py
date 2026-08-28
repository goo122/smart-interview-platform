from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
from fastapi.testclient import TestClient

from app.core.config import get_settings


def register(client: TestClient, *, username: str = "testuser", email: str = "test@example.com"):
    return client.post(
        "/api/v1/auth/register",
        json={"username": username, "email": email, "password": "secure-password"},
    )


def login(client: TestClient, account: str = "test@example.com"):
    return client.post(
        "/api/v1/auth/login",
        json={"account": account, "password": "secure-password"},
    )


def test_register_and_normalize_email(auth_client) -> None:
    client, _, _ = auth_client
    response = register(client, email="Test@EXAMPLE.com")

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "test@example.com"
    assert "password_hash" not in body


def test_duplicate_username(auth_client) -> None:
    client, _, _ = auth_client
    register(client)

    response = register(client, email="other@example.com")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "user_already_exists"


def test_duplicate_email(auth_client) -> None:
    client, _, _ = auth_client
    register(client)

    response = register(client, username="otheruser", email="TEST@example.com")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "user_already_exists"


def test_login_by_email_and_username(auth_client) -> None:
    client, _, _ = auth_client
    register(client)

    by_email = login(client)
    by_username = login(client, account="testuser")

    assert by_email.status_code == 200
    assert by_username.status_code == 200
    assert by_email.json()["token_type"] == "bearer"
    assert by_email.json()["expires_in"] == 1800


def test_wrong_password_and_unknown_user_have_same_failure(auth_client) -> None:
    client, _, _ = auth_client
    register(client)

    wrong_password = client.post(
        "/api/v1/auth/login",
        json={"account": "test@example.com", "password": "wrong-password"},
    )
    unknown_user = client.post(
        "/api/v1/auth/login",
        json={"account": "missing@example.com", "password": "wrong-password"},
    )

    assert wrong_password.status_code == unknown_user.status_code == 401
    assert wrong_password.json() == unknown_user.json()


def test_disabled_user_cannot_login(auth_client) -> None:
    client, repository, _ = auth_client
    register(client)
    repository.users[0].is_active = False

    response = login(client)

    assert response.status_code == 401
    assert response.json()["error"]["message"] == "Authentication failed"


def test_refresh_rotates_and_invalidates_old_token(auth_client) -> None:
    client, _, _ = auth_client
    register(client)
    original = login(client).json()

    refreshed = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": original["refresh_token"]}
    )
    old_token = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": original["refresh_token"]}
    )

    assert refreshed.status_code == 200
    assert refreshed.json()["refresh_token"] != original["refresh_token"]
    assert old_token.status_code == 401
    assert old_token.json()["error"]["code"] == "invalid_refresh_token"


def test_access_token_cannot_be_used_as_refresh_token(auth_client) -> None:
    client, _, _ = auth_client
    register(client)
    tokens = login(client).json()

    response = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["access_token"]}
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_refresh_token"


def test_expired_refresh_token_is_rejected(auth_client) -> None:
    client, _, _ = auth_client
    register(client)
    now = datetime.now(UTC)
    expired = jwt.encode(
        {
            "sub": str(uuid4()),
            "type": "refresh",
            "jti": str(uuid4()),
            "iat": int((now - timedelta(minutes=2)).timestamp()),
            "exp": int((now - timedelta(minutes=1)).timestamp()),
        },
        get_settings().secret_key,
        algorithm=get_settings().jwt_algorithm,
    )

    response = client.post("/api/v1/auth/refresh", json={"refresh_token": expired})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_refresh_token"


def test_revoked_refresh_token_is_rejected(auth_client) -> None:
    client, _, _ = auth_client
    register(client)
    tokens = login(client).json()
    logout = client.post("/api/v1/auth/logout", json={"refresh_token": tokens["refresh_token"]})
    refresh = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )

    assert logout.status_code == 200
    assert refresh.status_code == 401


def test_logout_invalidates_refresh_token(auth_client) -> None:
    client, _, session_store = auth_client
    register(client)
    tokens = login(client).json()

    response = client.post("/api/v1/auth/logout", json={"refresh_token": tokens["refresh_token"]})

    assert response.status_code == 200
    assert response.json() == {"message": "Logged out"}
    assert session_store.revoked


def test_me_requires_login(auth_client) -> None:
    client, _, _ = auth_client

    response = client.get("/api/v1/auth/me")

    assert response.status_code == 401
    assert response.json() == {
        "error": {"code": "authentication_failed", "message": "Authentication failed"}
    }


def test_me_returns_user_without_password_hash(auth_client) -> None:
    client, _, _ = auth_client
    register(client)
    tokens = login(client).json()

    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )

    assert response.status_code == 200
    assert response.json()["email"] == "test@example.com"
    assert "password_hash" not in response.json()

