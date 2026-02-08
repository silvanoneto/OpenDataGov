"""FastAPI OpenTelemetry instrumentation helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

if TYPE_CHECKING:
    from fastapi import FastAPI


def instrument_fastapi(app: FastAPI) -> None:
    """Instrument a FastAPI app with OpenTelemetry tracing."""
    FastAPIInstrumentor.instrument_app(app)
