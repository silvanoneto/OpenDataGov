"""Tests for odg_core.connectors.base module."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from collections.abc import Iterator

from odg_core.connectors.base import (
    BaseConnector,
    ConnectorConfig,
    ConnectorStatus,
    IngestionResult,
)

# ──── Concrete subclass for testing abstract BaseConnector ────


class _DummyConnector(BaseConnector):
    """Minimal concrete connector used by tests."""

    def __init__(self, config: ConnectorConfig, records: list[dict[str, Any]] | None = None):
        super().__init__(config)
        self._records = records or []

    def connect(self) -> None:
        self._connected = True

    def extract(self, **kwargs: Any) -> Iterator[dict[str, Any]]:
        yield from self._records

    def get_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}}


# ──── ConnectorStatus ────────────────────────────────────────


class TestConnectorStatus:
    """Tests for ConnectorStatus enum values."""

    def test_pending_value(self) -> None:
        assert ConnectorStatus.PENDING.value == "pending"

    def test_running_value(self) -> None:
        assert ConnectorStatus.RUNNING.value == "running"

    def test_success_value(self) -> None:
        assert ConnectorStatus.SUCCESS.value == "success"

    def test_failed_value(self) -> None:
        assert ConnectorStatus.FAILED.value == "failed"

    def test_partial_value(self) -> None:
        assert ConnectorStatus.PARTIAL.value == "partial"

    def test_all_members_present(self) -> None:
        names = {m.name for m in ConnectorStatus}
        assert names == {"PENDING", "RUNNING", "SUCCESS", "FAILED", "PARTIAL"}


# ──── ConnectorConfig ────────────────────────────────────────


class TestConnectorConfig:
    """Tests for ConnectorConfig dataclass."""

    def test_creation_with_required_fields(self) -> None:
        cfg = ConnectorConfig(connector_type="rest_api", source_name="my_source")
        assert cfg.connector_type == "rest_api"
        assert cfg.source_name == "my_source"

    def test_defaults(self) -> None:
        cfg = ConnectorConfig(connector_type="rest_api", source_name="s")
        assert cfg.schedule is None
        assert cfg.enabled is True
        assert cfg.auth_type is None
        assert cfg.credentials == {}
        assert cfg.target_database == "bronze"
        assert cfg.target_table is None
        assert cfg.target_layer == "bronze"
        assert cfg.extract_schema is True
        assert cfg.validate_data is True
        assert cfg.batch_size == 1000
        assert cfg.tags == []
        assert cfg.metadata == {}

    def test_custom_values(self) -> None:
        cfg = ConnectorConfig(
            connector_type="web_scraper",
            source_name="scraper",
            target_layer="silver",
            batch_size=500,
            tags=["pii"],
        )
        assert cfg.target_layer == "silver"
        assert cfg.batch_size == 500
        assert cfg.tags == ["pii"]


# ──── IngestionResult ────────────────────────────────────────


class TestIngestionResult:
    """Tests for IngestionResult dataclass and success_rate property."""

    def _make_result(self, ingested: int, failed: int) -> IngestionResult:
        now = datetime.now(UTC)
        return IngestionResult(
            status=ConnectorStatus.SUCCESS,
            records_ingested=ingested,
            records_failed=failed,
            start_time=now,
            end_time=now,
            duration_seconds=0.0,
        )

    def test_success_rate_zero_total(self) -> None:
        result = self._make_result(0, 0)
        assert result.success_rate == 0.0

    def test_success_rate_half(self) -> None:
        result = self._make_result(5, 5)
        assert result.success_rate == 0.5

    def test_success_rate_all_success(self) -> None:
        result = self._make_result(10, 0)
        assert result.success_rate == 1.0

    def test_success_rate_all_failures(self) -> None:
        result = self._make_result(0, 10)
        assert result.success_rate == 0.0

    def test_default_fields(self) -> None:
        result = self._make_result(1, 0)
        assert result.error_message is None
        assert result.errors == []
        assert result.metadata == {}


# ──── BaseConnector ──────────────────────────────────────────


class TestBaseConnector:
    """Tests for BaseConnector via _DummyConnector."""

    @pytest.fixture()
    def config(self) -> ConnectorConfig:
        return ConnectorConfig(connector_type="test", source_name="test_source")

    def test_initial_connected_is_false(self, config: ConnectorConfig) -> None:
        connector = _DummyConnector(config)
        assert connector._connected is False

    def test_connect_sets_connected(self, config: ConnectorConfig) -> None:
        connector = _DummyConnector(config)
        connector.connect()
        assert connector._connected is True

    def test_disconnect_sets_connected_false(self, config: ConnectorConfig) -> None:
        connector = _DummyConnector(config)
        connector.connect()
        assert connector._connected is True
        connector.disconnect()
        assert connector._connected is False

    def test_validate_record_valid_dict(self, config: ConnectorConfig) -> None:
        connector = _DummyConnector(config)
        valid, msg = connector.validate_record({"key": "value"})
        assert valid is True
        assert msg is None

    def test_validate_record_empty_dict(self, config: ConnectorConfig) -> None:
        connector = _DummyConnector(config)
        valid, msg = connector.validate_record({})
        assert valid is True
        assert msg is None

    def test_validate_record_non_dict_string(self, config: ConnectorConfig) -> None:
        connector = _DummyConnector(config)
        valid, msg = connector.validate_record("not a dict")  # type: ignore[arg-type]
        assert valid is False
        assert msg is not None
        assert "dictionary" in msg.lower()

    def test_validate_record_non_dict_list(self, config: ConnectorConfig) -> None:
        connector = _DummyConnector(config)
        valid, msg = connector.validate_record([1, 2])  # type: ignore[arg-type]
        assert valid is False
        assert msg is not None

    def test_validate_record_non_dict_none(self, config: ConnectorConfig) -> None:
        connector = _DummyConnector(config)
        valid, _ = connector.validate_record(None)  # type: ignore[arg-type]
        assert valid is False

    def test_extract_yields_records(self, config: ConnectorConfig) -> None:
        records = [{"a": 1}, {"b": 2}]
        connector = _DummyConnector(config, records=records)
        assert list(connector.extract()) == records

    def test_get_schema_returns_dict(self, config: ConnectorConfig) -> None:
        connector = _DummyConnector(config)
        schema = connector.get_schema()
        assert isinstance(schema, dict)
        assert schema["type"] == "object"
