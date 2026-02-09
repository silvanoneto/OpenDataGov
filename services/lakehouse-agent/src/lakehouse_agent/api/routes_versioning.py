"""API routes for dataset versioning with Apache Iceberg.

Provides endpoints for:
- Listing dataset versions (snapshots)
- Time-travel queries to specific versions
- Tagging versions
- Rolling back to previous versions
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/v1/datasets", tags=["versioning"])


class SnapshotInfo(BaseModel):
    """Snapshot metadata."""

    snapshot_id: str
    timestamp: str
    timestamp_ms: int
    operation: str
    summary: dict[str, Any] = Field(default_factory=dict)


class SnapshotListResponse(BaseModel):
    """Response for listing snapshots."""

    dataset: str
    namespace: str
    table_name: str
    versions: list[SnapshotInfo]
    total_count: int


class SnapshotDataResponse(BaseModel):
    """Response for time-travel query."""

    snapshot_id: str
    row_count: int
    schema_fields: list[str]
    sample: list[dict[str, Any]]


class SnapshotCreateResponse(BaseModel):
    """Response for snapshot creation."""

    snapshot_id: str
    description: str | None
    timestamp: str


class RollbackResponse(BaseModel):
    """Response for rollback operation."""

    success: bool
    rolled_back_to: str
    timestamp: str


@router.get("/{namespace}/{table_name}/versions", response_model=SnapshotListResponse)
async def list_dataset_versions(namespace: str, table_name: str) -> SnapshotListResponse:
    """List all versions (snapshots) of a dataset.

    Args:
        namespace: Dataset namespace (e.g., "bronze", "silver", "gold")
        table_name: Dataset table name

    Returns:
        List of snapshot metadata

    Example:
        GET /api/v1/datasets/gold/customers/versions
    """
    try:
        from odg_core.storage.iceberg_catalog import IcebergCatalog

        iceberg = IcebergCatalog()
        snapshots = iceberg.list_snapshots(namespace, table_name)

        return SnapshotListResponse(
            dataset=f"{namespace}.{table_name}",
            namespace=namespace,
            table_name=table_name,
            versions=[SnapshotInfo(**snap) for snap in snapshots],
            total_count=len(snapshots),
        )

    except ValueError as e:
        raise HTTPException(status_code=404, detail=f"Table not found: {e}") from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list snapshots: {e}") from e


@router.get("/{namespace}/{table_name}/versions/{snapshot_id}", response_model=SnapshotDataResponse)
async def get_dataset_version(
    namespace: str, table_name: str, snapshot_id: str, limit: int = 10
) -> SnapshotDataResponse:
    """Get data from a specific snapshot (time-travel query).

    Args:
        namespace: Dataset namespace
        table_name: Dataset table name
        snapshot_id: Snapshot ID to query
        limit: Maximum number of sample rows to return (default: 10)

    Returns:
        Snapshot data with sample rows

    Example:
        GET /api/v1/datasets/gold/customers/versions/1234567890?limit=5
    """
    try:
        from odg_core.storage.iceberg_catalog import IcebergCatalog

        iceberg = IcebergCatalog()
        data = iceberg.time_travel(namespace, table_name, snapshot_id)

        return SnapshotDataResponse(
            snapshot_id=snapshot_id,
            row_count=len(data),
            schema_fields=list(data.columns),
            sample=[{str(k): v for k, v in row.items()} for row in data.head(limit).to_dict(orient="records")],
        )

    except ValueError as e:
        raise HTTPException(status_code=404, detail=f"Snapshot not found: {e}") from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to query snapshot: {e}") from e


@router.post("/{namespace}/{table_name}/snapshots", response_model=SnapshotCreateResponse)
async def create_snapshot(namespace: str, table_name: str, description: str | None = None) -> SnapshotCreateResponse:
    """Create a manual snapshot of a dataset.

    Note: Iceberg automatically creates snapshots on writes. This endpoint
    retrieves the current snapshot ID and optionally tags it.

    Args:
        namespace: Dataset namespace
        table_name: Dataset table name
        description: Optional description for the snapshot

    Returns:
        Created snapshot metadata

    Example:
        POST /api/v1/datasets/gold/customers/snapshots
        {"description": "Before migration to new schema"}
    """
    try:
        from odg_core.storage.iceberg_catalog import IcebergCatalog

        iceberg = IcebergCatalog()
        snapshot_id = iceberg.get_snapshot_id(namespace, table_name)

        # If description provided, tag the snapshot
        if description:
            tag = f"manual_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            iceberg.tag_snapshot(namespace, table_name, snapshot_id, tag)

        return SnapshotCreateResponse(
            snapshot_id=snapshot_id, description=description, timestamp=datetime.now().isoformat()
        )

    except ValueError as e:
        raise HTTPException(status_code=404, detail=f"Table not found: {e}") from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create snapshot: {e}") from e


@router.post("/{namespace}/{table_name}/snapshots/{snapshot_id}/tag")
async def tag_snapshot(namespace: str, table_name: str, snapshot_id: str, tag: str) -> dict[str, Any]:
    """Tag a snapshot with a semantic label.

    Args:
        namespace: Dataset namespace
        table_name: Dataset table name
        snapshot_id: Snapshot ID to tag
        tag: Tag name (e.g., "production", "pre_migration")

    Returns:
        Success confirmation

    Example:
        POST /api/v1/datasets/gold/customers/snapshots/1234567890/tag
        {"tag": "production_2026_02_15"}
    """
    try:
        from odg_core.storage.iceberg_catalog import IcebergCatalog

        iceberg = IcebergCatalog()
        iceberg.tag_snapshot(namespace, table_name, snapshot_id, tag)

        return {"success": True, "snapshot_id": snapshot_id, "tag": tag, "timestamp": datetime.now().isoformat()}

    except ValueError as e:
        raise HTTPException(status_code=404, detail=f"Snapshot not found: {e}") from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to tag snapshot: {e}") from e


@router.post("/{namespace}/{table_name}/rollback", response_model=RollbackResponse)
async def rollback_to_snapshot(namespace: str, table_name: str, snapshot_id: str) -> RollbackResponse:
    """Rollback dataset to a previous snapshot.

    WARNING: This operation modifies the dataset's current state.
    Use with caution in production environments.

    Args:
        namespace: Dataset namespace
        table_name: Dataset table name
        snapshot_id: Snapshot ID to rollback to

    Returns:
        Rollback confirmation

    Example:
        POST /api/v1/datasets/gold/customers/rollback
        {"snapshot_id": "1234567890"}
    """
    try:
        from odg_core.storage.iceberg_catalog import IcebergCatalog

        iceberg = IcebergCatalog()
        iceberg.rollback_to_snapshot(namespace, table_name, snapshot_id)

        return RollbackResponse(success=True, rolled_back_to=snapshot_id, timestamp=datetime.now().isoformat())

    except ValueError as e:
        raise HTTPException(status_code=404, detail=f"Snapshot not found: {e}") from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to rollback: {e}") from e


@router.get("/{namespace}/{table_name}/tags/{tag}", response_model=SnapshotDataResponse)
async def get_version_by_tag(namespace: str, table_name: str, tag: str, limit: int = 10) -> SnapshotDataResponse:
    """Get dataset version by tag name (time-travel by tag).

    Args:
        namespace: Dataset namespace
        table_name: Dataset table name
        tag: Tag name (e.g., "production", "pre_migration")
        limit: Maximum number of sample rows to return (default: 10)

    Returns:
        Snapshot data with sample rows

    Example:
        GET /api/v1/datasets/gold/customers/tags/production_2026_02_15
    """
    try:
        from odg_core.storage.iceberg_catalog import IcebergCatalog

        iceberg = IcebergCatalog()
        data = iceberg.time_travel_by_tag(namespace, table_name, tag)
        snapshot_id = iceberg.get_snapshot_by_tag(namespace, table_name, tag)

        return SnapshotDataResponse(
            snapshot_id=snapshot_id,
            row_count=len(data),
            schema_fields=list(data.columns),
            sample=[{str(k): v for k, v in row.items()} for row in data.head(limit).to_dict(orient="records")],
        )

    except ValueError as e:
        raise HTTPException(status_code=404, detail=f"Tag not found: {e}") from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to query tagged version: {e}") from e
