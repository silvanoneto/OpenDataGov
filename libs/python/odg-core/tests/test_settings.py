"""Tests for application settings defaults."""

from odg_core.settings import (
    DatabaseSettings,
    MinIOSettings,
    NATSSettings,
    OTelSettings,
    RedisSettings,
)


class TestSettingsDefaults:
    def test_database_defaults(self) -> None:
        settings = DatabaseSettings()
        assert "postgresql" in settings.url
        assert settings.pool_size == 10
        assert settings.max_overflow == 20
        assert settings.echo is False

    def test_redis_defaults(self) -> None:
        settings = RedisSettings()
        assert "redis" in settings.url
        assert settings.max_connections == 20

    def test_minio_defaults(self) -> None:
        settings = MinIOSettings()
        assert settings.endpoint == "localhost:9000"
        assert settings.access_key == "minioadmin"
        assert settings.secret_key == "minioadmin"
        assert settings.secure is False

    def test_nats_defaults(self) -> None:
        settings = NATSSettings()
        assert "nats" in settings.url

    def test_otel_defaults(self) -> None:
        settings = OTelSettings()
        assert "4317" in settings.exporter_otlp_endpoint
        assert settings.service_name == "opendatagov"
        assert settings.enabled is True
