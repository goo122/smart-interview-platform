from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(slots=True)
class User:
    """Domain representation of a user, independent of SQLAlchemy."""

    id: UUID
    username: str
    email: str
    password_hash: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def new(cls, username: str, email: str, password_hash: str) -> "User":
        now = utc_now()
        return cls(
            id=uuid4(),
            username=username,
            email=email.lower(),
            password_hash=password_hash,
            is_active=True,
            created_at=now,
            updated_at=now,
        )
