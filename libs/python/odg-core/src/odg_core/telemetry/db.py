"""SQLAlchemy OpenTelemetry instrumentation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine


def instrument_db(engine: AsyncEngine) -> None:
    """Instrument a SQLAlchemy async engine with OpenTelemetry tracing."""
    SQLAlchemyInstrumentor().instrument(engine=engine.sync_engine)
