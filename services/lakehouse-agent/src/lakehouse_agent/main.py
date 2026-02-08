"""Lakehouse Agent FastAPI application."""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from odg_core.settings import MinIOSettings
from odg_core.telemetry import init_telemetry, shutdown_telemetry
from odg_core.telemetry.middleware import instrument_fastapi

from lakehouse_agent.api.routes_buckets import router as bucket_router
from lakehouse_agent.api.routes_promotion import router as catalog_router
from lakehouse_agent.minio_client import MinIOBucketManager
from lakehouse_agent.promotion import PromotionService

logger = logging.getLogger(__name__)

_DEFAULT_DOMAIN = "default"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Manage application lifecycle: OTel + MinIO client startup / shutdown."""
    init_telemetry("lakehouse-agent")

    settings = MinIOSettings()
    bucket_manager = MinIOBucketManager(settings)

    # Ensure the default domain buckets exist on startup.
    try:
        created = await bucket_manager.ensure_buckets(_DEFAULT_DOMAIN)
        logger.info("Default buckets ready: %s", created)
    except Exception:
        logger.warning(
            "Could not create default buckets on startup; MinIO may not be reachable yet. Continuing anyway."
        )

    app.state.bucket_manager = bucket_manager
    app.state.promotion_service = PromotionService(bucket_manager)

    yield

    shutdown_telemetry()


app = FastAPI(
    title="OpenDataGov Lakehouse Agent",
    version="0.1.0",
    lifespan=lifespan,
)

instrument_fastapi(app)

app.include_router(bucket_router)
app.include_router(catalog_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
async def ready() -> dict[str, str]:
    return {"status": "ready"}
