"""DuckDB transformation versioning with lineage tracking.

Provides automatic versioning of SQL queries based on query hash,
with input/output dataset tracking via Iceberg snapshots.
"""

from __future__ import annotations

import hashlib
import os
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import duckdb
    import pandas as pd


class VersionedDuckDBJob:
    """Wrapper for DuckDB SQL transformations with versioning and lineage.

    Computes a hash of the SQL query and registers each version in the
    pipeline_versions table. Tracks execution with Iceberg snapshot IDs.

    Example:
        >>> import duckdb
        >>> from odg_core.duckdb.versioned_query import VersionedDuckDBJob
        >>>
        >>> job = VersionedDuckDBJob(
        ...     job_name="aggregate_orders",
        ...     sql_query='''
        ...         SELECT
        ...             customer_id,
        ...             COUNT(*) as order_count,
        ...             SUM(amount) as total_amount
        ...         FROM orders
        ...         WHERE status = 'completed'
        ...         GROUP BY customer_id
        ...     ''',
        ...     input_tables=["orders"],
        ...     output_table="customer_aggregates"
        ... )
        >>>
        >>> conn = duckdb.connect()
        >>> result = job.execute(conn)
    """

    def __init__(
        self, job_name: str, sql_query: str, input_tables: list[str], output_table: str, git_commit: str | None = None
    ):
        """Initialize versioned DuckDB job.

        Args:
            job_name: Job identifier (e.g., "aggregate_orders")
            sql_query: SQL query to execute
            input_tables: List of input table names
            output_table: Output table name
            git_commit: Git commit SHA (optional)
        """
        self.job_name = job_name
        self.sql_query = sql_query.strip()
        self.input_tables = input_tables
        self.output_table = output_table
        self.git_commit = git_commit or os.getenv("GIT_COMMIT")
        self.query_hash = self._compute_query_hash()

    def _compute_query_hash(self) -> str:
        """Compute SHA256 hash of the SQL query.

        Normalizes query by stripping whitespace and converting to lowercase
        before hashing to detect semantic changes.

        Returns:
            12-character hash of the normalized SQL query
        """
        # Normalize query: lowercase, strip extra whitespace
        normalized = " ".join(self.sql_query.lower().split())
        full_hash = hashlib.sha256(normalized.encode()).hexdigest()
        return full_hash[:12]

    def register_version(self) -> int:
        """Register this DuckDB query version in the database.

        Creates a new entry in the pipeline_versions table if the query hash
        doesn't already exist. Returns the version number.

        Returns:
            Version number (sequential integer)
        """
        try:
            from sqlalchemy import create_engine, func, select
            from sqlalchemy.orm import Session

            from odg_core.db.tables import PipelineVersionRow

            db_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/odg")
            engine = create_engine(db_url)

            with Session(engine) as session:
                # Check if this exact query hash already exists
                existing = (
                    session.execute(
                        select(PipelineVersionRow).where(
                            PipelineVersionRow.pipeline_id == self.job_name,
                            PipelineVersionRow.transformation_hash == self.query_hash,
                        )
                    )
                    .scalars()
                    .first()
                )

                if existing:
                    return existing.version

                # Get next version number
                last_version = session.execute(
                    select(func.max(PipelineVersionRow.version)).where(PipelineVersionRow.pipeline_id == self.job_name)
                ).scalar()

                next_version = (last_version or 0) + 1

                # Create new version
                version_row = PipelineVersionRow(
                    pipeline_id=self.job_name,
                    version=next_version,
                    dag_definition={
                        "type": "duckdb",
                        "inputs": self.input_tables,
                        "output": self.output_table,
                        "query_preview": self.sql_query[:200],  # First 200 chars
                    },
                    dag_hash=self.query_hash,
                    transformation_code=self.sql_query,
                    transformation_hash=self.query_hash,
                    git_commit=self.git_commit,
                    created_by="duckdb",
                    is_active=True,
                )

                session.add(version_row)
                session.commit()

                return next_version

        except Exception as e:
            print(f"Warning: Failed to register DuckDB query version for {self.job_name}: {e}")
            return 0

    def execute(self, conn: duckdb.DuckDBPyConnection, namespace: str = "gold") -> pd.DataFrame:
        """Execute DuckDB query and capture lineage with Iceberg snapshots.

        Args:
            conn: DuckDB connection
            namespace: Iceberg namespace for tables (default: "gold")

        Returns:
            Query result as pandas DataFrame

        Raises:
            Exception: If query execution fails
        """
        import uuid

        from odg_core.lineage.emitter import emit_lineage_event
        from odg_core.storage.iceberg_catalog import IcebergCatalog

        run_id = str(uuid.uuid4())

        try:
            iceberg = IcebergCatalog()

            # Capture input snapshots BEFORE query execution
            input_snapshots: list[dict[str, str | None]] = []
            for table in self.input_tables:
                try:
                    snapshot_id = iceberg.get_snapshot_id(namespace, table)
                    input_snapshots.append({"name": table, "snapshot": snapshot_id})
                except Exception as e:
                    print(f"Warning: Could not get snapshot for {namespace}.{table}: {e}")
                    input_snapshots.append({"name": table, "snapshot": None})

            # Execute DuckDB query
            result = conn.execute(self.sql_query).df()

            # Track execution success
            self._track_execution(
                run_id=run_id, status="success", rows_processed=len(result), input_snapshots=input_snapshots
            )

            # Emit lineage event
            emit_lineage_event(
                job_name=f"duckdb_{self.job_name}",
                job_namespace="duckdb",
                inputs=[
                    {"namespace": namespace, "name": table, "facets": {"snapshot": snap["snapshot"]}}
                    for table, snap in zip(self.input_tables, input_snapshots, strict=False)
                ],
                outputs=[{"namespace": namespace, "name": self.output_table, "facets": {"rows": len(result)}}],
                event_type="COMPLETE",
                run_id=run_id,
            )

            return result

        except Exception as e:
            # Track execution failure
            self._track_execution(run_id=run_id, status="failed", error_message=str(e))
            raise

    def _track_execution(
        self,
        run_id: str,
        status: str,
        rows_processed: int | None = None,
        input_snapshots: list[dict[str, Any]] | None = None,
        error_message: str | None = None,
    ) -> None:
        """Track execution in pipeline_executions table.

        Args:
            run_id: Unique execution identifier
            status: Execution status (success, failed)
            rows_processed: Number of rows processed (optional)
            input_snapshots: Input dataset snapshots (optional)
            error_message: Error message if failed (optional)
        """
        try:
            from sqlalchemy import create_engine, select
            from sqlalchemy.orm import Session

            from odg_core.db.tables import PipelineExecutionRow, PipelineVersionRow

            db_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/odg")
            engine = create_engine(db_url)

            with Session(engine) as session:
                # Get version number
                version_row = (
                    session.execute(
                        select(PipelineVersionRow).where(
                            PipelineVersionRow.pipeline_id == self.job_name,
                            PipelineVersionRow.transformation_hash == self.query_hash,
                        )
                    )
                    .scalars()
                    .first()
                )

                version = version_row.version if version_row else 0

                # Create execution record
                execution = PipelineExecutionRow(
                    run_id=run_id,
                    pipeline_id=self.job_name,
                    pipeline_version=version,
                    status=status,
                    start_time=datetime.now(UTC),
                    end_time=datetime.now(UTC),
                    duration_ms=0,  # DuckDB queries are typically fast
                    input_datasets=input_snapshots,
                    rows_processed=rows_processed,
                    error_message=error_message,
                )

                session.add(execution)
                session.commit()

        except Exception as e:
            print(f"Warning: Failed to track DuckDB execution: {e}")


def create_versioned_query(
    job_name: str, sql_query: str, input_tables: list[str], output_table: str
) -> VersionedDuckDBJob:
    """Factory function to create a versioned DuckDB job.

    Args:
        job_name: Job identifier
        sql_query: SQL query to execute
        input_tables: List of input table names
        output_table: Output table name

    Returns:
        Configured VersionedDuckDBJob instance

    Example:
        >>> job = create_versioned_query(
        ...     job_name="daily_sales_summary",
        ...     sql_query="SELECT date, SUM(amount) FROM sales GROUP BY date",
        ...     input_tables=["sales"],
        ...     output_table="sales_summary"
        ... )
        >>> version = job.register_version()
    """
    return VersionedDuckDBJob(
        job_name=job_name, sql_query=sql_query, input_tables=input_tables, output_table=output_table
    )
