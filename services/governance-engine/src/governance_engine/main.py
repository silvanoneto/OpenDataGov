"""Governance Engine FastAPI application."""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from odg_core.db.engine import create_async_engine_factory, get_async_session_factory
from odg_core.settings import DatabaseSettings, NATSSettings
from odg_core.telemetry import init_telemetry, shutdown_telemetry
from odg_core.telemetry.db import instrument_db
from odg_core.telemetry.middleware import instrument_fastapi

from governance_engine.api.routes_audit import router as audit_router
from governance_engine.api.routes_dashboard import router as dashboard_router
from governance_engine.api.routes_decisions import router as decisions_router
from governance_engine.api.routes_graphql import graphql_router
from governance_engine.api.routes_mlops import router as mlops_router
from governance_engine.api.routes_roles import router as roles_router
from governance_engine.api.routes_self_service import router as self_service_router
from governance_engine.events.publisher import NATSPublisher
from governance_engine.webhooks.kserve import router as kserve_webhook_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:  # pragma: no cover
    """Manage application lifecycle: OTel + DB engine + NATS startup/shutdown."""
    init_telemetry("governance-engine")

    db_settings = DatabaseSettings()
    engine = create_async_engine_factory(db_settings)
    instrument_db(engine)
    app.state.session_factory = get_async_session_factory(engine)

    nats_settings = NATSSettings()
    publisher = NATSPublisher()
    await publisher.connect(nats_settings.url)
    app.state.nats_publisher = publisher

    yield

    await publisher.disconnect()
    await engine.dispose()
    shutdown_telemetry()


app = FastAPI(
    title="OpenDataGov Governance Engine",
    version="0.1.0",
    lifespan=lifespan,
)

instrument_fastapi(app)

app.include_router(decisions_router)
app.include_router(audit_router)
app.include_router(roles_router)
app.include_router(graphql_router)
app.include_router(dashboard_router)
app.include_router(self_service_router)
app.include_router(mlops_router)
app.include_router(kserve_webhook_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
async def ready() -> dict[str, str]:
    return {"status": "ready"}
