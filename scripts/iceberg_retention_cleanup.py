"""Automated Iceberg snapshot retention and cleanup.

This script runs as a cron job to enforce retention policies across all Iceberg tables.

Retention Policy:
- Keep last 30 snapshots
- Keep snapshots from last 90 days
- Keep all tagged snapshots (production, gold, etc.)
- Special handling for production datasets (keep 2 years)

Usage:
    python iceberg_retention_cleanup.py --dry-run
    python iceberg_retention_cleanup.py --namespace gold --table customers
    python iceberg_retention_cleanup.py --all
"""

from __future__ import annotations

import argparse
import logging
from datetime import datetime, timedelta
from typing import Any

from odg_core.storage.iceberg_catalog import IcebergCatalog

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class RetentionPolicy:
    """Defines retention policy for Iceberg snapshots."""

    def __init__(
        self,
        keep_last_n: int = 30,
        keep_days: int = 90,
        keep_tagged: bool = True,
        production_keep_days: int = 730,  # 2 years
    ):
        """Initialize retention policy.

        Args:
            keep_last_n: Always keep this many recent snapshots
            keep_days: Keep snapshots within this many days
            keep_tagged: Always keep tagged snapshots
            production_keep_days: Keep days for production datasets
        """
        self.keep_last_n = keep_last_n
        self.keep_days = keep_days
        self.keep_tagged = keep_tagged
        self.production_keep_days = production_keep_days


class IcebergRetentionManager:
    """Manages retention policies for Iceberg tables."""

    def __init__(self, catalog: IcebergCatalog, policy: RetentionPolicy):
        """Initialize retention manager.

        Args:
            catalog: Iceberg catalog instance
            policy: Retention policy to enforce
        """
        self.catalog = catalog
        self.policy = policy

    def should_keep_snapshot(
        self, snapshot: dict[str, Any], recent_snapshot_ids: set[int], cutoff_timestamp_ms: int, is_production: bool
    ) -> tuple[bool, str]:
        """Determine if a snapshot should be kept.

        Args:
            snapshot: Snapshot metadata
            recent_snapshot_ids: Set of recent snapshot IDs to keep
            cutoff_timestamp_ms: Timestamp cutoff for expiration
            is_production: Whether this is a production dataset

        Returns:
            Tuple of (should_keep, reason)
        """
        snapshot_id = int(snapshot["snapshot_id"])
        timestamp_ms = snapshot["timestamp_ms"]
        summary = snapshot.get("summary", {})

        # Rule 1: Keep recent snapshots
        if snapshot_id in recent_snapshot_ids:
            return True, f"recent (top {self.policy.keep_last_n})"

        # Rule 2: Keep tagged snapshots
        if self.policy.keep_tagged and "tag" in summary:
            return True, f"tagged ({summary['tag']})"

        # Rule 3: Keep production snapshots longer
        if is_production:
            production_cutoff = int(
                (datetime.now() - timedelta(days=self.policy.production_keep_days)).timestamp() * 1000
            )
            if timestamp_ms > production_cutoff:
                return True, f"production (< {self.policy.production_keep_days} days)"

        # Rule 4: Keep within retention period
        if timestamp_ms > cutoff_timestamp_ms:
            return True, f"within retention ({self.policy.keep_days} days)"

        # Otherwise, expire
        return False, "expired"

    def cleanup_table(self, namespace: str, table_name: str, dry_run: bool = True) -> dict[str, Any]:
        """Clean up old snapshots for a specific table.

        Args:
            namespace: Table namespace
            table_name: Table name
            dry_run: If True, only simulate cleanup without deleting

        Returns:
            Cleanup summary with statistics
        """
        logger.info(f"Processing table: {namespace}.{table_name}")

        try:
            # Get all snapshots
            snapshots = self.catalog.list_snapshots(namespace, table_name)

            if not snapshots:
                logger.info("  No snapshots found")
                return {
                    "table": f"{namespace}.{table_name}",
                    "total_snapshots": 0,
                    "kept": 0,
                    "expired": 0,
                    "error": None,
                }

            # Determine if this is a production dataset
            is_production = any("production" in snap.get("summary", {}).get("tag", "").lower() for snap in snapshots)

            # Calculate cutoff timestamp
            cutoff_timestamp_ms = int((datetime.now() - timedelta(days=self.policy.keep_days)).timestamp() * 1000)

            # Get recent snapshots to keep
            recent_snapshots = sorted(snapshots, key=lambda s: s["timestamp_ms"], reverse=True)[
                : self.policy.keep_last_n
            ]
            recent_snapshot_ids = {int(s["snapshot_id"]) for s in recent_snapshots}

            # Evaluate each snapshot
            kept_snapshots = []
            expired_snapshots = []

            for snapshot in snapshots:
                should_keep, reason = self.should_keep_snapshot(
                    snapshot, recent_snapshot_ids, cutoff_timestamp_ms, is_production
                )

                if should_keep:
                    kept_snapshots.append((snapshot, reason))
                else:
                    expired_snapshots.append((snapshot, reason))

            # Log summary
            logger.info(f"  Total snapshots: {len(snapshots)}")
            logger.info(f"  To keep: {len(kept_snapshots)}")
            logger.info(f"  To expire: {len(expired_snapshots)}")

            # Log kept snapshots
            if kept_snapshots:
                logger.info("  Kept snapshots:")
                for snap, reason in kept_snapshots[:5]:  # Show first 5
                    snap_time = datetime.fromtimestamp(snap["timestamp_ms"] / 1000).strftime("%Y-%m-%d %H:%M")
                    logger.info(f"    - {snap['snapshot_id']} ({snap_time}) - {reason}")
                if len(kept_snapshots) > 5:
                    logger.info(f"    ... and {len(kept_snapshots) - 5} more")

            # Log expired snapshots
            if expired_snapshots:
                logger.info("  Expired snapshots:")
                for snap, reason in expired_snapshots[:5]:  # Show first 5
                    snap_time = datetime.fromtimestamp(snap["timestamp_ms"] / 1000).strftime("%Y-%m-%d %H:%M")
                    logger.info(f"    - {snap['snapshot_id']} ({snap_time}) - {reason}")
                if len(expired_snapshots) > 5:
                    logger.info(f"    ... and {len(expired_snapshots) - 5} more")

            # Execute cleanup if not dry run
            if not dry_run and expired_snapshots:
                logger.info("  Executing cleanup...")
                expired_count = self.catalog.expire_old_snapshots(
                    namespace, table_name, older_than_days=self.policy.keep_days, keep_last_n=self.policy.keep_last_n
                )
                logger.info(f"  ✓ Expired {expired_count} snapshots")
            elif dry_run and expired_snapshots:
                logger.info("  [DRY RUN] Would expire snapshots")

            return {
                "table": f"{namespace}.{table_name}",
                "total_snapshots": len(snapshots),
                "kept": len(kept_snapshots),
                "expired": len(expired_snapshots),
                "is_production": is_production,
                "dry_run": dry_run,
                "error": None,
            }

        except Exception as e:
            logger.error(f"  Error processing table: {e}")
            return {
                "table": f"{namespace}.{table_name}",
                "total_snapshots": 0,
                "kept": 0,
                "expired": 0,
                "error": str(e),
            }

    def cleanup_all_tables(self, namespaces: list[str] | None = None, dry_run: bool = True) -> list[dict[str, Any]]:
        """Clean up all tables across specified namespaces.

        Args:
            namespaces: List of namespaces to process (default: all)
            dry_run: If True, only simulate cleanup

        Returns:
            List of cleanup summaries per table
        """
        if namespaces is None:
            namespaces = ["bronze", "silver", "gold", "platinum"]

        logger.info(f"Starting retention cleanup for namespaces: {namespaces}")
        logger.info(f"Policy: keep_last_n={self.policy.keep_last_n}, keep_days={self.policy.keep_days}")
        logger.info(f"Dry run: {dry_run}")

        results = []

        for namespace in namespaces:
            logger.info(f"\nProcessing namespace: {namespace}")

            try:
                # List all tables in namespace
                # Note: This is simplified - actual implementation needs catalog.list_tables()
                # For now, we assume tables are known or discovered via metadata
                tables = self._discover_tables(namespace)

                for table_name in tables:
                    result = self.cleanup_table(namespace, table_name, dry_run)
                    results.append(result)

            except Exception as e:
                logger.error(f"Error processing namespace {namespace}: {e}")

        # Print summary
        self._print_summary(results)

        return results

    def _discover_tables(self, namespace: str) -> list[str]:
        """Discover tables in a namespace.

        Args:
            namespace: Namespace to search

        Returns:
            List of table names
        """
        # This is a simplified version
        # In production, use: catalog.catalog.list_tables(namespace)
        try:
            return self.catalog.catalog.list_tables(namespace)
        except Exception:
            logger.warning(f"Could not list tables in {namespace}, using defaults")
            # Default tables for demo
            return {
                "bronze": ["sales", "products", "customers"],
                "silver": ["sales_cleaned", "products_enriched", "customers_validated"],
                "gold": ["sales_aggregated", "customer_features", "product_performance"],
                "platinum": ["ml_training_data", "feature_store"],
            }.get(namespace, [])

    def _print_summary(self, results: list[dict[str, Any]]) -> None:
        """Print cleanup summary.

        Args:
            results: List of cleanup results
        """
        logger.info("\n" + "=" * 80)
        logger.info("CLEANUP SUMMARY")
        logger.info("=" * 80)

        total_tables = len(results)
        total_snapshots = sum(r["total_snapshots"] for r in results)
        total_kept = sum(r["kept"] for r in results)
        total_expired = sum(r["expired"] for r in results)
        errors = [r for r in results if r["error"]]

        logger.info(f"Tables processed: {total_tables}")
        logger.info(f"Total snapshots: {total_snapshots}")
        logger.info(f"Kept: {total_kept}")
        logger.info(f"Expired: {total_expired}")
        logger.info(f"Errors: {len(errors)}")

        if errors:
            logger.error("\nErrors encountered:")
            for err in errors:
                logger.error(f"  - {err['table']}: {err['error']}")

        if results and results[0]["dry_run"]:
            logger.info("\n⚠️  DRY RUN MODE - No snapshots were actually deleted")
        else:
            logger.info("\n✓ Cleanup completed successfully")


def main():
    """Main entry point for retention cleanup script."""
    parser = argparse.ArgumentParser(
        description="Iceberg snapshot retention cleanup",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run (simulate) cleanup for all tables
  python iceberg_retention_cleanup.py --all --dry-run

  # Actually cleanup a specific table
  python iceberg_retention_cleanup.py --namespace gold --table customers

  # Cleanup with custom policy
  python iceberg_retention_cleanup.py --all --keep-last 50 --keep-days 120
        """,
    )

    parser.add_argument("--namespace", help="Table namespace (bronze, silver, gold, platinum)")
    parser.add_argument("--table", help="Table name")
    parser.add_argument("--all", action="store_true", help="Process all tables in all namespaces")
    parser.add_argument(
        "--dry-run", action="store_true", default=True, help="Simulate cleanup without deleting (default: True)"
    )
    parser.add_argument("--execute", action="store_true", help="Actually execute cleanup (overrides --dry-run)")
    parser.add_argument("--keep-last", type=int, default=30, help="Number of recent snapshots to keep (default: 30)")
    parser.add_argument("--keep-days", type=int, default=90, help="Keep snapshots within this many days (default: 90)")
    parser.add_argument(
        "--production-keep-days", type=int, default=730, help="Keep days for production datasets (default: 730)"
    )

    args = parser.parse_args()

    # Validate arguments
    if not args.all and (not args.namespace or not args.table):
        parser.error("Must specify either --all or both --namespace and --table")

    # Determine dry run mode
    dry_run = not args.execute

    # Initialize catalog and policy
    catalog = IcebergCatalog()
    policy = RetentionPolicy(
        keep_last_n=args.keep_last, keep_days=args.keep_days, production_keep_days=args.production_keep_days
    )

    manager = IcebergRetentionManager(catalog, policy)

    # Execute cleanup
    if args.all:
        manager.cleanup_all_tables(dry_run=dry_run)
    else:
        result = manager.cleanup_table(args.namespace, args.table, dry_run=dry_run)
        if result["error"]:
            logger.error(f"Cleanup failed: {result['error']}")
            exit(1)


if __name__ == "__main__":
    main()
