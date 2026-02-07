"""Governance Engine FastAPI application."""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from odg_core.db.engine import create_async_engine_factory, get_async_session_factory
from odg_core.settings import DatabaseSettings, NATSSettings

from governance_engine.api.routes_audit import router as audit_router
from governance_engine.api.routes_decisions import router as decisions_router
from governance_engine.api.routes_roles import router as roles_router
from governance_engine.events.publisher import NATSPublisher

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Manage application lifecycle: DB engine + NATS startup/shutdown."""
    db_settings = DatabaseSettings()
    engine = create_async_engine_factory(db_settings)
    app.state.session_factory = get_async_session_factory(engine)

    nats_settings = NATSSettings()
    publisher = NATSPublisher()
    await publisher.connect(nats_settings.url)
    app.state.nats_publisher = publisher

    yield

    await publisher.disconnect()
    await engine.dispose()


app = FastAPI(
    title="OpenDataGov Governance Engine",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(decisions_router)
app.include_router(audit_router)
app.include_router(roles_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
async def ready() -> dict[str, str]:
    return {"status": "ready"}
