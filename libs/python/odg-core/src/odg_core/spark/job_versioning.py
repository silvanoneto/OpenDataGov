"""Spark job versioning and execution tracking.

Provides automatic versioning of Spark jobs based on code hash,
with execution tracking and lineage integration.
"""

from __future__ import annotations

import hashlib
import os
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pyspark.sql import SparkSession


class VersionedSparkJob:
    """Wrapper for Spark jobs with automatic versioning and lineage tracking.

    Computes a hash of the job file and registers each version in the
    pipeline_versions table. Tracks execution with input/output datasets.

    Example:
        >>> from pyspark.sql import SparkSession
        >>> from odg_core.spark.job_versioning import VersionedSparkJob
        >>> import uuid
        >>>
        >>> job = VersionedSparkJob(
        ...     job_name="transform_sales",
        ...     job_file=__file__,
        ...     input_datasets=["bronze/sales"],
        ...     output_datasets=["silver/sales"],
        ...     git_commit=os.getenv('GIT_COMMIT')
        ... )
        >>>
        >>> version = job.register_version()
        >>> print(f"Running job version: {version}")
        >>>
        >>> spark = SparkSession.builder.appName(f"transform_sales_v{version}").getOrCreate()
        >>> run_id = str(uuid.uuid4())
        >>> job.track_execution(spark, run_id)
        >>>
        >>> # ... run Spark transformations ...
        >>>
        >>> job.emit_lineage()
        >>> spark.stop()
    """

    def __init__(
        self,
        job_name: str,
        job_file: str,
        input_datasets: list[str],
        output_datasets: list[str],
        git_commit: str | None = None,
    ):
        """Initialize versioned Spark job.

        Args:
            job_name: Job identifier (e.g., "transform_sales")
            job_file: Path to the job Python file
            input_datasets: List of input dataset IDs (e.g., ["bronze/sales"])
            output_datasets: List of output dataset IDs (e.g., ["silver/sales"])
            git_commit: Git commit SHA (optional)
        """
        self.job_name = job_name
        self.job_file = job_file
        self.input_datasets = input_datasets
        self.output_datasets = output_datasets
        self.git_commit = git_commit or os.getenv("GIT_COMMIT")
        self.job_hash = self._compute_job_hash()

    def _compute_job_hash(self) -> str:
        """Compute SHA256 hash of the job file.

        Returns:
            12-character hash of the job file contents
        """
        try:
            with open(self.job_file, "rb") as f:
                full_hash = hashlib.sha256(f.read()).hexdigest()
                return full_hash[:12]
        except FileNotFoundError:
            # If file doesn't exist (e.g., running in deployed container), use job_name hash
            return hashlib.sha256(self.job_name.encode()).hexdigest()[:12]

    def register_version(self) -> int:
        """Register this Spark job version in the database.

        Creates a new entry in the pipeline_versions table if the job hash
        doesn't already exist. Returns the version number.

        Returns:
            Version number (sequential integer)
        """
        try:
            from sqlalchemy import create_engine, func, select
            from sqlalchemy.orm import Session

            from odg_core.db.tables import PipelineVersionRow

            # Get database URL from environment
            db_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/odg")
            engine = create_engine(db_url)

            with Session(engine) as session:
                # Check if this exact job hash already exists
                existing = (
                    session.execute(
                        select(PipelineVersionRow).where(
                            PipelineVersionRow.pipeline_id == self.job_name,
                            PipelineVersionRow.transformation_hash == self.job_hash,
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

                # Read job code
                try:
                    with open(self.job_file) as f:
                        job_code = f.read()
                except FileNotFoundError:
                    job_code = None

                # Create new version
                version_row = PipelineVersionRow(
                    pipeline_id=self.job_name,
                    version=next_version,
                    dag_definition={
                        "type": "spark",
                        "job_file": self.job_file,
                        "inputs": self.input_datasets,
                        "outputs": self.output_datasets,
                    },
                    dag_hash=self.job_hash,
                    transformation_code=job_code,
                    transformation_hash=self.job_hash,
                    git_commit=self.git_commit,
                    created_by="spark",
                    is_active=True,
                )

                session.add(version_row)
                session.commit()

                return next_version

        except Exception as e:
            print(f"Warning: Failed to register Spark job version for {self.job_name}: {e}")
            return 0

    def track_execution(self, spark: SparkSession, run_id: str) -> None:
        """Add execution tracking listener to Spark.

        This registers a Spark listener that will track job execution
        metrics and save them to the pipeline_executions table.

        Args:
            spark: Spark session
            run_id: Unique execution identifier (UUID)
        """
        try:
            listener = ODGSparkListener(
                job_name=self.job_name,
                run_id=run_id,
                job_hash=self.job_hash,
                input_datasets=self.input_datasets,
                output_datasets=self.output_datasets,
            )
            spark.sparkContext.addSparkListener(listener)
        except Exception as e:
            print(f"Warning: Failed to add Spark listener: {e}")

    def emit_lineage(self) -> None:
        """Emit OpenLineage event for this Spark job.

        Creates a lineage event linking input datasets to output datasets
        through this Spark job.
        """
        try:
            from odg_core.lineage.emitter import emit_lineage_event

            emit_lineage_event(
                job_name=f"spark_{self.job_name}",
                inputs=[{"namespace": "lakehouse", "name": dataset_id} for dataset_id in self.input_datasets],
                outputs=[{"namespace": "lakehouse", "name": dataset_id} for dataset_id in self.output_datasets],
                event_type="COMPLETE",
            )
        except Exception as e:
            print(f"Warning: Failed to emit lineage: {e}")


class ODGSparkListener:
    """Spark listener to capture execution metrics.

    This listener tracks Spark application lifecycle events and records
    execution metadata to the pipeline_executions table.

    Note:
        This is a simplified implementation. Full Spark listener requires
        extending org.apache.spark.scheduler.SparkListener in Scala/Java.
        For Python, we'll create execution records manually.
    """

    def __init__(
        self, job_name: str, run_id: str, job_hash: str, input_datasets: list[str], output_datasets: list[str]
    ):
        """Initialize Spark listener.

        Args:
            job_name: Job identifier
            run_id: Unique execution identifier
            job_hash: Job code hash
            input_datasets: List of input dataset IDs
            output_datasets: List of output dataset IDs
        """
        self.job_name = job_name
        self.run_id = run_id
        self.job_hash = job_hash
        self.input_datasets = input_datasets
        self.output_datasets = output_datasets
        self.start_time = datetime.now()

        # Create initial execution record
        self._create_execution_record("running")

    def _create_execution_record(self, status: str) -> None:
        """Create or update execution record in database.

        Args:
            status: Execution status (running, success, failed)
        """
        try:
            from sqlalchemy import create_engine, select
            from sqlalchemy.orm import Session

            from odg_core.db.tables import PipelineExecutionRow, PipelineVersionRow

            db_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/odg")
            engine = create_engine(db_url)

            with Session(engine) as session:
                # Get version number from job hash
                version_row = (
                    session.execute(
                        select(PipelineVersionRow).where(
                            PipelineVersionRow.pipeline_id == self.job_name,
                            PipelineVersionRow.transformation_hash == self.job_hash,
                        )
                    )
                    .scalars()
                    .first()
                )

                version = version_row.version if version_row else 0

                # Check if execution record already exists
                existing = (
                    session.execute(select(PipelineExecutionRow).where(PipelineExecutionRow.run_id == self.run_id))
                    .scalars()
                    .first()
                )

                if existing:
                    # Update existing record
                    existing.status = status
                    if status in ("success", "failed"):
                        existing.end_time = datetime.now()
                        existing.duration_ms = int((existing.end_time - existing.start_time).total_seconds() * 1000)
                else:
                    # Create new record
                    execution = PipelineExecutionRow(
                        run_id=self.run_id,
                        pipeline_id=self.job_name,
                        pipeline_version=version,
                        status=status,
                        start_time=self.start_time,
                        input_datasets=[{"id": ds} for ds in self.input_datasets],
                        output_datasets=[{"id": ds} for ds in self.output_datasets],
                    )
                    session.add(execution)

                session.commit()

        except Exception as e:
            print(f"Warning: Failed to create execution record: {e}")

    def mark_success(self, rows_processed: int | None = None, bytes_processed: int | None = None) -> None:
        """Mark execution as successful.

        Args:
            rows_processed: Number of rows processed (optional)
            bytes_processed: Number of bytes processed (optional)
        """
        try:
            from sqlalchemy import create_engine, select
            from sqlalchemy.orm import Session

            from odg_core.db.tables import PipelineExecutionRow

            db_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/odg")
            engine = create_engine(db_url)

            with Session(engine) as session:
                execution = (
                    session.execute(select(PipelineExecutionRow).where(PipelineExecutionRow.run_id == self.run_id))
                    .scalars()
                    .first()
                )

                if execution:
                    execution.status = "success"
                    execution.end_time = datetime.now()
                    execution.duration_ms = int((execution.end_time - execution.start_time).total_seconds() * 1000)
                    if rows_processed is not None:
                        execution.rows_processed = rows_processed
                    if bytes_processed is not None:
                        execution.bytes_processed = bytes_processed

                    session.commit()

        except Exception as e:
            print(f"Warning: Failed to mark execution as success: {e}")

    def mark_failure(self, error_message: str, stacktrace: str | None = None) -> None:
        """Mark execution as failed.

        Args:
            error_message: Error message
            stacktrace: Full error stacktrace (optional)
        """
        try:
            from sqlalchemy import create_engine, select
            from sqlalchemy.orm import Session

            from odg_core.db.tables import PipelineExecutionRow

            db_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/odg")
            engine = create_engine(db_url)

            with Session(engine) as session:
                execution = (
                    session.execute(select(PipelineExecutionRow).where(PipelineExecutionRow.run_id == self.run_id))
                    .scalars()
                    .first()
                )

                if execution:
                    execution.status = "failed"
                    execution.end_time = datetime.now()
                    execution.duration_ms = int((execution.end_time - execution.start_time).total_seconds() * 1000)
                    execution.error_message = error_message
                    execution.error_stacktrace = stacktrace

                    session.commit()

        except Exception as e:
            print(f"Warning: Failed to mark execution as failed: {e}")
