"""Tests for odg_core.cdc.cdc_consumer module."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from odg_core.cdc.cdc_consumer import (
    CDCConsumer,
    CDCEvent,
    CDCOperation,
    sync_to_cache,
    sync_to_elasticsearch,
    trigger_workflow,
)

# ── CDCOperation enum ────────────────────────────────────────


class TestCDCOperation:
    def test_create(self) -> None:
        assert CDCOperation.CREATE.value == "c"

    def test_update(self) -> None:
        assert CDCOperation.UPDATE.value == "u"

    def test_delete(self) -> None:
        assert CDCOperation.DELETE.value == "d"

    def test_read(self) -> None:
        assert CDCOperation.READ.value == "r"


# ── CDCEvent model ────────────────────────────────────────────


class TestCDCEvent:
    def test_create_event(self) -> None:
        event = CDCEvent(
            operation=CDCOperation.CREATE,
            table_name="governance_decisions",
            schema_name="public",
            database="odg",
            after={"id": 1, "title": "Test"},
            source_timestamp=datetime(2026, 1, 1),
            event_timestamp=datetime(2026, 1, 1),
            connector_name="odg_postgres",
        )
        assert event.operation == CDCOperation.CREATE
        assert event.table_name == "governance_decisions"
        assert event.before is None
        assert event.after == {"id": 1, "title": "Test"}
        assert event.lsn is None
        assert event.transaction_id is None
        assert event.is_snapshot is False

    def test_update_event(self) -> None:
        event = CDCEvent(
            operation=CDCOperation.UPDATE,
            table_name="model_cards",
            schema_name="public",
            database="odg",
            before={"id": 1, "status": "draft"},
            after={"id": 1, "status": "approved"},
            source_timestamp=datetime(2026, 1, 1),
            event_timestamp=datetime(2026, 1, 1),
            connector_name="odg_postgres",
            lsn=12345,
        )
        assert event.operation == CDCOperation.UPDATE
        assert event.before is not None
        assert event.after is not None
        assert event.lsn == 12345

    def test_delete_event(self) -> None:
        event = CDCEvent(
            operation=CDCOperation.DELETE,
            table_name="test_table",
            schema_name="public",
            database="odg",
            before={"id": 1},
            source_timestamp=datetime(2026, 1, 1),
            event_timestamp=datetime(2026, 1, 1),
            connector_name="odg_postgres",
        )
        assert event.operation == CDCOperation.DELETE
        assert event.after is None


# ── CDCConsumer ───────────────────────────────────────────────


class TestCDCConsumer:
    def test_init_defaults(self) -> None:
        consumer = CDCConsumer()
        assert consumer.bootstrap_servers == "kafka:9092"
        assert consumer.group_id == "cdc-consumer-group"
        assert consumer.auto_offset_reset == "earliest"
        assert consumer._consumer is None

    def test_init_custom(self) -> None:
        consumer = CDCConsumer(
            bootstrap_servers="kafka:9094",
            group_id="my-group",
            auto_offset_reset="latest",
        )
        assert consumer.bootstrap_servers == "kafka:9094"
        assert consumer.group_id == "my-group"

    def test_consume_raises_when_not_subscribed(self) -> None:
        consumer = CDCConsumer()
        with pytest.raises(RuntimeError, match="Consumer not subscribed"):
            list(consumer.consume())

    def test_close_when_consumer_is_none(self) -> None:
        consumer = CDCConsumer()
        consumer.close()  # Should not raise

    def test_close_with_consumer(self) -> None:
        consumer = CDCConsumer()
        mock_consumer = MagicMock()
        consumer._consumer = mock_consumer  # type: ignore[assignment]
        consumer.close()
        mock_consumer.close.assert_called_once()

    def test_parse_event_valid(self) -> None:
        consumer = CDCConsumer()
        raw = {
            "op": "c",
            "before": None,
            "after": {"id": 1, "name": "test"},
            "source": {
                "version": "2.5.0.Final",
                "connector": "postgresql",
                "name": "odg_postgres",
                "ts_ms": 1707392400000,
                "snapshot": "false",
                "db": "odg",
                "schema": "public",
                "table": "governance_decisions",
                "lsn": 12345,
            },
            "ts_ms": 1707392400100,
            "transaction": None,
        }
        event = consumer._parse_event(raw)
        assert event is not None
        assert event.operation == CDCOperation.CREATE
        assert event.table_name == "governance_decisions"
        assert event.database == "odg"
        assert event.after == {"id": 1, "name": "test"}
        assert event.lsn == 12345
        assert event.is_snapshot is False
        assert event.connector_name == "odg_postgres"

    def test_parse_event_snapshot(self) -> None:
        consumer = CDCConsumer()
        raw = {
            "op": "r",
            "before": None,
            "after": {"id": 1},
            "source": {
                "name": "test",
                "ts_ms": 1000,
                "snapshot": "true",
                "db": "odg",
                "schema": "public",
                "table": "test_table",
            },
            "ts_ms": 2000,
        }
        event = consumer._parse_event(raw)
        assert event is not None
        assert event.operation == CDCOperation.READ
        assert event.is_snapshot is True

    def test_parse_event_heartbeat_returns_none(self) -> None:
        consumer = CDCConsumer()
        raw = {"source": {}, "ts_ms": 0}
        event = consumer._parse_event(raw)
        assert event is None

    def test_parse_event_with_transaction(self) -> None:
        consumer = CDCConsumer()
        raw = {
            "op": "u",
            "before": {"id": 1},
            "after": {"id": 1, "updated": True},
            "source": {
                "name": "test",
                "ts_ms": 1000,
                "db": "odg",
                "schema": "public",
                "table": "test_table",
            },
            "ts_ms": 2000,
            "transaction": {"id": "tx-123"},
        }
        event = consumer._parse_event(raw)
        assert event is not None
        assert event.transaction_id == "tx-123"

    def test_parse_event_invalid_returns_none(self) -> None:
        consumer = CDCConsumer()
        # Invalid operation value
        raw = {
            "op": "INVALID",
            "source": {"name": "test", "ts_ms": 0, "db": "odg", "schema": "public", "table": "t"},
            "ts_ms": 0,
        }
        event = consumer._parse_event(raw)
        assert event is None

    def test_consume_yields_events(self) -> None:
        consumer = CDCConsumer()
        mock_kafka_consumer = MagicMock()
        consumer._consumer = mock_kafka_consumer  # type: ignore[assignment]

        msg1 = MagicMock()
        msg1.value = {
            "op": "c",
            "before": None,
            "after": {"id": 1},
            "source": {"name": "test", "ts_ms": 1000, "db": "odg", "schema": "public", "table": "items"},
            "ts_ms": 2000,
        }
        msg2 = MagicMock()
        msg2.value = {
            "op": "u",
            "before": {"id": 1},
            "after": {"id": 1, "name": "updated"},
            "source": {"name": "test", "ts_ms": 1000, "db": "odg", "schema": "public", "table": "items"},
            "ts_ms": 3000,
        }
        mock_kafka_consumer.__iter__ = MagicMock(return_value=iter([msg1, msg2]))

        events = list(consumer.consume())
        assert len(events) == 2
        assert events[0].operation == CDCOperation.CREATE
        assert events[1].operation == CDCOperation.UPDATE


# ── sync_to_cache ─────────────────────────────────────────────


class TestSyncToCache:
    def test_create_sets_cache(self) -> None:
        event = CDCEvent(
            operation=CDCOperation.CREATE,
            table_name="items",
            schema_name="public",
            database="odg",
            after={"id": 1, "name": "test"},
            source_timestamp=datetime(2026, 1, 1),
            event_timestamp=datetime(2026, 1, 1),
            connector_name="test",
        )
        mock_cache = MagicMock()
        sync_to_cache(event, mock_cache)
        mock_cache.set.assert_called_once()

    def test_update_sets_cache(self) -> None:
        event = CDCEvent(
            operation=CDCOperation.UPDATE,
            table_name="items",
            schema_name="public",
            database="odg",
            before={"id": 1},
            after={"id": 1, "name": "updated"},
            source_timestamp=datetime(2026, 1, 1),
            event_timestamp=datetime(2026, 1, 1),
            connector_name="test",
        )
        mock_cache = MagicMock()
        sync_to_cache(event, mock_cache)
        mock_cache.set.assert_called_once()

    def test_delete_removes_from_cache(self) -> None:
        event = CDCEvent(
            operation=CDCOperation.DELETE,
            table_name="items",
            schema_name="public",
            database="odg",
            before={"id": 1},
            after={"id": 1},
            source_timestamp=datetime(2026, 1, 1),
            event_timestamp=datetime(2026, 1, 1),
            connector_name="test",
        )
        mock_cache = MagicMock()
        sync_to_cache(event, mock_cache)
        mock_cache.delete.assert_called_once()


# ── sync_to_elasticsearch ─────────────────────────────────────


class TestSyncToElasticsearch:
    def test_create_indexes_document(self) -> None:
        event = CDCEvent(
            operation=CDCOperation.CREATE,
            table_name="items",
            schema_name="public",
            database="odg",
            after={"id": 1, "name": "test"},
            source_timestamp=datetime(2026, 1, 1),
            event_timestamp=datetime(2026, 1, 1),
            connector_name="test",
        )
        mock_es = MagicMock()
        sync_to_elasticsearch(event, mock_es)
        mock_es.index.assert_called_once_with(index="cdc_items", id=1, document={"id": 1, "name": "test"})

    def test_delete_removes_document(self) -> None:
        event = CDCEvent(
            operation=CDCOperation.DELETE,
            table_name="items",
            schema_name="public",
            database="odg",
            before={"id": 1},
            source_timestamp=datetime(2026, 1, 1),
            event_timestamp=datetime(2026, 1, 1),
            connector_name="test",
        )
        mock_es = MagicMock()
        sync_to_elasticsearch(event, mock_es)
        mock_es.delete.assert_called_once_with(index="cdc_items", id=1, ignore=[404])

    def test_update_indexes_document(self) -> None:
        event = CDCEvent(
            operation=CDCOperation.UPDATE,
            table_name="items",
            schema_name="public",
            database="odg",
            before={"id": 1},
            after={"id": 1, "name": "updated"},
            source_timestamp=datetime(2026, 1, 1),
            event_timestamp=datetime(2026, 1, 1),
            connector_name="test",
        )
        mock_es = MagicMock()
        sync_to_elasticsearch(event, mock_es)
        mock_es.index.assert_called_once()


# ── trigger_workflow ──────────────────────────────────────────


class TestTriggerWorkflow:
    def test_governance_decision_create(self) -> None:
        event = CDCEvent(
            operation=CDCOperation.CREATE,
            table_name="governance_decisions",
            schema_name="public",
            database="odg",
            after={"id": 1, "title": "Approve dataset"},
            source_timestamp=datetime(2026, 1, 1),
            event_timestamp=datetime(2026, 1, 1),
            connector_name="test",
        )
        trigger_workflow(event)  # Should not raise

    def test_pipeline_execution_failed(self) -> None:
        event = CDCEvent(
            operation=CDCOperation.UPDATE,
            table_name="pipeline_executions",
            schema_name="public",
            database="odg",
            after={"pipeline_id": "p1", "status": "failed"},
            source_timestamp=datetime(2026, 1, 1),
            event_timestamp=datetime(2026, 1, 1),
            connector_name="test",
        )
        trigger_workflow(event)  # Should not raise

    def test_model_card_update(self) -> None:
        event = CDCEvent(
            operation=CDCOperation.UPDATE,
            table_name="model_cards",
            schema_name="public",
            database="odg",
            after={"model_name": "churn_v1"},
            source_timestamp=datetime(2026, 1, 1),
            event_timestamp=datetime(2026, 1, 1),
            connector_name="test",
        )
        trigger_workflow(event)  # Should not raise

    def test_unhandled_table(self) -> None:
        event = CDCEvent(
            operation=CDCOperation.CREATE,
            table_name="random_table",
            schema_name="public",
            database="odg",
            after={"id": 1},
            source_timestamp=datetime(2026, 1, 1),
            event_timestamp=datetime(2026, 1, 1),
            connector_name="test",
        )
        trigger_workflow(event)  # Should not raise
