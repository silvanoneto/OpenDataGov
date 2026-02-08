"""W3C Trace Context helpers for inter-service propagation."""

from __future__ import annotations

from opentelemetry import trace
from opentelemetry.propagate import inject


def get_trace_headers() -> dict[str, str]:
    """Extract current trace context as HTTP headers for propagation.

    Use this to inject traceparent headers into outbound messages (NATS, Kafka).
    """
    headers: dict[str, str] = {}
    inject(headers)
    return headers


def get_current_trace_id() -> str:
    """Return the current trace ID as a hex string, or empty if none."""
    span = trace.get_current_span()
    ctx = span.get_span_context()
    if ctx.trace_id == 0:
        return ""
    return format(ctx.trace_id, "032x")


def get_current_span_id() -> str:
    """Return the current span ID as a hex string, or empty if none."""
    span = trace.get_current_span()
    ctx = span.get_span_context()
    if ctx.span_id == 0:
        return ""
    return format(ctx.span_id, "016x")
