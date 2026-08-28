from collections.abc import Iterator
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.core.exceptions import UserAlreadyExistsError
from app.main import app
from app.modules.auth.dependencies import get_session_store, get_user_repository
from app.modules.auth.domain import User


class FakeUserRepository:
    def __init__(self) -> None:
        self.users: list[User] = []

    async def create(self, user: User) -> User:
        if await self.get_by_username(user.username) or await self.get_by_email(user.email):
            raise UserAlreadyExistsError("Username or email already exists")
        self.users.append(user)
        return user

    async def get_by_id(self, user_id: UUID) -> User | None:
        return next((user for user in self.users if user.id == user_id), None)

    async def get_by_username(self, username: str) -> User | None:
        return next((user for user in self.users if user.username == username), None)

    async def get_by_email(self, email: str) -> User | None:
        return next((user for user in self.users if user.email == email), None)


class FakeSessionStore:
    def __init__(self) -> None:
        self.active: dict[UUID, UUID] = {}
        self.revoked: set[UUID] = set()

    async def save_refresh_session(self, jti: UUID, user_id: UUID, ttl_seconds: int) -> None:
        self.active[jti] = user_id

    async def consume_refresh_session(self, jti: UUID) -> UUID | None:
        user_id = self.active.pop(jti, None)
        if user_id is not None:
            self.revoked.add(jti)
        return user_id

    async def revoke_refresh_session(self, jti: UUID, ttl_seconds: int) -> None:
        self.active.pop(jti, None)
        self.revoked.add(jti)


@pytest.fixture
def auth_client() -> Iterator[tuple[TestClient, FakeUserRepository, FakeSessionStore]]:
    repository = FakeUserRepository()
    session_store = FakeSessionStore()
    app.dependency_overrides[get_user_repository] = lambda: repository
    app.dependency_overrides[get_session_store] = lambda: session_store
    with TestClient(app) as client:
        yield client, repository, session_store
    app.dependency_overrides.clear()
