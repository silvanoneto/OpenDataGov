"""Async SQLAlchemy engine and session factories."""

import logging
from collections.abc import AsyncGenerator
from urllib.parse import urlparse, urlunparse

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from odg_core.settings import DatabaseSettings

logger = logging.getLogger(__name__)


def create_async_engine_factory(
    settings: DatabaseSettings | None = None,
    use_vault: bool = True,
) -> AsyncEngine:
    """Create an async SQLAlchemy engine with connection pooling.

    Args:
        settings: Database settings (uses defaults if None)
        use_vault: Whether to try using Vault for dynamic credentials (default: True)

    Returns:
        Configured AsyncEngine instance
    """
    if settings is None:
        settings = DatabaseSettings()

    db_url = settings.url

    # Try to use Vault dynamic credentials if enabled
    if use_vault:
        try:
            from odg_core.vault.client import VaultClient

            vault = VaultClient()
            if vault.is_configured:
                logger.info("Attempting to get database credentials from Vault")
                creds = vault.get_database_credentials()

                # Parse URL and replace credentials
                parsed_url = urlparse(db_url)
                netloc_without_creds = parsed_url.hostname
                if parsed_url.port:
                    netloc_without_creds = f"{netloc_without_creds}:{parsed_url.port}"

                new_netloc = f"{creds['username']}:{creds['password']}@{netloc_without_creds}"
                db_url = urlunparse(
                    (
                        parsed_url.scheme,
                        new_netloc,
                        parsed_url.path,
                        parsed_url.params,
                        parsed_url.query,
                        parsed_url.fragment,
                    )
                )

                logger.info(
                    "Using Vault dynamic database credentials (lease: %s, duration: %ds)",
                    creds["lease_id"],
                    creds["lease_duration"],
                )
                # TODO: Implement lease renewal background task
            else:
                logger.debug("Vault not configured, using static database credentials")
        except Exception as e:
            logger.warning("Failed to get Vault credentials, falling back to static: %s", e)

    return create_async_engine(
        db_url,
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
