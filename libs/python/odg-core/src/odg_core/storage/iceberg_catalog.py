"""Apache Iceberg catalog integration for dataset versioning.

Provides time-travel capabilities, snapshot management, and schema evolution
for lakehouse datasets.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import pandas as pd


class IcebergCatalog:
    """Manages Apache Iceberg tables with automatic versioning via snapshots."""

    def __init__(self, warehouse_path: str = "s3://odg-lakehouse/"):
        """Initialize Iceberg catalog.

        Args:
            warehouse_path: S3 path to the Iceberg warehouse
        """
        self.warehouse_path = warehouse_path
        self._catalog: Any = None

    def _get_catalog(self) -> Any:
        """Lazy load Iceberg catalog to avoid import errors if pyiceberg not installed."""
        if self._catalog is None:
            try:
                from pyiceberg.catalog import load_catalog

                self._catalog = load_catalog(
                    "odg",
                    **{
                        "type": "rest",
                        "uri": "http://iceberg-rest:8181",
                        "s3.endpoint": "http://minio:9000",
                        "warehouse": self.warehouse_path,
                    },
                )
            except ImportError as e:
                raise ImportError("pyiceberg not installed. Install with: pip install pyiceberg") from e
        return self._catalog

    @property
    def catalog(self) -> Any:
        """Get the underlying Iceberg catalog."""
        return self._get_catalog()

    def create_table(self, namespace: str, table_name: str, schema: Any) -> Any:
        """Create an Iceberg table with versioning enabled.

        Args:
            namespace: Table namespace (e.g., "bronze", "silver", "gold")
            table_name: Table name
            schema: Iceberg Schema object

        Returns:
            Created Iceberg table
        """
        return self.catalog.create_table(
            f"{namespace}.{table_name}",
            schema=schema,
            properties={"write.format.default": "parquet", "commit.manifest.min-count-to-merge": "3"},
        )

    def get_snapshot_id(self, namespace: str, table_name: str) -> str:
        """Get current snapshot ID (dataset version).

        Args:
            namespace: Table namespace
            table_name: Table name

        Returns:
            Current snapshot ID as string

        Example:
            >>> catalog = IcebergCatalog()
            >>> snapshot_id = catalog.get_snapshot_id("gold", "customers")
            >>> print(f"Current version: {snapshot_id}")
        """
        table = self.catalog.load_table(f"{namespace}.{table_name}")
        current_snapshot = table.current_snapshot()
        if current_snapshot is None:
            raise ValueError(f"Table {namespace}.{table_name} has no snapshots yet")
        return str(current_snapshot.snapshot_id)

    def time_travel(self, namespace: str, table_name: str, snapshot_id: str) -> pd.DataFrame:
        """Read table data from a specific snapshot (time-travel query).

        Args:
            namespace: Table namespace
            table_name: Table name
            snapshot_id: Snapshot ID to read from

        Returns:
            DataFrame with data from the specified snapshot

        Example:
            >>> catalog = IcebergCatalog()
            >>> # Read historical data from 1 week ago
            >>> old_data = catalog.time_travel("gold", "customers", "1234567890")
        """
        table = self.catalog.load_table(f"{namespace}.{table_name}")
        return table.scan(snapshot_id=int(snapshot_id)).to_pandas()  # type: ignore[no-any-return]

    def list_snapshots(self, namespace: str, table_name: str) -> list[dict[str, Any]]:
        """List all snapshots (versions) for a table.

        Args:
            namespace: Table namespace
            table_name: Table name

        Returns:
            List of snapshot metadata dictionaries

        Example:
            >>> catalog = IcebergCatalog()
            >>> snapshots = catalog.list_snapshots("gold", "customers")
            >>> for snap in snapshots:
            ...     print(f"Version {snap['snapshot_id']} at {snap['timestamp']}")
        """
        table = self.catalog.load_table(f"{namespace}.{table_name}")
        return [
            {
                "snapshot_id": str(snap.snapshot_id),
                "timestamp_ms": snap.timestamp_ms,
                "timestamp": datetime.fromtimestamp(snap.timestamp_ms / 1000).isoformat(),
                "operation": snap.summary.get("operation", "unknown"),
                "summary": snap.summary,
            }
            for snap in table.history()
        ]

    def rollback_to_snapshot(self, namespace: str, table_name: str, snapshot_id: str) -> None:
        """Rollback table to a previous snapshot.

        Args:
            namespace: Table namespace
            table_name: Table name
            snapshot_id: Snapshot ID to rollback to

        Example:
            >>> catalog = IcebergCatalog()
            >>> # Rollback to previous version if current data is corrupted
            >>> catalog.rollback_to_snapshot("gold", "customers", "1234567890")
        """
        table = self.catalog.load_table(f"{namespace}.{table_name}")
        table.manageSnapshots().rollback_to_snapshot(int(snapshot_id)).commit()

    def tag_snapshot(self, namespace: str, table_name: str, snapshot_id: str, tag: str) -> None:
        """Tag a snapshot with a semantic label (e.g., 'production_2026_02_15').

        Args:
            namespace: Table namespace
            table_name: Table name
            snapshot_id: Snapshot ID to tag
            tag: Tag name (e.g., 'production', 'pre_migration')

        Example:
            >>> catalog = IcebergCatalog()
            >>> current_snap = catalog.get_snapshot_id("gold", "customers")
            >>> catalog.tag_snapshot("gold", "customers", current_snap, "production_2026_02_15")
        """
        table = self.catalog.load_table(f"{namespace}.{table_name}")
        table.manageSnapshots().createTag(tag, int(snapshot_id)).commit()

    def get_snapshot_by_tag(self, namespace: str, table_name: str, tag: str) -> str:
        """Get snapshot ID by tag name.

        Args:
            namespace: Table namespace
            table_name: Table name
            tag: Tag name

        Returns:
            Snapshot ID associated with the tag

        Example:
            >>> catalog = IcebergCatalog()
            >>> prod_snapshot = catalog.get_snapshot_by_tag("gold", "customers", "production")
        """
        table = self.catalog.load_table(f"{namespace}.{table_name}")
        snapshot_ref = table.snapshot_by_name(tag)
        if snapshot_ref is None:
            raise ValueError(f"Tag '{tag}' not found for table {namespace}.{table_name}")
        return str(snapshot_ref.snapshot_id)

    def time_travel_by_tag(self, namespace: str, table_name: str, tag: str) -> pd.DataFrame:
        """Read table data from a tagged snapshot.

        Args:
            namespace: Table namespace
            table_name: Table name
            tag: Tag name (e.g., 'production', 'pre_migration')

        Returns:
            DataFrame with data from the tagged snapshot

        Example:
            >>> catalog = IcebergCatalog()
            >>> prod_data = catalog.time_travel_by_tag("gold", "customers", "production_2026_02_15")
        """
        snapshot_id = self.get_snapshot_by_tag(namespace, table_name, tag)
        return self.time_travel(namespace, table_name, snapshot_id)

    def expire_old_snapshots(
        self, namespace: str, table_name: str, older_than_days: int = 90, keep_last_n: int = 30
    ) -> int:
        """Expire old snapshots to save storage.

        Args:
            namespace: Table namespace
            table_name: Table name
            older_than_days: Expire snapshots older than this many days
            keep_last_n: Always keep at least this many recent snapshots

        Returns:
            Number of expired snapshots

        Example:
            >>> catalog = IcebergCatalog()
            >>> # Keep last 30 snapshots, expire older than 90 days
            >>> expired_count = catalog.expire_old_snapshots("gold", "customers", 90, 30)
        """
        from datetime import timedelta

        table = self.catalog.load_table(f"{namespace}.{table_name}")
        cutoff_timestamp_ms = int((datetime.now() - timedelta(days=older_than_days)).timestamp() * 1000)

        # Get all snapshots
        all_snapshots = list(table.history())

        # Keep recent snapshots
        recent_snapshots = sorted(all_snapshots, key=lambda s: s.timestamp_ms, reverse=True)[:keep_last_n]
        keep_snapshot_ids = {s.snapshot_id for s in recent_snapshots}

        # Count snapshots to expire
        expired_count = 0
        for snapshot in all_snapshots:
            if snapshot.snapshot_id not in keep_snapshot_ids and snapshot.timestamp_ms < cutoff_timestamp_ms:
                expired_count += 1

        # Expire snapshots
        if expired_count > 0:
            table.manageSnapshots().expireOlderThan(cutoff_timestamp_ms).commit()

        return expired_count
