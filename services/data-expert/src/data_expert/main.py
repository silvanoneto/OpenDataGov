"""Data Expert FastAPI application."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from odg_core.telemetry import init_telemetry, shutdown_telemetry
from odg_core.telemetry.middleware import instrument_fastapi

from data_expert.api.routes import router as expert_router
from data_expert.expert import MockDataExpert


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Manage application lifecycle: OTel + initialize and shut down the expert."""
    init_telemetry("data-expert")

    expert = MockDataExpert()
    await expert.initialize()
    app.state.expert = expert

    yield

    await expert.shutdown()
    shutdown_telemetry()


app = FastAPI(
    title="OpenDataGov Data Expert",
    version="0.1.0",
    lifespan=lifespan,
)

instrument_fastapi(app)

app.include_router(expert_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
async def ready() -> dict[str, str]:
    return {"status": "ready"}
