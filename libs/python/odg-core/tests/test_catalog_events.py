"""Tests for odg_core.catalog.events module."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

# ──── Mock kafka module (not installed in test env) ──────────

_mock_kafka = MagicMock()
_mock_kafka_producer_cls = MagicMock()
_mock_kafka.KafkaProducer = _mock_kafka_producer_cls


@pytest.fixture(autouse=True)
def _mock_kafka_module():
    """Mock kafka module before any test imports catalog.events."""
    with patch.dict(sys.modules, {"kafka": _mock_kafka}):
        # Reset the mock producer class before each test
        _mock_kafka_producer_cls.reset_mock()
        yield


def _get_emitter_class() -> type:
    """Import CatalogEventEmitter with kafka mocked."""
    # Force re-import to pick up the mocked kafka module
    mod_key = "odg_core.catalog.events"
    if mod_key in sys.modules:
        del sys.modules[mod_key]
    from odg_core.catalog.events import CatalogEventEmitter

    return CatalogEventEmitter


# ──── CatalogEventEmitter (disabled) ────────────────────────


class TestCatalogEventEmitterDisabled:
    """Tests for CatalogEventEmitter with enabled=False."""

    def test_disabled_does_not_create_producer(self) -> None:
        emitter_cls = _get_emitter_class()
        emitter = emitter_cls(enabled=False)
        assert emitter.producer is None

    def test_emit_lakehouse_promotion_noop_when_disabled(self) -> None:
        emitter_cls = _get_emitter_class()
        emitter = emitter_cls(enabled=False)
        emitter.emit_lakehouse_promotion(
            dataset_id="ds",
            source_layer="bronze",
            target_layer="silver",
            schema=[],
            dq_score=0.9,
            promoted_by="user",
        )
        # No producer, so nothing should happen

    def test_emit_mlflow_model_registered_noop_when_disabled(self) -> None:
        emitter_cls = _get_emitter_class()
        emitter = emitter_cls(enabled=False)
        emitter.emit_mlflow_model_registered(
            model_name="m",
            model_version=1,
            mlflow_run_id="r1",
            training_datasets=[],
            features=[],
            metrics={},
        )

    def test_emit_feast_materialization_noop_when_disabled(self) -> None:
        emitter_cls = _get_emitter_class()
        emitter = emitter_cls(enabled=False)
        emitter.emit_feast_materialization(
            feature_view="fv",
            features=[],
            source_dataset="ds",
            materialization_interval="1h",
        )

    def test_emit_kubeflow_pipeline_completed_noop_when_disabled(self) -> None:
        emitter_cls = _get_emitter_class()
        emitter = emitter_cls(enabled=False)
        emitter.emit_kubeflow_pipeline_completed(
            pipeline_name="p",
            run_id="r",
            input_datasets=[],
            output_model="m",
            output_version=1,
        )


# ──── CatalogEventEmitter (enabled) ─────────────────────────


class TestCatalogEventEmitterEnabled:
    """Tests for CatalogEventEmitter with enabled=True."""

    def test_enabled_creates_producer(self) -> None:
        emitter_cls = _get_emitter_class()
        mock_producer = MagicMock()
        _mock_kafka_producer_cls.return_value = mock_producer

        emitter = emitter_cls(kafka_bootstrap_servers="kafka:9092", enabled=True)
        _mock_kafka_producer_cls.assert_called_once()
        assert emitter.producer is mock_producer

    def test_emit_lakehouse_promotion_calls_send_and_flush(self) -> None:
        emitter_cls = _get_emitter_class()
        mock_producer = MagicMock()
        _mock_kafka_producer_cls.return_value = mock_producer

        emitter = emitter_cls(enabled=True)
        emitter.emit_lakehouse_promotion(
            dataset_id="gold/revenue",
            source_layer="silver",
            target_layer="gold",
            schema=[{"name": "id", "type": "STRING"}],
            dq_score=0.95,
            promoted_by="admin",
        )

        mock_producer.send.assert_called_once()
        call_args = mock_producer.send.call_args
        assert call_args[0][0] == "odg.lakehouse.promotion"
        assert call_args[1]["value"]["dataset_id"] == "gold/revenue"
        mock_producer.flush.assert_called_once()

    def test_emit_mlflow_model_registered_calls_send(self) -> None:
        emitter_cls = _get_emitter_class()
        mock_producer = MagicMock()
        _mock_kafka_producer_cls.return_value = mock_producer

        emitter = emitter_cls(enabled=True)
        emitter.emit_mlflow_model_registered(
            model_name="churn",
            model_version=3,
            mlflow_run_id="run1",
            training_datasets=["ds1"],
            features=["f1"],
            metrics={"accuracy": 0.9},
            tags=["prod"],
        )

        mock_producer.send.assert_called_once()
        call_args = mock_producer.send.call_args
        assert call_args[0][0] == "odg.mlflow.model.registered"
        assert call_args[1]["value"]["model_name"] == "churn"

    def test_emit_feast_materialization_calls_send(self) -> None:
        emitter_cls = _get_emitter_class()
        mock_producer = MagicMock()
        _mock_kafka_producer_cls.return_value = mock_producer

        emitter = emitter_cls(enabled=True)
        emitter.emit_feast_materialization(
            feature_view="customer_features",
            features=[{"name": "f1", "type": "FLOAT"}],
            source_dataset="gold/customers",
            materialization_interval="1h",
            tags=["online"],
        )

        mock_producer.send.assert_called_once()
        call_args = mock_producer.send.call_args
        assert call_args[0][0] == "odg.feast.materialization"
        assert call_args[1]["value"]["feature_view"] == "customer_features"

    def test_emit_kubeflow_pipeline_completed_calls_send(self) -> None:
        emitter_cls = _get_emitter_class()
        mock_producer = MagicMock()
        _mock_kafka_producer_cls.return_value = mock_producer

        emitter = emitter_cls(enabled=True)
        emitter.emit_kubeflow_pipeline_completed(
            pipeline_name="train_pipeline",
            run_id="run-42",
            input_datasets=["gold/customers"],
            output_model="churn_model",
            output_version=5,
        )

        mock_producer.send.assert_called_once()
        call_args = mock_producer.send.call_args
        assert call_args[0][0] == "odg.kubeflow.pipeline.completed"
        assert call_args[1]["value"]["pipeline_name"] == "train_pipeline"

    def test_close_calls_producer_close(self) -> None:
        emitter_cls = _get_emitter_class()
        mock_producer = MagicMock()
        _mock_kafka_producer_cls.return_value = mock_producer

        emitter = emitter_cls(enabled=True)
        emitter.close()

        mock_producer.close.assert_called_once()

    def test_close_noop_when_no_producer(self) -> None:
        emitter_cls = _get_emitter_class()
        emitter = emitter_cls(enabled=False)
        # Should not raise
        emitter.close()
