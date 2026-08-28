from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base metadata shared by SQLAlchemy models and Alembic."""


def create_database_engine(database_url: str) -> AsyncEngine:
    """Create the asynchronous SQLAlchemy engine without opening a database connection."""

    return create_async_engine(database_url, pool_pre_ping=True)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create a typed async session factory for future repositories."""

    return async_sessionmaker(engine, expire_on_commit=False)
