"""GraphQL types for datasets and lineage."""

import uuid
from typing import Any, cast

import strawberry


@strawberry.type
class DatasetGQL:
    """A dataset in the lakehouse."""

    id: uuid.UUID
    name: str
    description: str
    layer: str
    classification: str | None = None
    quality_score: float | None = None
    created_at: str
    updated_at: str


@strawberry.type
class SimpleLineageEdgeGQL:
    """A lineage relationship between datasets."""

    from_dataset: str
    to_dataset: str
    label: str | None = None


@strawberry.type
class LineageGraphGQL:
    """Full lineage graph for a dataset."""

    nodes: list[DatasetGQL]
    edges: list[SimpleLineageEdgeGQL]


@strawberry.type
class DatasetVersionGQL:
    """A snapshot/version of a dataset."""

    snapshot_id: str
    timestamp: str
    timestamp_ms: int
    operation: str  # INSERT, DELETE, OVERWRITE, APPEND
    row_count: int | None = None
    size_bytes: int | None = None
    summary: strawberry.scalars.JSON | None = None


@strawberry.type
class VersionedDatasetGQL:
    """A dataset with versioning capabilities."""

    # Base dataset info
    id: uuid.UUID
    name: str
    namespace: str
    description: str
    layer: str
    classification: str | None = None
    quality_score: float | None = None
    created_at: str
    updated_at: str

    # Versioning info
    current_version: str  # Current snapshot ID
    total_versions: int

    @strawberry.field
    def versions(self) -> list[DatasetVersionGQL]:
        """Get all versions (snapshots) of this dataset.

        Returns:
            List of dataset versions ordered by timestamp descending
        """
        from odg_core.storage.iceberg_catalog import IcebergCatalog

        try:
            iceberg = IcebergCatalog()
            snapshots = iceberg.list_snapshots(self.namespace, self.name)

            return [
                DatasetVersionGQL(
                    snapshot_id=snap["snapshot_id"],
                    timestamp=snap["timestamp"],
                    timestamp_ms=snap["timestamp_ms"],
                    operation=snap["operation"],
                    summary=snap.get("summary"),
                )
                for snap in snapshots
            ]
        except Exception:
            return []

    @strawberry.field
    def get_version_data(self, snapshot_id: str, limit: int = 10) -> strawberry.scalars.JSON:
        """Get data from a specific version (time-travel query).

        Args:
            snapshot_id: Snapshot ID to query
            limit: Maximum number of rows to return (default: 10)

        Returns:
            JSON object with row_count, schema, and sample data
        """
        from odg_core.storage.iceberg_catalog import IcebergCatalog

        try:
            iceberg = IcebergCatalog()
            data = iceberg.time_travel(self.namespace, self.name, snapshot_id)

            result: dict[str, Any] = {
                "snapshot_id": snapshot_id,
                "row_count": len(data),
                "schema": list(data.columns),
                "sample": data.head(limit).to_dict(orient="records"),
            }
            return cast(strawberry.scalars.JSON, result)
        except Exception as e:
            error_result: dict[str, str] = {"error": str(e), "snapshot_id": snapshot_id}
            return cast(strawberry.scalars.JSON, error_result)
