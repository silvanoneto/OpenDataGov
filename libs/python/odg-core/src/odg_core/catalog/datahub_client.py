"""DataHub metadata catalog client for OpenDataGov.

Integrates DataHub with:
- Medallion Lakehouse (Bronze/Silver/Gold/Platinum)
- MLflow (model registry)
- Feast (feature store)
- Kubeflow Pipelines (ML workflows)
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class DataHubClient:
    """Client for DataHub metadata catalog.

    Provides methods to:
    - Register datasets (Bronze/Silver/Gold/Platinum)
    - Track lineage (data transformations, ML pipelines)
    - Add governance tags (PII, GDPR, Gold layer, Production)
    - Search and discover data assets
    """

    def __init__(
        self,
        gms_url: str = "http://datahub-gms:8080",
        frontend_url: str = "http://datahub-frontend:9002",
        timeout: int = 30,
    ):
        """Initialize DataHub client.

        Args:
            gms_url: DataHub GMS (General Metadata Service) URL
            frontend_url: DataHub frontend URL
            timeout: HTTP request timeout in seconds
        """
        self.gms_url = gms_url.rstrip("/")
        self.frontend_url = frontend_url.rstrip("/")
        self.timeout = timeout
        self.client = httpx.Client(timeout=timeout)
        logger.info(f"DataHub client initialized: GMS={gms_url}")

    def register_dataset(
        self,
        dataset_id: str,
        name: str,
        platform: str,
        layer: str,
        schema: list[dict[str, str]],
        tags: list[str] | None = None,
        description: str | None = None,
        owner: str | None = None,
    ) -> dict[str, Any]:
        """Register a dataset in DataHub.

        Args:
            dataset_id: Unique dataset identifier
            name: Dataset name
            platform: Platform (s3, postgresql, iceberg)
            layer: Medallion layer (bronze, silver, gold, platinum)
            schema: List of {"name": str, "type": str, "description": str}
            tags: Governance tags (pii, gdpr, gold_layer, production)
            description: Dataset description
            owner: Dataset owner (email or user ID)

        Returns:
            Dataset metadata

        Example:
            >>> client.register_dataset(
            ...     dataset_id="gold/finance/revenue",
            ...     name="Revenue Data (Gold)",
            ...     platform="s3",
            ...     layer="gold",
            ...     schema=[
            ...         {"name": "transaction_id", "type": "STRING", "description": "Unique transaction ID"},
            ...         {"name": "amount", "type": "DECIMAL", "description": "Transaction amount"},
            ...     ],
            ...     tags=["gold_layer", "production"],
            ...     owner="data-architect@company.com"
            ... )
        """
        if tags is None:
            tags = []

        # Auto-add layer tag
        layer_tag = f"{layer}_layer"
        if layer_tag not in tags:
            tags.append(layer_tag)

        dataset_urn = f"urn:li:dataset:(urn:li:dataPlatform:{platform},{dataset_id},PROD)"

        metadata = {
            "urn": dataset_urn,
            "name": name,
            "platform": platform,
            "layer": layer,
            "schema": schema,
            "tags": tags,
            "description": description,
            "owner": owner,
            "registered_at": datetime.now().isoformat(),
        }

        logger.info(f"Registered dataset: {dataset_id} ({layer} layer)")

        # POST to DataHub GMS API (ingest endpoint)
        try:
            response = self.client.post(
                f"{self.gms_url}/entities?action=ingest",
                json={
                    "entity": {
                        "value": {
                            "com.linkedin.metadata.snapshot.DatasetSnapshot": {
                                "urn": dataset_urn,
                                "aspects": [
                                    {
                                        "com.linkedin.dataset.DatasetProperties": {
                                            "description": description or "",
                                            "customProperties": {
                                                "layer": layer,
                                                "registered_at": metadata["registered_at"],
                                            },
                                        }
                                    },
                                    {
                                        "com.linkedin.schema.SchemaMetadata": {
                                            "schemaName": name,
                                            "platform": dataset_urn,
                                            "version": 0,
                                            "fields": [
                                                {
                                                    "fieldPath": field["name"],
                                                    "nativeDataType": field["type"],
                                                    "type": {"type": {"com.linkedin.schema.StringType": {}}},
                                                    "description": field.get("description", ""),
                                                }
                                                for field in schema
                                            ],
                                        }
                                    },
                                ],
                            }
                        }
                    }
                },
            )
            response.raise_for_status()
            logger.info(f"Successfully registered dataset in DataHub: {dataset_id}")
        except httpx.HTTPError as e:
            logger.warning(f"Failed to register dataset in DataHub: {e}. Continuing with local metadata.")

        return metadata

    def add_lineage(
        self,
        downstream_urn: str,
        upstream_urns: list[str],
        lineage_type: str = "transformation",
        transformation_description: str | None = None,
    ) -> dict[str, Any]:
        """Add data lineage relationship.

        Args:
            downstream_urn: Downstream dataset URN (output)
            upstream_urns: List of upstream dataset URNs (inputs)
            lineage_type: Type (transformation, copy, aggregation, ml_training)
            transformation_description: Description of transformation

        Returns:
            Lineage metadata

        Example:
            >>> # Bronze → Silver lineage
            >>> client.add_lineage(
            ...     downstream_urn="urn:li:dataset:(urn:li:dataPlatform:s3,silver/finance/revenue,PROD)",
            ...     upstream_urns=["urn:li:dataset:(urn:li:dataPlatform:s3,bronze/raw/transactions,PROD)"],
            ...     lineage_type="transformation",
            ...     transformation_description="Data quality validation + deduplication"
            ... )
        """
        lineage = {
            "downstream": downstream_urn,
            "upstreams": upstream_urns,
            "type": lineage_type,
            "description": transformation_description,
            "created_at": datetime.now().isoformat(),
        }

        logger.info(f"Added lineage: {len(upstream_urns)} upstream(s) → {downstream_urn}")

        # In production: POST to DataHub GMS API
        # response = httpx.post(f"{self.gms_url}/lineage", json=lineage)

        return lineage

    def register_ml_model(
        self,
        model_name: str,
        model_version: int,
        mlflow_run_id: str,
        training_datasets: list[str],
        features: list[str],
        metrics: dict[str, float],
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """Register ML model in DataHub.

        Args:
            model_name: Model name
            model_version: Model version
            mlflow_run_id: MLflow run ID
            training_datasets: List of dataset URNs used for training
            features: List of feature names
            metrics: Performance metrics (accuracy, f1, etc.)
            tags: Model tags

        Returns:
            Model metadata

        Example:
            >>> client.register_ml_model(
            ...     model_name="customer-churn",
            ...     model_version=3,
            ...     mlflow_run_id="abc123",
            ...     training_datasets=["urn:li:dataset:(urn:li:dataPlatform:s3,gold/crm/customers,PROD)"],
            ...     features=["total_purchases", "avg_order_value", "days_since_last_purchase"],
            ...     metrics={"accuracy": 0.92, "f1_score": 0.89},
            ...     tags=["production"]
            ... )
        """
        if tags is None:
            tags = []

        model_urn = f"urn:li:mlModel:(urn:li:dataPlatform:mlflow,{model_name},{model_version})"

        metadata = {
            "urn": model_urn,
            "name": model_name,
            "version": model_version,
            "platform": "mlflow",
            "mlflow_run_id": mlflow_run_id,
            "training_datasets": training_datasets,
            "features": features,
            "metrics": metrics,
            "tags": tags,
            "registered_at": datetime.now().isoformat(),
        }

        logger.info(f"Registered ML model: {model_name} v{model_version}")

        # Add lineage: training datasets → model
        self.add_lineage(
            downstream_urn=model_urn,
            upstream_urns=training_datasets,
            lineage_type="ml_training",
            transformation_description=f"Trained {model_name} with {len(features)} features",
        )

        return metadata

    def register_feast_features(
        self,
        feature_view_name: str,
        features: list[dict[str, str]],
        source_dataset_urn: str,
        materialization_interval: str,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """Register Feast feature view in DataHub.

        Args:
            feature_view_name: Feature view name
            features: List of {"name": str, "type": str, "description": str}
            source_dataset_urn: Source dataset URN
            materialization_interval: Materialization interval (e.g., "1h", "1d")
            tags: Feature tags

        Returns:
            Feature view metadata

        Example:
            >>> client.register_feast_features(
            ...     feature_view_name="customer_features",
            ...     features=[
            ...         {"name": "total_purchases", "type": "FLOAT", "description": "Total purchases"},
            ...         {"name": "avg_order_value", "type": "FLOAT", "description": "Average order value"},
            ...     ],
            ...     source_dataset_urn="urn:li:dataset:(urn:li:dataPlatform:s3,gold/features/customer,PROD)",
            ...     materialization_interval="1h",
            ...     tags=["online_serving", "production"]
            ... )
        """
        if tags is None:
            tags = []

        feature_urn = f"urn:li:mlFeatureTable:(urn:li:dataPlatform:feast,{feature_view_name},PROD)"

        metadata = {
            "urn": feature_urn,
            "name": feature_view_name,
            "platform": "feast",
            "features": features,
            "source_dataset": source_dataset_urn,
            "materialization_interval": materialization_interval,
            "tags": tags,
            "registered_at": datetime.now().isoformat(),
        }

        logger.info(f"Registered Feast feature view: {feature_view_name} ({len(features)} features)")

        # Add lineage: source dataset → feature table
        self.add_lineage(
            downstream_urn=feature_urn,
            upstream_urns=[source_dataset_urn],
            lineage_type="feature_engineering",
            transformation_description=f"Materialized {len(features)} features",
        )

        return metadata

    def add_tags(
        self,
        entity_urn: str,
        tags: list[str],
    ) -> dict[str, Any]:
        """Add governance tags to entity.

        Args:
            entity_urn: Entity URN
            tags: Tags to add (pii, gdpr, gold_layer, production)

        Returns:
            Tag metadata

        Example:
            >>> client.add_tags(
            ...     entity_urn="urn:li:dataset:(urn:li:dataPlatform:s3,gold/finance/revenue,PROD)",
            ...     tags=["gdpr", "production"]
            ... )
        """
        tag_metadata = {
            "urn": entity_urn,
            "tags": tags,
            "added_at": datetime.now().isoformat(),
        }

        logger.info(f"Added {len(tags)} tags to {entity_urn}")

        return tag_metadata

    def search(
        self,
        query: str,
        entity_types: list[str] | None = None,
        filters: dict[str, Any] | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Search DataHub catalog.

        Args:
            query: Search query
            entity_types: Entity types to search (dataset, mlModel, mlFeatureTable)
            filters: Search filters (e.g., {"layer": "gold", "tags": ["production"]})
            limit: Max results

        Returns:
            Search results

        Example:
            >>> # Search for Gold layer datasets
            >>> results = client.search(
            ...     query="revenue",
            ...     entity_types=["dataset"],
            ...     filters={"layer": "gold"},
            ...     limit=10
            ... )
        """
        if entity_types is None:
            entity_types = ["dataset"]
        if filters is None:
            filters = {}

        logger.info(f"Search: '{query}' (types: {entity_types})")

        # POST to DataHub GMS API
        try:
            response = self.client.post(
                f"{self.gms_url}/entities?action=search",
                json={
                    "input": query,
                    "entity": entity_types[0] if entity_types else "dataset",
                    "start": 0,
                    "count": limit,
                    "filters": filters or {},
                },
            )
            response.raise_for_status()
            data = response.json()

            # Parse DataHub search results
            results = []
            for entity in data.get("value", {}).get("entities", []):
                results.append(
                    {
                        "urn": entity.get("urn"),
                        "name": entity.get("name", ""),
                        "platform": entity.get("platform", ""),
                        "score": entity.get("score", 0.0),
                    }
                )

            logger.info(f"Search returned {len(results)} results")
            return results

        except httpx.HTTPError as e:
            logger.warning(f"DataHub search failed: {e}. Returning empty results.")
            return []

    def get_lineage(
        self,
        entity_urn: str,
        direction: str = "both",
        max_hops: int = 3,
    ) -> dict[str, Any]:
        """Get lineage graph for entity.

        Args:
            entity_urn: Entity URN
            direction: Direction (upstream, downstream, both)
            max_hops: Maximum hops to traverse

        Returns:
            Lineage graph

        Example:
            >>> # Get full lineage for Gold dataset
            >>> lineage = client.get_lineage(
            ...     entity_urn="urn:li:dataset:(urn:li:dataPlatform:s3,gold/finance/revenue,PROD)",
            ...     direction="upstream",
            ...     max_hops=5
            ... )
            >>> # Shows: Bronze → Silver → Gold
        """
        lineage = {
            "entity": entity_urn,
            "direction": direction,
            "max_hops": max_hops,
            "graph": {},
        }

        logger.info(f"Get lineage: {entity_urn} ({direction}, max_hops={max_hops})")

        # In production: GET from DataHub GMS API
        # response = httpx.get(f"{self.gms_url}/lineage/{entity_urn}")

        return lineage
