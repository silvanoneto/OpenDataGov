"""Feast materialization job tracking with lineage and versioning.

Tracks which Spark/Flink jobs generated which feature versions, enabling
reproducibility and debugging of feature engineering pipelines.
"""

from __future__ import annotations

import hashlib
import os
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from feast import FeatureStore, FeatureView


class MaterializationTracker:
    """Tracks Feast feature materialization jobs with lineage.

    Example:
        >>> from feast import FeatureStore
        >>> from odg_core.feast import MaterializationTracker
        >>>
        >>> store = FeatureStore(repo_path=".")
        >>> tracker = MaterializationTracker(store)
        >>>
        >>> # Track materialization
        >>> tracker.track_materialization(
        ...     feature_view_name="customer_features",
        ...     source_pipeline_id="spark_aggregate_customers",
        ...     source_pipeline_version=5,
        ...     start_date=datetime(2026, 1, 1),
        ...     end_date=datetime(2026, 2, 1)
        ... )
    """

    def __init__(self, feature_store: FeatureStore):
        """Initialize materialization tracker.

        Args:
            feature_store: Feast FeatureStore instance
        """
        self.store = feature_store

    def track_materialization(
        self,
        feature_view_name: str,
        source_pipeline_id: str | None = None,
        source_pipeline_version: int | None = None,
        source_dataset_id: str | None = None,
        source_dataset_version: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> dict[str, Any]:
        """Track a feature materialization job.

        Args:
            feature_view_name: Name of the Feast FeatureView
            source_pipeline_id: Pipeline that generated source data (e.g., "spark_aggregate_customers")
            source_pipeline_version: Version of the pipeline
            source_dataset_id: Source dataset ID (e.g., "gold/customers")
            source_dataset_version: Iceberg snapshot ID of source dataset
            start_date: Materialization start date
            end_date: Materialization end date

        Returns:
            Materialization metadata dictionary
        """
        from odg_core.lineage.emitter import emit_lineage_event
        from odg_core.storage.iceberg_catalog import IcebergCatalog

        run_id = str(uuid.uuid4())
        materialization_time = datetime.now(UTC)

        # Get FeatureView metadata
        feature_view = self.store.get_feature_view(feature_view_name)
        feature_names = [f.name for f in feature_view.features]

        # Capture source dataset snapshot if not provided
        if source_dataset_id and not source_dataset_version:
            try:
                iceberg = IcebergCatalog()
                namespace, table_name = source_dataset_id.split("/")
                source_dataset_version = iceberg.get_snapshot_id(namespace, table_name)
            except Exception as e:
                print(f"Warning: Could not get snapshot for {source_dataset_id}: {e}")

        # Build materialization metadata
        materialization_metadata = {
            "run_id": run_id,
            "feature_view": feature_view_name,
            "feature_names": feature_names,
            "source_pipeline_id": source_pipeline_id,
            "source_pipeline_version": source_pipeline_version,
            "source_dataset_id": source_dataset_id,
            "source_dataset_version": source_dataset_version,
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None,
            "materialization_time": materialization_time.isoformat(),
            "feature_view_hash": self._compute_feature_view_hash(feature_view),
        }

        # Persist to database
        self._persist_materialization(materialization_metadata)

        # Emit OpenLineage event
        inputs = []
        if source_dataset_id:
            inputs.append(
                {
                    "namespace": source_dataset_id.split("/")[0] if "/" in source_dataset_id else "unknown",
                    "name": source_dataset_id,
                    "facets": {
                        "snapshot": source_dataset_version,
                        "pipeline_id": source_pipeline_id,
                        "pipeline_version": source_pipeline_version,
                    },
                }
            )

        emit_lineage_event(
            job_name=f"feast_materialize_{feature_view_name}",
            job_namespace="feast",
            inputs=inputs,
            outputs=[
                {
                    "namespace": "feast",
                    "name": feature_view_name,
                    "facets": {
                        "features": feature_names,
                        "start_date": start_date.isoformat() if start_date else None,
                        "end_date": end_date.isoformat() if end_date else None,
                    },
                }
            ],
            event_type="COMPLETE",
            run_id=run_id,
        )

        return materialization_metadata

    def _compute_feature_view_hash(self, feature_view: FeatureView) -> str:
        """Compute hash of FeatureView definition.

        Args:
            feature_view: Feast FeatureView

        Returns:
            12-character hash of the feature view definition
        """
        # Serialize feature view structure
        fv_structure = {
            "name": feature_view.name,
            "entities": sorted(feature_view.entities),
            "features": sorted([f.name for f in feature_view.features]),
            "ttl": str(feature_view.ttl) if feature_view.ttl else None,
            "source": str(feature_view.batch_source) if hasattr(feature_view, "batch_source") else None,
        }

        import json

        fv_json = json.dumps(fv_structure, sort_keys=True)
        full_hash = hashlib.sha256(fv_json.encode()).hexdigest()
        return full_hash[:12]

    def _persist_materialization(self, metadata: dict[str, Any]) -> None:
        """Persist materialization metadata to database.

        Args:
            metadata: Materialization metadata dictionary
        """
        try:
            from sqlalchemy import create_engine
            from sqlalchemy.orm import Session

            from odg_core.db.tables import FeastMaterializationRow

            db_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/odg")
            engine = create_engine(db_url)

            with Session(engine) as session:
                materialization = FeastMaterializationRow(
                    run_id=metadata["run_id"],
                    feature_view=metadata["feature_view"],
                    feature_names=metadata["feature_names"],
                    source_pipeline_id=metadata.get("source_pipeline_id"),
                    source_pipeline_version=metadata.get("source_pipeline_version"),
                    source_dataset_id=metadata.get("source_dataset_id"),
                    source_dataset_version=metadata.get("source_dataset_version"),
                    start_date=datetime.fromisoformat(metadata["start_date"]) if metadata.get("start_date") else None,
                    end_date=datetime.fromisoformat(metadata["end_date"]) if metadata.get("end_date") else None,
                    materialization_time=datetime.fromisoformat(metadata["materialization_time"]),
                    feature_view_hash=metadata["feature_view_hash"],
                )

                session.add(materialization)
                session.commit()

        except Exception as e:
            print(f"Warning: Failed to persist Feast materialization: {e}")

    def get_materialization_history(self, feature_view_name: str, limit: int = 10) -> list[dict[str, Any]]:
        """Get materialization history for a feature view.

        Args:
            feature_view_name: Name of the FeatureView
            limit: Maximum number of records to return

        Returns:
            List of materialization records
        """
        try:
            from sqlalchemy import create_engine, select
            from sqlalchemy.orm import Session

            from odg_core.db.tables import FeastMaterializationRow

            db_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/odg")
            engine = create_engine(db_url)

            with Session(engine) as session:
                stmt = (
                    select(FeastMaterializationRow)
                    .where(FeastMaterializationRow.feature_view == feature_view_name)
                    .order_by(FeastMaterializationRow.materialization_time.desc())
                    .limit(limit)
                )

                results = session.execute(stmt).scalars().all()

                return [
                    {
                        "run_id": r.run_id,
                        "feature_view": r.feature_view,
                        "feature_names": r.feature_names,
                        "source_pipeline_id": r.source_pipeline_id,
                        "source_pipeline_version": r.source_pipeline_version,
                        "source_dataset_id": r.source_dataset_id,
                        "source_dataset_version": r.source_dataset_version,
                        "start_date": r.start_date.isoformat() if r.start_date else None,
                        "end_date": r.end_date.isoformat() if r.end_date else None,
                        "materialization_time": r.materialization_time.isoformat(),
                    }
                    for r in results
                ]

        except Exception as e:
            print(f"Warning: Failed to get materialization history: {e}")
            return []

    def validate_feature_freshness(self, feature_view_name: str, max_age_hours: int = 24) -> dict[str, Any]:
        """Validate that features are fresh enough for model training.

        Args:
            feature_view_name: Name of the FeatureView
            max_age_hours: Maximum age in hours for features to be considered fresh

        Returns:
            Validation result dictionary with freshness status
        """
        history = self.get_materialization_history(feature_view_name, limit=1)

        if not history:
            return {
                "is_fresh": False,
                "reason": "No materialization history found",
                "feature_view": feature_view_name,
            }

        last_materialization = history[0]
        materialization_time = datetime.fromisoformat(last_materialization["materialization_time"])
        age_hours = (datetime.now(UTC) - materialization_time).total_seconds() / 3600

        is_fresh = age_hours <= max_age_hours

        return {
            "is_fresh": is_fresh,
            "age_hours": age_hours,
            "max_age_hours": max_age_hours,
            "last_materialization_time": last_materialization["materialization_time"],
            "source_pipeline_id": last_materialization.get("source_pipeline_id"),
            "source_pipeline_version": last_materialization.get("source_pipeline_version"),
            "feature_view": feature_view_name,
        }


def track_feast_materialization(feature_store: FeatureStore, feature_view_name: str, **kwargs: Any) -> dict[str, Any]:
    """Convenience function to track Feast materialization.

    Args:
        feature_store: Feast FeatureStore instance
        feature_view_name: Name of the FeatureView
        **kwargs: Additional tracking parameters (source_pipeline_id, etc.)

    Returns:
        Materialization metadata

    Example:
        >>> from feast import FeatureStore
        >>> from odg_core.feast import track_feast_materialization
        >>>
        >>> store = FeatureStore(repo_path=".")
        >>> store.materialize(
        ...     start_date=datetime(2026, 1, 1),
        ...     end_date=datetime(2026, 2, 1)
        ... )
        >>>
        >>> # Track what was materialized
        >>> track_feast_materialization(
        ...     feature_store=store,
        ...     feature_view_name="customer_features",
        ...     source_pipeline_id="spark_aggregate_customers",
        ...     source_pipeline_version=5
        ... )
    """
    tracker = MaterializationTracker(feature_store)
    return tracker.track_materialization(feature_view_name, **kwargs)
