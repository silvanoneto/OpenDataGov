"""Iceberg table compaction for performance optimization.

Compaction consolidates small files into larger files, improving query performance
by reducing the number of file opens and metadata overhead.

Benefits:
- Reduced query latency (fewer files to scan)
- Lower S3 API costs (fewer GET requests)
- Better compression ratios
- Improved cache hit rates

Usage:
    python iceberg_compaction.py --namespace gold --table customers --execute
    python iceberg_compaction.py --all --min-file-size-mb 10
"""

from __future__ import annotations

import argparse
import logging
from datetime import datetime
from typing import Any

from odg_core.storage.iceberg_catalog import IcebergCatalog

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class CompactionPolicy:
    """Defines compaction policy for Iceberg tables."""

    def __init__(
        self,
        target_file_size_mb: int = 512,
        min_file_size_mb: int = 10,
        max_concurrent_files: int = 100,
        rewrite_all: bool = False,
    ):
        """Initialize compaction policy.

        Args:
            target_file_size_mb: Target file size after compaction
            min_file_size_mb: Minimum file size to trigger compaction
            max_concurrent_files: Max files to compact in single operation
            rewrite_all: If True, rewrite all files regardless of size
        """
        self.target_file_size_mb = target_file_size_mb
        self.target_file_size_bytes = target_file_size_mb * 1024 * 1024
        self.min_file_size_mb = min_file_size_mb
        self.min_file_size_bytes = min_file_size_mb * 1024 * 1024
        self.max_concurrent_files = max_concurrent_files
        self.rewrite_all = rewrite_all


class IcebergCompactionManager:
    """Manages compaction operations for Iceberg tables."""

    def __init__(self, catalog: IcebergCatalog, policy: CompactionPolicy):
        """Initialize compaction manager.

        Args:
            catalog: Iceberg catalog instance
            policy: Compaction policy
        """
        self.catalog = catalog
        self.policy = policy

    def analyze_table(self, namespace: str, table_name: str) -> dict[str, Any]:
        """Analyze table to determine if compaction is needed.

        Args:
            namespace: Table namespace
            table_name: Table name

        Returns:
            Analysis results with file statistics
        """
        logger.info(f"Analyzing table: {namespace}.{table_name}")

        try:
            table = self.catalog.catalog.load_table(f"{namespace}.{table_name}")
            current_snapshot = table.current_snapshot()

            if not current_snapshot:
                return {
                    "table": f"{namespace}.{table_name}",
                    "total_files": 0,
                    "total_size_mb": 0,
                    "needs_compaction": False,
                    "reason": "No data",
                }

            # Get manifest files
            manifests = list(current_snapshot.manifests(table.io))

            total_files = 0
            total_size_bytes = 0
            small_files = 0
            small_files_size = 0

            for manifest in manifests:
                for entry in manifest.fetch_manifest_entry(table.io):
                    data_file = entry.data_file
                    file_size = data_file.file_size_in_bytes

                    total_files += 1
                    total_size_bytes += file_size

                    if file_size < self.policy.min_file_size_bytes:
                        small_files += 1
                        small_files_size += file_size

            avg_file_size_mb = (total_size_bytes / total_files / 1024 / 1024) if total_files > 0 else 0

            # Determine if compaction needed
            needs_compaction = (
                small_files > 10  # More than 10 small files
                or avg_file_size_mb < self.policy.min_file_size_mb
                or self.policy.rewrite_all
            )

            analysis = {
                "table": f"{namespace}.{table_name}",
                "total_files": total_files,
                "total_size_mb": round(total_size_bytes / 1024 / 1024, 2),
                "avg_file_size_mb": round(avg_file_size_mb, 2),
                "small_files": small_files,
                "small_files_size_mb": round(small_files_size / 1024 / 1024, 2),
                "needs_compaction": needs_compaction,
                "reason": self._get_compaction_reason(small_files, avg_file_size_mb, self.policy.rewrite_all),
            }

            logger.info(f"  Total files: {total_files}")
            logger.info(f"  Total size: {analysis['total_size_mb']} MB")
            logger.info(f"  Avg file size: {avg_file_size_mb:.2f} MB")
            logger.info(f"  Small files (<{self.policy.min_file_size_mb} MB): {small_files}")
            logger.info(f"  Needs compaction: {needs_compaction}")

            return analysis

        except Exception as e:
            logger.error(f"Error analyzing table: {e}")
            return {
                "table": f"{namespace}.{table_name}",
                "total_files": 0,
                "total_size_mb": 0,
                "needs_compaction": False,
                "error": str(e),
            }

    def _get_compaction_reason(self, small_files: int, avg_file_size_mb: float, rewrite_all: bool) -> str:
        """Determine reason for compaction recommendation."""
        if rewrite_all:
            return "Rewrite all files policy"
        elif small_files > 10:
            return f"Too many small files ({small_files})"
        elif avg_file_size_mb < self.policy.min_file_size_mb:
            return f"Average file size too small ({avg_file_size_mb:.2f} MB)"
        else:
            return "No compaction needed"

    def compact_table(self, namespace: str, table_name: str, dry_run: bool = True) -> dict[str, Any]:
        """Compact a specific table by rewriting data files.

        Args:
            namespace: Table namespace
            table_name: Table name
            dry_run: If True, only analyze without compacting

        Returns:
            Compaction results
        """
        # Analyze first
        analysis = self.analyze_table(namespace, table_name)

        if not analysis["needs_compaction"]:
            logger.info(f"  Skipping compaction: {analysis['reason']}")
            return {
                **analysis,
                "compacted": False,
                "files_before": analysis["total_files"],
                "files_after": analysis["total_files"],
                "size_before_mb": analysis["total_size_mb"],
                "size_after_mb": analysis["total_size_mb"],
            }

        if dry_run:
            logger.info("  [DRY RUN] Would compact table")
            return {**analysis, "compacted": False, "dry_run": True}

        # Execute compaction
        logger.info("  Starting compaction...")
        start_time = datetime.now()

        try:
            table = self.catalog.catalog.load_table(f"{namespace}.{table_name}")

            # Iceberg compaction using rewrite_data_files action
            # This rewrites small files into larger optimized files

            # Read all data
            logger.info("  Reading table data...")
            df = table.scan().to_pandas()

            # Rewrite as optimized files
            logger.info("  Writing compacted files...")
            table.overwrite(df)

            # Analyze after compaction
            analysis_after = self.analyze_table(namespace, table_name)

            duration_seconds = (datetime.now() - start_time).total_seconds()

            result = {
                "table": f"{namespace}.{table_name}",
                "compacted": True,
                "files_before": analysis["total_files"],
                "files_after": analysis_after["total_files"],
                "size_before_mb": analysis["total_size_mb"],
                "size_after_mb": analysis_after["total_size_mb"],
                "compression_ratio": (
                    analysis["total_size_mb"] / analysis_after["total_size_mb"]
                    if analysis_after["total_size_mb"] > 0
                    else 1.0
                ),
                "duration_seconds": round(duration_seconds, 2),
                "error": None,
            }

            logger.info(f"  ✓ Compaction completed in {duration_seconds:.2f}s")
            logger.info(f"    Files: {result['files_before']} → {result['files_after']}")
            logger.info(f"    Size: {result['size_before_mb']:.2f} MB → {result['size_after_mb']:.2f} MB")

            return result

        except Exception as e:
            logger.error(f"  ✗ Compaction failed: {e}")
            return {**analysis, "compacted": False, "error": str(e)}

    def compact_all_tables(self, namespaces: list[str] | None = None, dry_run: bool = True) -> list[dict[str, Any]]:
        """Compact all tables that need it.

        Args:
            namespaces: List of namespaces to process
            dry_run: If True, only analyze

        Returns:
            List of compaction results
        """
        if namespaces is None:
            namespaces = ["bronze", "silver", "gold", "platinum"]

        logger.info(f"Starting compaction for namespaces: {namespaces}")
        logger.info(f"Policy: target={self.policy.target_file_size_mb}MB, min={self.policy.min_file_size_mb}MB")
        logger.info(f"Dry run: {dry_run}")

        results = []

        for namespace in namespaces:
            logger.info(f"\nProcessing namespace: {namespace}")

            try:
                tables = self._discover_tables(namespace)

                for table_name in tables:
                    result = self.compact_table(namespace, table_name, dry_run)
                    results.append(result)

            except Exception as e:
                logger.error(f"Error processing namespace {namespace}: {e}")

        # Print summary
        self._print_summary(results)

        return results

    def _discover_tables(self, namespace: str) -> list[str]:
        """Discover tables in namespace."""
        try:
            return self.catalog.catalog.list_tables(namespace)
        except Exception:
            logger.warning(f"Could not list tables in {namespace}")
            return []

    def _print_summary(self, results: list[dict[str, Any]]) -> None:
        """Print compaction summary."""
        logger.info("\n" + "=" * 80)
        logger.info("COMPACTION SUMMARY")
        logger.info("=" * 80)

        total_tables = len(results)
        compacted_tables = sum(1 for r in results if r.get("compacted", False))
        total_files_before = sum(r.get("files_before", 0) for r in results)
        total_files_after = sum(r.get("files_after", 0) for r in results)
        total_size_before = sum(r.get("size_before_mb", 0) for r in results)
        total_size_after = sum(r.get("size_after_mb", 0) for r in results)
        errors = [r for r in results if r.get("error")]

        logger.info(f"Tables processed: {total_tables}")
        logger.info(f"Tables compacted: {compacted_tables}")
        logger.info(f"Files: {total_files_before} → {total_files_after}")
        logger.info(f"Size: {total_size_before:.2f} MB → {total_size_after:.2f} MB")

        if total_size_before > 0:
            space_saved_mb = total_size_before - total_size_after
            space_saved_pct = (space_saved_mb / total_size_before) * 100
            logger.info(f"Space saved: {space_saved_mb:.2f} MB ({space_saved_pct:.1f}%)")

        logger.info(f"Errors: {len(errors)}")

        if errors:
            logger.error("\nErrors encountered:")
            for err in errors:
                logger.error(f"  - {err['table']}: {err['error']}")

        if results and not results[0].get("compacted", False):
            logger.info("\n⚠️  DRY RUN MODE - No files were actually compacted")
        else:
            logger.info("\n✓ Compaction completed successfully")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Iceberg table compaction for performance optimization")

    parser.add_argument("--namespace", help="Table namespace")
    parser.add_argument("--table", help="Table name")
    parser.add_argument("--all", action="store_true", help="Compact all tables")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Analyze only")
    parser.add_argument("--execute", action="store_true", help="Execute compaction")
    parser.add_argument("--target-file-size-mb", type=int, default=512, help="Target file size (MB)")
    parser.add_argument("--min-file-size-mb", type=int, default=10, help="Min file size threshold (MB)")

    args = parser.parse_args()

    if not args.all and (not args.namespace or not args.table):
        parser.error("Must specify either --all or both --namespace and --table")

    dry_run = not args.execute

    catalog = IcebergCatalog()
    policy = CompactionPolicy(target_file_size_mb=args.target_file_size_mb, min_file_size_mb=args.min_file_size_mb)

    manager = IcebergCompactionManager(catalog, policy)

    if args.all:
        manager.compact_all_tables(dry_run=dry_run)
    else:
        manager.compact_table(args.namespace, args.table, dry_run=dry_run)


if __name__ == "__main__":
    main()
