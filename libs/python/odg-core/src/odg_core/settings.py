"""Application settings via Pydantic Settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """PostgreSQL connection settings."""

    model_config = SettingsConfigDict(env_prefix="DATABASE_")

    url: str = "postgresql+asyncpg://odg:odg@localhost:5432/odg"
    pool_size: int = 10
    max_overflow: int = 20
    echo: bool = False


class RedisSettings(BaseSettings):
    """Redis connection settings."""

    model_config = SettingsConfigDict(env_prefix="REDIS_")

    url: str = "redis://localhost:6379/0"
    max_connections: int = 20


class MinIOSettings(BaseSettings):
    """MinIO connection settings."""

    model_config = SettingsConfigDict(env_prefix="MINIO_")

    endpoint: str = "localhost:9000"
    access_key: str = "minioadmin"
    secret_key: str = "minioadmin"
    secure: bool = False


class NATSSettings(BaseSettings):
    """NATS connection settings."""

    model_config = SettingsConfigDict(env_prefix="NATS_")

    url: str = "nats://localhost:4222"


class OTelSettings(BaseSettings):
    """OpenTelemetry settings."""

    model_config = SettingsConfigDict(env_prefix="OTEL_")

    exporter_otlp_endpoint: str = "http://localhost:4317"
    service_name: str = "opendatagov"
    enabled: bool = True


class KafkaSettings(BaseSettings):
    """Kafka connection settings."""

    model_config = SettingsConfigDict(env_prefix="KAFKA_")

    bootstrap_servers: str = "localhost:9092"
    audit_topic: str = "odg.audit.events"
    audit_retention_ms: int = 31_536_000_000  # 1 year


class DataHubSettings(BaseSettings):
    """DataHub catalog settings."""

    model_config = SettingsConfigDict(env_prefix="DATAHUB_")

    gms_url: str = "http://localhost:8080"
    enabled: bool = False


class KeycloakSettings(BaseSettings):
    """Keycloak OIDC settings."""

    model_config = SettingsConfigDict(env_prefix="KEYCLOAK_")

    server_url: str = "http://localhost:8180"
    realm: str = "opendatagov"
    client_id: str = "odg-api"
    enabled: bool = False


class OPASettings(BaseSettings):
    """OPA policy engine settings."""

    model_config = SettingsConfigDict(env_prefix="OPA_")

    url: str = "http://localhost:8181"
    enabled: bool = False


class VaultSettings(BaseSettings):
    """HashiCorp Vault settings."""

    model_config = SettingsConfigDict(env_prefix="VAULT_")

    addr: str = "http://localhost:8200"
    token: str = ""
    enabled: bool = False
