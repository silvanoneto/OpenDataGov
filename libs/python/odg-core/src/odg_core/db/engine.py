"""Async SQLAlchemy engine and session factories."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from odg_core.settings import DatabaseSettings


def create_async_engine_factory(settings: DatabaseSettings | None = None) -> AsyncEngine:
    """Create an async SQLAlchemy engine with connection pooling."""
    if settings is None:
        settings = DatabaseSettings()

    return create_async_engine(
        settings.url,
        pool_size=settings.pool_size,
        max_overflow=settings.max_overflow,
        echo=settings.echo,
    )


def get_async_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create an async session factory bound to the given engine."""
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncSession]:
    """Yield an async session for dependency injection."""
    async with session_factory() as session:
        yield session
