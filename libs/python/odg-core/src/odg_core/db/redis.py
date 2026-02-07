"""Redis async connection pool factory."""

from redis.asyncio import ConnectionPool, Redis

from odg_core.settings import RedisSettings


def create_redis_pool(settings: RedisSettings | None = None) -> Redis:
    """Create a Redis client with an async connection pool."""
    if settings is None:
        settings = RedisSettings()

    pool = ConnectionPool.from_url(
        settings.url,
        max_connections=settings.max_connections,
        decode_responses=True,
    )
    return Redis(connection_pool=pool)
