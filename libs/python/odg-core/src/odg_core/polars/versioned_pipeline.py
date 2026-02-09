"""Polars lazy plan versioning with lineage tracking.

Provides automatic versioning of Polars lazy execution plans based on
plan structure hash, with input/output dataset tracking.
"""

from __future__ import annotations

import hashlib
import os
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import polars as pl


class VersionedPolarsJob:
    """Wrapper for Polars lazy plans with versioning and lineage tracking.

    Serializes the lazy execution plan and computes a hash to detect changes.
    Tracks execution with Iceberg snapshot IDs for reproducibility.

    Example:
        >>> import polars as pl
        >>> from odg_core.polars.versioned_pipeline import VersionedPolarsJob
        >>>
        >>> lazy_df = (
        ...     pl.scan_parquet("s3://lakehouse/silver/sales/*.parquet")
        ...     .filter(pl.col("amount") > 100)
        ...     .groupby("customer_id")
        ...     .agg(pl.col("amount").sum().alias("total_sales"))
        ... )
        >>>
        >>> job = VersionedPolarsJob("aggregate_sales", lazy_df)
        >>> result = job.execute_and_track("s3://lakehouse/gold/customer_sales.parquet")
    """

    def __init__(
        self,
        job_name: str,
        lazy_plan: pl.LazyFrame,
        input_datasets: list[str] | None = None,
        git_commit: str | None = None,
    ):
        """Initialize versioned Polars job.

        Args:
            job_name: Job identifier (e.g., "aggregate_sales")
            lazy_plan: Polars LazyFrame to execute
            input_datasets: List of input dataset IDs (optional, auto-detected if possible)
            git_commit: Git commit SHA (optional)
        """
        self.job_name = job_name
        self.lazy_plan = lazy_plan
        self.input_datasets = input_datasets or []
        self.git_commit = git_commit or os.getenv("GIT_COMMIT")
        self.plan_hash = self._compute_plan_hash()

    def _compute_plan_hash(self) -> str:
        """Compute SHA256 hash of the Polars execution plan.

        Uses the optimized query plan string representation from Polars.

        Returns:
            12-character hash of the execution plan
        """
        try:
            # Get optimized query plan as string
            plan_str = self.lazy_plan.explain(optimized=True)
            full_hash = hashlib.sha256(plan_str.encode()).hexdigest()
            return full_hash[:12]
        except Exception as e:
            # Fallback to job name hash if explain() fails
            print(f"Warning: Could not explain Polars plan: {e}")
            return hashlib.sha256(self.job_name.encode()).hexdigest()[:12]

    def _get_next_version(self) -> int:
        """Get next version number for this job.

        Returns:
            Next sequential version number
        """
        try:
            from sqlalchemy import create_engine, func, select
            from sqlalchemy.orm import Session

            from odg_core.db.tables import PipelineVersionRow

            db_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/odg")
            engine = create_engine(db_url)

            with Session(engine) as session:
                last_version = session.execute(
                    select(func.max(PipelineVersionRow.version)).where(PipelineVersionRow.pipeline_id == self.job_name)
                ).scalar()

                return (last_version or 0) + 1

        except Exception:
            return 1

    def register_version(self) -> int:
        """Register this Polars plan version in the database.

        Creates a new entry in the pipeline_versions table if the plan hash
        doesn't already exist. Returns the version number.

        Returns:
            Version number (sequential integer)
        """
        try:
            from sqlalchemy import create_engine, select
            from sqlalchemy.orm import Session

            from odg_core.db.tables import PipelineVersionRow

            db_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/odg")
            engine = create_engine(db_url)

            with Session(engine) as session:
                # Check if this exact plan hash already exists
                existing = (
                    session.execute(
                        select(PipelineVersionRow).where(
                            PipelineVersionRow.pipeline_id == self.job_name,
                            PipelineVersionRow.dag_hash == self.plan_hash,
                        )
                    )
                    .scalars()
                    .first()
                )

                if existing:
                    return existing.version

                next_version = self._get_next_version()

                # Get plan explanations
                try:
                    optimized_plan = self.lazy_plan.explain(optimized=True)
                    unoptimized_plan = self.lazy_plan.explain(optimized=False)
                except Exception:
                    optimized_plan = "Plan explain not available"
                    unoptimized_plan = "Plan explain not available"

                # Create new version
                version_row = PipelineVersionRow(
                    pipeline_id=self.job_name,
                    version=next_version,
                    dag_definition={
                        "type": "polars",
                        "plan": optimized_plan[:500],  # First 500 chars of optimized plan
                        "inputs": self.input_datasets,
                    },
                    dag_hash=self.plan_hash,
                    transformation_code=unoptimized_plan,  # Store full unoptimized plan
                    transformation_hash=self.plan_hash,
                    git_commit=self.git_commit,
                    created_by="polars",
                    is_active=True,
                )

                session.add(version_row)
                session.commit()

                return next_version

        except Exception as e:
            print(f"Warning: Failed to register Polars plan version for {self.job_name}: {e}")
            return 0

    def execute_and_track(self, output_path: str, namespace: str = "gold") -> pl.DataFrame:
        """Execute Polars lazy plan and track lineage.

        Args:
            output_path: Path to write output (e.g., S3/local path for Parquet)
            namespace: Iceberg namespace for tracking (default: "gold")

        Returns:
            Computed DataFrame

        Raises:
            Exception: If execution fails
        """
        import uuid

        from odg_core.lineage.emitter import emit_lineage_event

        run_id = str(uuid.uuid4())
        start_time = datetime.now(UTC)

        try:
            # Execute lazy plan (this triggers computation)
            df = self.lazy_plan.collect()

            # Write output
            df.write_parquet(output_path)

            # Track execution success
            self._track_execution(
                run_id=run_id, status="success", start_time=start_time, rows_processed=len(df), output_path=output_path
            )

            # Emit lineage event
            emit_lineage_event(
                job_name=f"polars_{self.job_name}",
                job_namespace="polars",
                inputs=[{"namespace": namespace, "name": dataset_id} for dataset_id in self.input_datasets],
                outputs=[
                    {
                        "namespace": namespace,
                        "name": self.job_name,
                        "facets": {"rows": len(df), "output_path": output_path},
                    }
                ],
                event_type="COMPLETE",
                run_id=run_id,
            )

            return df

        except Exception as e:
            # Track execution failure
            self._track_execution(run_id=run_id, status="failed", start_time=start_time, error_message=str(e))
            raise

    def _track_execution(
        self,
        run_id: str,
        status: str,
        start_time: datetime,
        rows_processed: int | None = None,
        output_path: str | None = None,
        error_message: str | None = None,
    ) -> None:
        """Track execution in pipeline_executions table.

        Args:
            run_id: Unique execution identifier
            status: Execution status (success, failed)
            start_time: When execution started
            rows_processed: Number of rows processed (optional)
            output_path: Output file path (optional)
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
                            PipelineVersionRow.dag_hash == self.plan_hash,
                        )
                    )
                    .scalars()
                    .first()
                )

                version = version_row.version if version_row else 0

                end_time = datetime.now(UTC)
                duration_ms = int((end_time - start_time).total_seconds() * 1000)

                # Create execution record
                execution = PipelineExecutionRow(
                    run_id=run_id,
                    pipeline_id=self.job_name,
                    pipeline_version=version,
                    status=status,
                    start_time=start_time,
                    end_time=end_time,
                    duration_ms=duration_ms,
                    output_datasets=[{"path": output_path}] if output_path else None,
                    rows_processed=rows_processed,
                    error_message=error_message,
                )

                session.add(execution)
                session.commit()

        except Exception as e:
            print(f"Warning: Failed to track Polars execution: {e}")


def create_versioned_pipeline(job_name: str, lazy_plan: pl.LazyFrame) -> VersionedPolarsJob:
    """Factory function to create a versioned Polars job.

    Args:
        job_name: Job identifier
        lazy_plan: Polars LazyFrame to execute

    Returns:
        Configured VersionedPolarsJob instance

    Example:
        >>> import polars as pl
        >>> from odg_core.polars import create_versioned_pipeline
        >>>
        >>> lazy_df = pl.scan_csv("data.csv").filter(pl.col("value") > 0)
        >>> job = create_versioned_pipeline("process_data", lazy_df)
        >>> version = job.register_version()
        >>> result = job.execute_and_track("output.parquet")
    """
    return VersionedPolarsJob(job_name=job_name, lazy_plan=lazy_plan)
