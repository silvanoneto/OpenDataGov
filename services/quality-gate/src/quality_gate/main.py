"""Quality Gate FastAPI application."""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from odg_core.db.engine import create_async_engine_factory, get_async_session_factory
from odg_core.settings import DatabaseSettings
from odg_core.telemetry import init_telemetry, shutdown_telemetry
from odg_core.telemetry.db import instrument_db
from odg_core.telemetry.middleware import instrument_fastapi

from quality_gate.api.routes import router as quality_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Manage application lifecycle: OTel + DB engine startup/shutdown."""
    init_telemetry("quality-gate")

    db_settings = DatabaseSettings()
    engine = create_async_engine_factory(db_settings)
    instrument_db(engine)
    app.state.session_factory = get_async_session_factory(engine)

    yield

    await engine.dispose()
    shutdown_telemetry()


app = FastAPI(
    title="OpenDataGov Quality Gate",
    version="0.1.0",
    lifespan=lifespan,
)

instrument_fastapi(app)

app.include_router(quality_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
async def ready() -> dict[str, str]:
    return {"status": "ready"}
