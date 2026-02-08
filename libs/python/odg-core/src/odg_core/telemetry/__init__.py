"""OpenTelemetry telemetry integration for OpenDataGov services."""

from odg_core.telemetry.setup import init_telemetry, shutdown_telemetry

__all__ = ["init_telemetry", "shutdown_telemetry"]
