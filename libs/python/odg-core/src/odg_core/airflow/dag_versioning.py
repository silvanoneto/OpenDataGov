"""Airflow DAG versioning and execution tracking.

Provides automatic versioning of Airflow DAGs based on task structure and
dependencies, with execution tracking for auditability and reproducibility.
"""

from __future__ import annotations

import hashlib
import json
import os
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from airflow import DAG


class VersionedDAG:
    """Wrapper for Airflow DAG with automatic versioning.

    Computes a hash of the DAG structure (tasks, dependencies, schedule)
    and registers each version in the pipeline_versions table.

    Example:
        >>> from airflow import DAG
        >>> from odg_core.airflow.dag_versioning import VersionedDAG
        >>>
        >>> dag = DAG('transform_sales', start_date=datetime(2026, 1, 1))
        >>> # ... add tasks to DAG ...
        >>>
        >>> versioned_dag = VersionedDAG(dag, git_commit=os.getenv('GIT_COMMIT'))
        >>> version = versioned_dag.register_version()
        >>> print(f"DAG version: {version}")
    """

    def __init__(self, dag: DAG, git_commit: str | None = None):
        """Initialize versioned DAG.

        Args:
            dag: Airflow DAG instance
            git_commit: Git commit SHA (optional)
        """
        self.dag = dag
        self.git_commit = git_commit
        self.version_hash = self._compute_version_hash()

    def _compute_version_hash(self) -> str:
        """Compute SHA256 hash of DAG structure.

        The hash includes:
        - DAG ID
        - Task IDs and types
        - Task dependencies (upstream/downstream)
        - Schedule interval

        Returns:
            12-character hash of the DAG structure
        """
        dag_structure = {
            "dag_id": self.dag.dag_id,
            "tasks": sorted(
                [
                    {
                        "task_id": task.task_id,
                        "task_type": task.__class__.__name__,
                        "upstream_task_ids": sorted(list(task.upstream_task_ids)),
                    }
                    for task in self.dag.tasks
                ],
                key=lambda x: x["task_id"],
            ),
            "schedule_interval": str(self.dag.schedule_interval),
        }

        dag_json = json.dumps(dag_structure, sort_keys=True)
        full_hash = hashlib.sha256(dag_json.encode()).hexdigest()
        return full_hash[:12]  # Return first 12 characters

    def register_version(self) -> int:
        """Register this DAG version in the database.

        Creates a new entry in the pipeline_versions table if the DAG hash
        doesn't already exist. Returns the version number.

        Returns:
            Version number (sequential integer)

        Note:
            This method requires a database connection. In production,
            this should be called during DAG initialization.
        """
        try:
            from sqlalchemy import create_engine, func, select
            from sqlalchemy.orm import Session

            from odg_core.db.tables import PipelineVersionRow

            # Get database URL from environment
            db_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/odg")
            engine = create_engine(db_url)

            with Session(engine) as session:
                # Check if this exact DAG hash already exists
                existing = (
                    session.execute(
                        select(PipelineVersionRow).where(
                            PipelineVersionRow.pipeline_id == self.dag.dag_id,
                            PipelineVersionRow.dag_hash == self.version_hash,
                        )
                    )
                    .scalars()
                    .first()
                )

                if existing:
                    return existing.version

                # Get next version number
                last_version = session.execute(
                    select(func.max(PipelineVersionRow.version)).where(
                        PipelineVersionRow.pipeline_id == self.dag.dag_id
                    )
                ).scalar()

                next_version = (last_version or 0) + 1

                # Create new version
                version_row = PipelineVersionRow(
                    pipeline_id=self.dag.dag_id,
                    version=next_version,
                    dag_definition={
                        "dag_id": self.dag.dag_id,
                        "tasks": [t.task_id for t in self.dag.tasks],
                        "schedule": str(self.dag.schedule_interval),
                        "task_count": len(self.dag.tasks),
                    },
                    dag_hash=self.version_hash,
                    git_commit=self.git_commit,
                    created_by="airflow",
                    is_active=True,
                )

                session.add(version_row)
                session.commit()

                return next_version

        except Exception as e:
            # Log error but don't fail DAG initialization
            print(f"Warning: Failed to register DAG version for {self.dag.dag_id}: {e}")
            return 0


class VersionedDAGRunHook:
    """Airflow hook to track DAG executions.

    This hook captures DAG run success/failure events and records them
    in the pipeline_executions table for auditability.

    Usage:
        Add this to your Airflow configuration:

        [core]
        dagrun_success_callback = odg_core.airflow.dag_versioning:on_dagrun_success
        dagrun_failure_callback = odg_core.airflow.dag_versioning:on_dagrun_failure
    """

    @staticmethod
    def _get_dag_version(dag_id: str, dag_hash: str) -> int:
        """Get DAG version from database.

        Args:
            dag_id: DAG identifier
            dag_hash: DAG structure hash

        Returns:
            Version number, or 0 if not found
        """
        try:
            from sqlalchemy import create_engine, select
            from sqlalchemy.orm import Session

            from odg_core.db.tables import PipelineVersionRow

            db_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/odg")
            engine = create_engine(db_url)

            with Session(engine) as session:
                version_row = (
                    session.execute(
                        select(PipelineVersionRow).where(
                            PipelineVersionRow.pipeline_id == dag_id, PipelineVersionRow.dag_hash == dag_hash
                        )
                    )
                    .scalars()
                    .first()
                )

                return version_row.version if version_row else 0

        except Exception:
            return 0

    @staticmethod
    def on_dagrun_success(context: dict[str, Any], *args: Any, **kwargs: Any) -> None:
        """Called when a DAG run completes successfully.

        Args:
            context: Airflow context dictionary
        """
        try:
            from sqlalchemy import create_engine
            from sqlalchemy.orm import Session

            from odg_core.db.tables import PipelineExecutionRow

            dag_run = context["dag_run"]
            dag = context["dag"]

            # Compute DAG hash to get version
            versioned_dag = VersionedDAG(dag)
            version = VersionedDAGRunHook._get_dag_version(dag.dag_id, versioned_dag.version_hash)

            db_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/odg")
            engine = create_engine(db_url)

            with Session(engine) as session:
                execution = PipelineExecutionRow(
                    run_id=dag_run.run_id,
                    pipeline_id=dag.dag_id,
                    pipeline_version=version,
                    status="success",
                    start_time=dag_run.start_date,
                    end_time=dag_run.end_date,
                    duration_ms=int((dag_run.end_date - dag_run.start_date).total_seconds() * 1000)
                    if dag_run.end_date and dag_run.start_date
                    else None,
                )

                session.add(execution)
                session.commit()

        except Exception as e:
            print(f"Warning: Failed to record DAG run success: {e}")

    @staticmethod
    def on_dagrun_failure(context: dict[str, Any], *args: Any, **kwargs: Any) -> None:
        """Called when a DAG run fails.

        Args:
            context: Airflow context dictionary
        """
        try:
            from sqlalchemy import create_engine
            from sqlalchemy.orm import Session

            from odg_core.db.tables import PipelineExecutionRow

            dag_run = context["dag_run"]
            dag = context["dag"]
            exception = context.get("exception")

            # Compute DAG hash to get version
            versioned_dag = VersionedDAG(dag)
            version = VersionedDAGRunHook._get_dag_version(dag.dag_id, versioned_dag.version_hash)

            db_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/odg")
            engine = create_engine(db_url)

            with Session(engine) as session:
                execution = PipelineExecutionRow(
                    run_id=dag_run.run_id,
                    pipeline_id=dag.dag_id,
                    pipeline_version=version,
                    status="failed",
                    start_time=dag_run.start_date,
                    end_time=dag_run.end_date,
                    duration_ms=int((dag_run.end_date - dag_run.start_date).total_seconds() * 1000)
                    if dag_run.end_date and dag_run.start_date
                    else None,
                    error_message=str(exception) if exception else None,
                )

                session.add(execution)
                session.commit()

        except Exception as e:
            print(f"Warning: Failed to record DAG run failure: {e}")


# Export callback functions for Airflow configuration
on_dagrun_success = VersionedDAGRunHook.on_dagrun_success
on_dagrun_failure = VersionedDAGRunHook.on_dagrun_failure
