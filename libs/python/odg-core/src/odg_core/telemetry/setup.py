"""Central OTel setup: TracerProvider, MeterProvider, auto-instrumentation."""

from __future__ import annotations

import logging

from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.propagate import set_global_textmap
from opentelemetry.propagators.composite import CompositePropagator
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

from odg_core.settings import OTelSettings

logger = logging.getLogger(__name__)

_tracer_provider: TracerProvider | None = None
_meter_provider: MeterProvider | None = None


def init_telemetry(service_name: str | None = None) -> None:
    """Initialize OpenTelemetry with OTLP gRPC exporters.

    Call once at application startup (e.g. in FastAPI lifespan).
    Safe to call multiple times — subsequent calls are no-ops.
    """
    global _tracer_provider, _meter_provider

    if _tracer_provider is not None:
        return

    settings = OTelSettings()
    if not settings.enabled:
        logger.info("OTel telemetry disabled via OTEL_ENABLED=false")
        return

    name = service_name or settings.service_name
    resource = Resource.create({SERVICE_NAME: name})
    endpoint = settings.exporter_otlp_endpoint

    # Traces
    _tracer_provider = TracerProvider(resource=resource)
    span_exporter = OTLPSpanExporter(endpoint=endpoint, insecure=True)
    _tracer_provider.add_span_processor(BatchSpanProcessor(span_exporter))
    trace.set_tracer_provider(_tracer_provider)

    # Metrics
    metric_reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(endpoint=endpoint, insecure=True),
        export_interval_millis=15_000,
    )
    _meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
    metrics.set_meter_provider(_meter_provider)

    # W3C Trace Context propagation
    set_global_textmap(CompositePropagator([TraceContextTextMapPropagator()]))

    # Auto-instrument common libraries
    HTTPXClientInstrumentor().instrument()
    RedisInstrumentor().instrument()

    logger.info("OTel telemetry initialized for '%s' → %s", name, endpoint)


def shutdown_telemetry() -> None:
    """Flush and shut down OTel providers. Call at application shutdown."""
    global _tracer_provider, _meter_provider

    if _tracer_provider is not None:
        _tracer_provider.shutdown()
        _tracer_provider = None

    if _meter_provider is not None:
        _meter_provider.shutdown()
        _meter_provider = None

    logger.info("OTel telemetry shut down")
