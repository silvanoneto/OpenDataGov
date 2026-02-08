"""Integration test: OTel telemetry initialization and trace context."""

from __future__ import annotations

import odg_core.telemetry.setup as _setup


class TestOTelPipeline:
    """Verify telemetry initializes and trace context helpers work."""

    def test_init_telemetry_creates_valid_providers(self) -> None:
        """init_telemetry() should create TracerProvider and MeterProvider."""
        # Reset global state so init_telemetry is not a no-op
        _setup._tracer_provider = None
        _setup._meter_provider = None

        _setup.init_telemetry("integration-test")

        assert _setup._tracer_provider is not None
        assert _setup._meter_provider is not None

        # Cleanup so other tests aren't affected
        _setup._tracer_provider.shutdown()
        _setup._meter_provider.shutdown()
        _setup._tracer_provider = None
        _setup._meter_provider = None

    def test_trace_context_headers_returns_dict(self) -> None:
        """get_trace_headers() should return a dict (possibly empty without active span)."""
        from odg_core.telemetry.context import get_trace_headers

        headers = get_trace_headers()
        assert isinstance(headers, dict)

    def test_trace_id_and_span_id_format(self) -> None:
        """get_current_trace_id/span_id should return empty strings without active span."""
        from odg_core.telemetry.context import get_current_span_id, get_current_trace_id

        trace_id = get_current_trace_id()
        span_id = get_current_span_id()

        # Without an active span, both return empty string
        assert isinstance(trace_id, str)
        assert isinstance(span_id, str)
