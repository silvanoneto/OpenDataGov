"""Catalog event emitters for automatic metadata ingestion.

Emits Kafka events that trigger DataHub metadata ingestion:
- Lakehouse layer promotions
- MLflow model registrations
- Feast feature materializations
- Kubeflow pipeline completions
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from kafka import KafkaProducer

logger = logging.getLogger(__name__)


class CatalogEventEmitter:
    """Emits catalog events to Kafka for automatic metadata ingestion."""

    def __init__(
        self,
        kafka_bootstrap_servers: str = "kafka:9092",
        enabled: bool = True,
    ):
        """Initialize catalog event emitter.

        Args:
            kafka_bootstrap_servers: Kafka bootstrap servers
            enabled: Enable/disable event emission
        """
        self.enabled = enabled
        self.kafka_bootstrap_servers = kafka_bootstrap_servers

        if enabled:
            self.producer = KafkaProducer(
                bootstrap_servers=kafka_bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            )
            logger.info(f"Catalog event emitter initialized (Kafka: {kafka_bootstrap_servers})")
        else:
            self.producer = None
            logger.info("Catalog event emitter disabled")

    def emit_lakehouse_promotion(
        self,
        dataset_id: str,
        source_layer: str,
        target_layer: str,
        schema: list[dict[str, Any]],
        dq_score: float,
        promoted_by: str,
    ) -> None:
        """Emit lakehouse promotion event.

        Triggers automatic DataHub registration of the promoted dataset.

        Args:
            dataset_id: Dataset identifier
            source_layer: Source layer (bronze, silver, gold)
            target_layer: Target layer (silver, gold, platinum)
            schema: Dataset schema
            dq_score: Data quality score
            promoted_by: User who promoted the dataset
        """
        if not self.enabled or self.producer is None:
            return

        event = {
            "dataset_id": dataset_id,
            "source_layer": source_layer,
            "target_layer": target_layer,
            "schema": schema,
            "dq_score": dq_score,
            "promoted_by": promoted_by,
            "promoted_at": datetime.now().isoformat(),
        }

        self.producer.send("odg.lakehouse.promotion", value=event)
        self.producer.flush()

        logger.info(f"Emitted lakehouse promotion event: {dataset_id} ({source_layer} → {target_layer})")

    def emit_mlflow_model_registered(
        self,
        model_name: str,
        model_version: int,
        mlflow_run_id: str,
        training_datasets: list[str],
        features: list[str],
        metrics: dict[str, float],
        tags: list[str] | None = None,
    ) -> None:
        """Emit MLflow model registration event.

        Triggers automatic DataHub registration of the ML model.

        Args:
            model_name: Model name
            model_version: Model version
            mlflow_run_id: MLflow run ID
            training_datasets: Training dataset IDs
            features: Feature names
            metrics: Performance metrics
            tags: Model tags
        """
        if not self.enabled or self.producer is None:
            return

        event = {
            "model_name": model_name,
            "model_version": model_version,
            "mlflow_run_id": mlflow_run_id,
            "training_datasets": training_datasets,
            "features": features,
            "metrics": metrics,
            "tags": tags or [],
            "registered_at": datetime.now().isoformat(),
        }

        self.producer.send("odg.mlflow.model.registered", value=event)
        self.producer.flush()

        logger.info(f"Emitted MLflow model event: {model_name} v{model_version}")

    def emit_feast_materialization(
        self,
        feature_view: str,
        features: list[dict[str, str]],
        source_dataset: str,
        materialization_interval: str,
        tags: list[str] | None = None,
    ) -> None:
        """Emit Feast feature materialization event.

        Triggers automatic DataHub registration of the feature view.

        Args:
            feature_view: Feature view name
            features: Feature definitions
            source_dataset: Source dataset ID
            materialization_interval: Materialization interval
            tags: Feature tags
        """
        if not self.enabled or self.producer is None:
            return

        event = {
            "feature_view": feature_view,
            "features": features,
            "source_dataset": source_dataset,
            "materialization_interval": materialization_interval,
            "tags": tags or [],
            "materialized_at": datetime.now().isoformat(),
        }

        self.producer.send("odg.feast.materialization", value=event)
        self.producer.flush()

        logger.info(f"Emitted Feast materialization event: {feature_view}")

    def emit_kubeflow_pipeline_completed(
        self,
        pipeline_name: str,
        run_id: str,
        input_datasets: list[str],
        output_model: str,
        output_version: int,
    ) -> None:
        """Emit Kubeflow pipeline completion event.

        Triggers automatic DataHub lineage tracking for the pipeline.

        Args:
            pipeline_name: Pipeline name
            run_id: Pipeline run ID
            input_datasets: Input dataset IDs
            output_model: Output model name
            output_version: Output model version
        """
        if not self.enabled or self.producer is None:
            return

        event = {
            "pipeline_name": pipeline_name,
            "run_id": run_id,
            "input_datasets": input_datasets,
            "output_model": output_model,
            "output_version": output_version,
            "completed_at": datetime.now().isoformat(),
        }

        self.producer.send("odg.kubeflow.pipeline.completed", value=event)
        self.producer.flush()

        logger.info(f"Emitted Kubeflow pipeline event: {pipeline_name} (run: {run_id})")

    def close(self) -> None:
        """Close Kafka producer."""
        if self.producer:
            self.producer.close()
            logger.info("Catalog event emitter closed")


# Global emitter instance (singleton)
_emitter: CatalogEventEmitter | None = None


def get_emitter(
    kafka_bootstrap_servers: str = "kafka:9092",
    enabled: bool = True,
) -> CatalogEventEmitter:
    """Get or create global catalog event emitter.

    Args:
        kafka_bootstrap_servers: Kafka bootstrap servers
        enabled: Enable/disable event emission

    Returns:
        CatalogEventEmitter instance
    """
    global _emitter
    if _emitter is None:
        _emitter = CatalogEventEmitter(
            kafka_bootstrap_servers=kafka_bootstrap_servers,
            enabled=enabled,
        )
    return _emitter
