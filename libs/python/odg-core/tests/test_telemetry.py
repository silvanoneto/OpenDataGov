"""Tests for OpenTelemetry telemetry setup, context helpers, db, and middleware."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from opentelemetry.sdk.trace import TracerProvider

from odg_core.telemetry.context import (
    get_current_span_id,
    get_current_trace_id,
    get_trace_headers,
)
from odg_core.telemetry.db import instrument_db
from odg_core.telemetry.middleware import instrument_fastapi
from odg_core.telemetry.setup import (
    init_telemetry,
    shutdown_telemetry,
)


class TestInitTelemetry:
    def test_init_creates_providers(self) -> None:
        """init_telemetry should set global tracer and meter providers."""
        with patch("odg_core.telemetry.setup.OTelSettings") as mock_settings:
            mock_settings.return_value.enabled = True
            mock_settings.return_value.service_name = "test-service"
            mock_settings.return_value.exporter_otlp_endpoint = "localhost:4317"

            # Reset module state
            import odg_core.telemetry.setup as setup_mod

            setup_mod._tracer_provider = None
            setup_mod._meter_provider = None

            init_telemetry("test-service")

            assert setup_mod._tracer_provider is not None
            assert setup_mod._meter_provider is not None

            # Cleanup
            setup_mod._tracer_provider.shutdown()
            setup_mod._meter_provider.shutdown()
            setup_mod._tracer_provider = None
            setup_mod._meter_provider = None

    def test_init_is_idempotent(self) -> None:
        """Calling init_telemetry twice should not create new providers."""
        with patch("odg_core.telemetry.setup.OTelSettings") as mock_settings:
            mock_settings.return_value.enabled = True
            mock_settings.return_value.service_name = "test-service"
            mock_settings.return_value.exporter_otlp_endpoint = "localhost:4317"

            import odg_core.telemetry.setup as setup_mod

            setup_mod._tracer_provider = None
            setup_mod._meter_provider = None

            init_telemetry("test-service")
            first_tp = setup_mod._tracer_provider

            init_telemetry("test-service")
            assert setup_mod._tracer_provider is first_tp

            # Cleanup
            assert setup_mod._tracer_provider is not None
            assert setup_mod._meter_provider is not None
            setup_mod._tracer_provider.shutdown()
            setup_mod._meter_provider.shutdown()
            setup_mod._tracer_provider = None
            setup_mod._meter_provider = None

    def test_disabled_skips_init(self) -> None:
        """When OTEL_ENABLED=false, providers should not be created."""
        with patch("odg_core.telemetry.setup.OTelSettings") as mock_settings:
            mock_settings.return_value.enabled = False

            import odg_core.telemetry.setup as setup_mod

            setup_mod._tracer_provider = None
            setup_mod._meter_provider = None

            init_telemetry("test-service")

            assert setup_mod._tracer_provider is None
            assert setup_mod._meter_provider is None


class TestContextHelpers:
    def test_get_trace_headers_without_span(self) -> None:
        """Without an active span, headers should be empty or minimal."""
        headers = get_trace_headers()
        assert isinstance(headers, dict)

    def test_get_current_trace_id_without_span(self) -> None:
        """Without an active span, trace ID should be empty."""
        trace_id = get_current_trace_id()
        assert trace_id == ""

    def test_get_current_span_id_without_span(self) -> None:
        """Without an active span, span ID should be empty."""
        span_id = get_current_span_id()
        assert span_id == ""

    def test_get_ids_with_active_span(self) -> None:
        """With an active span, trace and span IDs should be hex strings."""
        tp = TracerProvider()
        tracer = tp.get_tracer("test")

        with tracer.start_as_current_span("test-span"):
            trace_id = get_current_trace_id()
            span_id = get_current_span_id()

            assert len(trace_id) == 32
            assert len(span_id) == 16
            assert all(c in "0123456789abcdef" for c in trace_id)
            assert all(c in "0123456789abcdef" for c in span_id)

        tp.shutdown()


class TestShutdownTelemetry:
    def test_shutdown_clears_providers(self) -> None:
        """shutdown_telemetry should clear both providers."""
        with patch("odg_core.telemetry.setup.OTelSettings") as mock_settings:
            mock_settings.return_value.enabled = True
            mock_settings.return_value.service_name = "test-service"
            mock_settings.return_value.exporter_otlp_endpoint = "localhost:4317"

            import odg_core.telemetry.setup as setup_mod

            setup_mod._tracer_provider = None
            setup_mod._meter_provider = None

            init_telemetry("test-service")
            assert setup_mod._tracer_provider is not None
            assert setup_mod._meter_provider is not None

            shutdown_telemetry()

            assert setup_mod._tracer_provider is None
            assert setup_mod._meter_provider is None

    def test_shutdown_when_not_initialized(self) -> None:
        """shutdown_telemetry should be safe when providers are None."""
        import odg_core.telemetry.setup as setup_mod

        setup_mod._tracer_provider = None
        setup_mod._meter_provider = None

        shutdown_telemetry()


class TestInstrumentDb:
    def test_instrument_db_calls_instrumentor(self) -> None:
        """instrument_db should call SQLAlchemyInstrumentor.instrument with sync_engine."""
        mock_engine = MagicMock()
        mock_sync_engine = MagicMock()
        mock_engine.sync_engine = mock_sync_engine

        with patch("odg_core.telemetry.db.SQLAlchemyInstrumentor") as mock_instrumentor_cls:
            mock_instrumentor = MagicMock()
            mock_instrumentor_cls.return_value = mock_instrumentor

            instrument_db(mock_engine)

            mock_instrumentor_cls.assert_called_once()
            mock_instrumentor.instrument.assert_called_once_with(engine=mock_sync_engine)

    def test_instrument_db_passes_sync_engine(self) -> None:
        """instrument_db should extract sync_engine from the async engine."""
        mock_engine = MagicMock()
        mock_engine.sync_engine = "the-sync-engine"

        with patch("odg_core.telemetry.db.SQLAlchemyInstrumentor") as mock_instrumentor_cls:
            mock_instrumentor = MagicMock()
            mock_instrumentor_cls.return_value = mock_instrumentor

            instrument_db(mock_engine)

            call_kwargs = mock_instrumentor.instrument.call_args[1]
            assert call_kwargs["engine"] == "the-sync-engine"


class TestInstrumentFastAPI:
    def test_instrument_fastapi_calls_instrumentor(self) -> None:
        """instrument_fastapi should call FastAPIInstrumentor.instrument_app."""
        mock_app = MagicMock()

        with patch("odg_core.telemetry.middleware.FastAPIInstrumentor") as mock_instrumentor_cls:
            instrument_fastapi(mock_app)

            mock_instrumentor_cls.instrument_app.assert_called_once_with(mock_app)

    def test_instrument_fastapi_passes_app_object(self) -> None:
        """instrument_fastapi should pass the app instance directly."""
        mock_app = MagicMock(name="my-fastapi-app")

        with patch("odg_core.telemetry.middleware.FastAPIInstrumentor") as mock_instrumentor_cls:
            instrument_fastapi(mock_app)

            call_args = mock_instrumentor_cls.instrument_app.call_args[0]
            assert call_args[0] is mock_app
