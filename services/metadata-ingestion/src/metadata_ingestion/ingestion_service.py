"""Metadata Ingestion Service for DataHub.

Automatically ingests metadata into DataHub from:
- Lakehouse layer promotions (Bronze → Silver → Gold → Platinum)
- MLflow model registrations
- Feast feature view materializations
- Kubeflow pipeline executions

Event-driven architecture using Kafka.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from kafka import KafkaConsumer
from odg_core.catalog import DataHubClient

logger = logging.getLogger(__name__)


class MetadataIngestionService:
    """Automated metadata ingestion service.

    Listens to Kafka topics and automatically:
    1. Registers datasets in DataHub
    2. Tracks lineage relationships
    3. Adds governance tags
    4. Updates metadata on changes
    """

    def __init__(
        self,
        kafka_bootstrap_servers: str = "kafka:9092",
        datahub_gms_url: str = "http://datahub-gms:8080",
        consumer_group: str = "metadata-ingestion",
    ):
        """Initialize metadata ingestion service.

        Args:
            kafka_bootstrap_servers: Kafka bootstrap servers
            datahub_gms_url: DataHub GMS URL
            consumer_group: Kafka consumer group ID
        """
        self.kafka_bootstrap_servers = kafka_bootstrap_servers
        self.datahub_client = DataHubClient(gms_url=datahub_gms_url)
        self.consumer_group = consumer_group

        # Initialize Kafka consumers for different topics
        self.topics = [
            "odg.lakehouse.promotion",  # Dataset promotions
            "odg.mlflow.model.registered",  # MLflow model registrations
            "odg.feast.materialization",  # Feast feature materializations
            "odg.kubeflow.pipeline.completed",  # Kubeflow pipeline completions
        ]

        logger.info(f"Metadata Ingestion Service initialized (topics: {self.topics})")

    def start(self) -> None:
        """Start consuming Kafka events and ingesting metadata."""
        consumer = KafkaConsumer(
            *self.topics,
            bootstrap_servers=self.kafka_bootstrap_servers,
            group_id=self.consumer_group,
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
            auto_offset_reset="earliest",
            enable_auto_commit=True,
        )

        logger.info("Starting metadata ingestion service...")

        try:
            for message in consumer:
                self._process_event(message.topic, message.value)
        except KeyboardInterrupt:
            logger.info("Shutting down metadata ingestion service...")
        finally:
            consumer.close()

    def _process_event(self, topic: str, event: dict[str, Any]) -> None:
        """Process Kafka event and ingest metadata.

        Args:
            topic: Kafka topic name
            event: Event payload
        """
        try:
            if topic == "odg.lakehouse.promotion":
                self._handle_lakehouse_promotion(event)
            elif topic == "odg.mlflow.model.registered":
                self._handle_mlflow_model(event)
            elif topic == "odg.feast.materialization":
                self._handle_feast_materialization(event)
            elif topic == "odg.kubeflow.pipeline.completed":
                self._handle_kubeflow_pipeline(event)
            else:
                logger.warning(f"Unknown topic: {topic}")

        except Exception as e:
            logger.error(f"Failed to process event from {topic}: {e}", exc_info=True)

    def _handle_lakehouse_promotion(self, event: dict[str, Any]) -> None:
        """Handle lakehouse layer promotion event.

        Event structure:
        {
            "dataset_id": "finance/revenue",
            "source_layer": "bronze",
            "target_layer": "silver",
            "schema": [...],
            "dq_score": 0.96,
            "promoted_at": "2026-02-08T10:30:00Z"
        }
        """
        dataset_id = event["dataset_id"]
        target_layer = event["target_layer"]
        source_layer = event["source_layer"]
        schema = event.get("schema", [])
        dq_score = event.get("dq_score", 0.0)

        logger.info(f"Processing lakehouse promotion: {dataset_id} ({source_layer} → {target_layer})")

        # Register dataset in DataHub
        tags = [f"{target_layer}_layer"]

        # Add quality tags
        if target_layer == "gold" and dq_score >= 0.95:
            tags.append("gold_layer")
            tags.append("high_quality")
        if dq_score >= 0.98:
            tags.append("production")

        # Check for PII in schema
        if any("pii" in field.get("tags", []) for field in schema):
            tags.extend(["pii", "gdpr"])

        self.datahub_client.register_dataset(
            dataset_id=f"{target_layer}/{dataset_id}",
            name=f"{dataset_id.replace('/', ' ').title()} ({target_layer.capitalize()})",
            platform="s3",
            layer=target_layer,
            schema=schema,
            tags=tags,
            description=f"Promoted from {source_layer} layer (DQ score: {dq_score:.2f})",
            owner=event.get("promoted_by", "system"),
        )

        # Add lineage relationship
        self.datahub_client.add_lineage(
            downstream_urn=f"urn:li:dataset:(urn:li:dataPlatform:s3,{target_layer}/{dataset_id},PROD)",
            upstream_urns=[f"urn:li:dataset:(urn:li:dataPlatform:s3,{source_layer}/{dataset_id},PROD)"],
            lineage_type="transformation",
            transformation_description=f"Promoted {source_layer} → {target_layer} (DQ score: {dq_score:.2f})",
        )

        logger.info(f"✓ Registered {target_layer}/{dataset_id} in DataHub")

    def _handle_mlflow_model(self, event: dict[str, Any]) -> None:
        """Handle MLflow model registration event.

        Event structure:
        {
            "model_name": "customer-churn",
            "model_version": 3,
            "mlflow_run_id": "abc123",
            "training_datasets": ["gold/crm/customers"],
            "features": ["total_purchases", "avg_order_value"],
            "metrics": {"accuracy": 0.92, "f1_score": 0.89},
            "registered_at": "2026-02-08T10:30:00Z"
        }
        """
        model_name = event["model_name"]
        model_version = event["model_version"]

        logger.info(f"Processing MLflow model: {model_name} v{model_version}")

        # Convert dataset IDs to URNs
        training_dataset_urns = [
            f"urn:li:dataset:(urn:li:dataPlatform:s3,{ds},PROD)" for ds in event.get("training_datasets", [])
        ]

        self.datahub_client.register_ml_model(
            model_name=model_name,
            model_version=model_version,
            mlflow_run_id=event["mlflow_run_id"],
            training_datasets=training_dataset_urns,
            features=event.get("features", []),
            metrics=event.get("metrics", {}),
            tags=event.get("tags", []),
        )

        logger.info(f"✓ Registered model {model_name} v{model_version} in DataHub")

    def _handle_feast_materialization(self, event: dict[str, Any]) -> None:
        """Handle Feast feature materialization event.

        Event structure:
        {
            "feature_view": "customer_features",
            "features": [...],
            "source_dataset": "gold/features/customer",
            "materialization_interval": "1h",
            "materialized_at": "2026-02-08T10:30:00Z"
        }
        """
        feature_view = event["feature_view"]

        logger.info(f"Processing Feast materialization: {feature_view}")

        source_dataset_urn = f"urn:li:dataset:(urn:li:dataPlatform:s3,{event['source_dataset']},PROD)"

        self.datahub_client.register_feast_features(
            feature_view_name=feature_view,
            features=event.get("features", []),
            source_dataset_urn=source_dataset_urn,
            materialization_interval=event.get("materialization_interval", "1h"),
            tags=event.get("tags", []),
        )

        logger.info(f"✓ Registered Feast feature view {feature_view} in DataHub")

    def _handle_kubeflow_pipeline(self, event: dict[str, Any]) -> None:
        """Handle Kubeflow pipeline completion event.

        Event structure:
        {
            "pipeline_name": "train-customer-churn",
            "run_id": "xyz789",
            "input_datasets": ["gold/crm/customers"],
            "output_model": "customer-churn",
            "output_version": 3,
            "completed_at": "2026-02-08T10:30:00Z"
        }
        """
        pipeline_name = event["pipeline_name"]
        run_id = event["run_id"]

        logger.info(f"Processing Kubeflow pipeline: {pipeline_name} (run: {run_id})")

        # Track pipeline lineage: input datasets → output model
        input_dataset_urns = [
            f"urn:li:dataset:(urn:li:dataPlatform:s3,{ds},PROD)" for ds in event.get("input_datasets", [])
        ]

        output_model_urn = (
            f"urn:li:mlModel:(urn:li:dataPlatform:mlflow,{event['output_model']},{event['output_version']})"
        )

        self.datahub_client.add_lineage(
            downstream_urn=output_model_urn,
            upstream_urns=input_dataset_urns,
            lineage_type="ml_training",
            transformation_description=f"Kubeflow pipeline: {pipeline_name} (run: {run_id})",
        )

        logger.info("✓ Registered Kubeflow pipeline lineage in DataHub")


def main() -> None:
    """Run metadata ingestion service."""
    import os

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    kafka_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
    datahub_url = os.getenv("DATAHUB_GMS_URL", "http://datahub-gms:8080")

    service = MetadataIngestionService(
        kafka_bootstrap_servers=kafka_servers,
        datahub_gms_url=datahub_url,
    )

    service.start()


if __name__ == "__main__":
    main()
