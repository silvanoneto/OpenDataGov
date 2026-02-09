"""Coverage tests for spark, polars, duckdb, airflow versioning modules."""

from __future__ import annotations

import hashlib
import os
import tempfile
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

# ── VersionedSparkJob ─────────────────────────────────────────


class TestVersionedSparkJob:
    def test_init_and_hash(self) -> None:
        from odg_core.spark.job_versioning import VersionedSparkJob

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("# spark job\ndf = spark.read.parquet('input')\n")
            f.flush()
            job = VersionedSparkJob(
                job_name="test_job",
                job_file=f.name,
                input_datasets=["bronze/sales"],
                output_datasets=["silver/sales"],
            )
        os.unlink(f.name)

        assert job.job_name == "test_job"
        assert len(job.job_hash) == 12
        assert job.input_datasets == ["bronze/sales"]
        assert job.output_datasets == ["silver/sales"]

    def test_hash_file_not_found_uses_name(self) -> None:
        from odg_core.spark.job_versioning import VersionedSparkJob

        job = VersionedSparkJob(
            job_name="missing_job",
            job_file="/nonexistent/file.py",
            input_datasets=[],
            output_datasets=[],
        )
        expected = hashlib.sha256(b"missing_job").hexdigest()[:12]
        assert job.job_hash == expected

    @patch("sqlalchemy.create_engine")
    def test_register_version_existing(self, mock_engine: MagicMock) -> None:
        from odg_core.spark.job_versioning import VersionedSparkJob

        job = VersionedSparkJob(
            job_name="test_job",
            job_file="/nonexistent.py",
            input_datasets=[],
            output_datasets=[],
        )

        mock_session = MagicMock()
        mock_existing = MagicMock()
        mock_existing.version = 5
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_session.execute.return_value.scalars.return_value.first.return_value = mock_existing

        with patch("sqlalchemy.orm.Session", return_value=mock_session):
            version = job.register_version()

        assert version == 5

    def test_register_version_db_error(self) -> None:
        from odg_core.spark.job_versioning import VersionedSparkJob

        job = VersionedSparkJob(
            job_name="test_job",
            job_file="/nonexistent.py",
            input_datasets=[],
            output_datasets=[],
        )

        with patch("sqlalchemy.create_engine", side_effect=Exception("DB Error")):
            version = job.register_version()
        assert version == 0

    def test_track_execution(self) -> None:
        from odg_core.spark.job_versioning import VersionedSparkJob

        job = VersionedSparkJob(
            job_name="test_job",
            job_file="/nonexistent.py",
            input_datasets=["bronze/sales"],
            output_datasets=["silver/sales"],
        )

        mock_spark = MagicMock()
        job.track_execution(mock_spark, "run-123")
        # Should not raise even if listener creation fails internally

    def test_emit_lineage(self) -> None:
        from odg_core.spark.job_versioning import VersionedSparkJob

        job = VersionedSparkJob(
            job_name="test_job",
            job_file="/nonexistent.py",
            input_datasets=["bronze/sales"],
            output_datasets=["silver/sales"],
        )

        with patch("odg_core.lineage.emitter.emit_lineage_event") as mock_emit:
            job.emit_lineage()
            mock_emit.assert_called_once()

    def test_emit_lineage_error(self) -> None:
        from odg_core.spark.job_versioning import VersionedSparkJob

        job = VersionedSparkJob(
            job_name="test_job",
            job_file="/nonexistent.py",
            input_datasets=[],
            output_datasets=[],
        )

        with patch("odg_core.lineage.emitter.emit_lineage_event", side_effect=Exception("fail")):
            job.emit_lineage()  # Should not raise


# ── ODGSparkListener ──────────────────────────────────────────


class TestODGSparkListener:
    def test_init_creates_record(self) -> None:
        from odg_core.spark.job_versioning import ODGSparkListener

        with patch.object(ODGSparkListener, "_create_execution_record") as mock_create:
            ODGSparkListener(
                job_name="test",
                run_id="run-1",
                job_hash="abc123",
                input_datasets=["bronze/sales"],
                output_datasets=["silver/sales"],
            )
            mock_create.assert_called_once_with("running")

    def test_mark_success(self) -> None:
        from odg_core.spark.job_versioning import ODGSparkListener

        with patch.object(ODGSparkListener, "_create_execution_record"):
            listener = ODGSparkListener(
                job_name="test", run_id="run-1", job_hash="abc", input_datasets=[], output_datasets=[]
            )

        # mark_success catches all errors internally
        listener.mark_success(rows_processed=100, bytes_processed=1024)

    def test_mark_failure(self) -> None:
        from odg_core.spark.job_versioning import ODGSparkListener

        with patch.object(ODGSparkListener, "_create_execution_record"):
            listener = ODGSparkListener(
                job_name="test", run_id="run-1", job_hash="abc", input_datasets=[], output_datasets=[]
            )

        listener.mark_failure("Some error", stacktrace="traceback...")


# ── VersionedPolarsJob ────────────────────────────────────────


class TestVersionedPolarsJob:
    def test_init(self) -> None:
        from odg_core.polars.versioned_pipeline import VersionedPolarsJob

        mock_lazy = MagicMock()
        mock_lazy.explain.return_value = "FILTER col > 0"

        job = VersionedPolarsJob(
            job_name="aggregate_sales",
            lazy_plan=mock_lazy,
            input_datasets=["silver/sales"],
        )
        assert job.job_name == "aggregate_sales"
        assert len(job.plan_hash) == 12
        assert job.input_datasets == ["silver/sales"]

    def test_plan_hash_fallback(self) -> None:
        from odg_core.polars.versioned_pipeline import VersionedPolarsJob

        mock_lazy = MagicMock()
        mock_lazy.explain.side_effect = Exception("No plan")

        job = VersionedPolarsJob(job_name="fallback_job", lazy_plan=mock_lazy)
        expected = hashlib.sha256(b"fallback_job").hexdigest()[:12]
        assert job.plan_hash == expected

    def test_register_version_db_error(self) -> None:
        from odg_core.polars.versioned_pipeline import VersionedPolarsJob

        mock_lazy = MagicMock()
        mock_lazy.explain.return_value = "PLAN"

        job = VersionedPolarsJob(job_name="test", lazy_plan=mock_lazy)

        with patch("sqlalchemy.create_engine", side_effect=Exception("DB Error")):
            version = job.register_version()
        assert version == 0

    def test_execute_and_track_success(self) -> None:
        from odg_core.polars.versioned_pipeline import VersionedPolarsJob

        mock_lazy = MagicMock()
        mock_lazy.explain.return_value = "PLAN"
        mock_df = MagicMock()
        mock_df.__len__ = MagicMock(return_value=10)
        mock_lazy.collect.return_value = mock_df

        job = VersionedPolarsJob(job_name="test", lazy_plan=mock_lazy, input_datasets=["silver/data"])

        with patch.object(job, "_track_execution"), patch("odg_core.lineage.emitter.emit_lineage_event"):
            result = job.execute_and_track("/tmp/output.parquet")
        assert result is mock_df

    def test_execute_and_track_failure(self) -> None:
        from odg_core.polars.versioned_pipeline import VersionedPolarsJob

        mock_lazy = MagicMock()
        mock_lazy.explain.return_value = "PLAN"
        mock_lazy.collect.side_effect = RuntimeError("OOM")

        job = VersionedPolarsJob(job_name="test", lazy_plan=mock_lazy)

        with patch.object(job, "_track_execution"), pytest.raises(RuntimeError, match="OOM"):
            job.execute_and_track("/tmp/output.parquet")

    def test_track_execution_db_error(self) -> None:
        from odg_core.polars.versioned_pipeline import VersionedPolarsJob

        mock_lazy = MagicMock()
        mock_lazy.explain.return_value = "PLAN"

        job = VersionedPolarsJob(job_name="test", lazy_plan=mock_lazy)

        # Should not raise
        job._track_execution(run_id="r1", status="success", start_time=datetime.now(UTC), rows_processed=10)

    def test_get_next_version_db_error(self) -> None:
        from odg_core.polars.versioned_pipeline import VersionedPolarsJob

        mock_lazy = MagicMock()
        mock_lazy.explain.return_value = "PLAN"

        job = VersionedPolarsJob(job_name="test", lazy_plan=mock_lazy)
        # _get_next_version returns 1 on error
        version = job._get_next_version()
        assert version == 1

    def test_create_versioned_pipeline(self) -> None:
        from odg_core.polars.versioned_pipeline import create_versioned_pipeline

        mock_lazy = MagicMock()
        mock_lazy.explain.return_value = "PLAN"

        job = create_versioned_pipeline("my_job", mock_lazy)
        assert job.job_name == "my_job"


# ── VersionedDuckDBJob ────────────────────────────────────────


class TestVersionedDuckDBJob:
    def test_init(self) -> None:
        from odg_core.duckdb.versioned_query import VersionedDuckDBJob

        job = VersionedDuckDBJob(
            job_name="aggregate_orders",
            sql_query="SELECT * FROM orders",
            input_tables=["orders"],
            output_table="order_summary",
        )
        assert job.job_name == "aggregate_orders"
        assert len(job.query_hash) == 12
        assert job.sql_query == "SELECT * FROM orders"

    def test_query_hash_normalization(self) -> None:
        from odg_core.duckdb.versioned_query import VersionedDuckDBJob

        job1 = VersionedDuckDBJob(
            job_name="test", sql_query="  SELECT *   FROM  orders  ", input_tables=["orders"], output_table="out"
        )
        job2 = VersionedDuckDBJob(
            job_name="test", sql_query="SELECT * FROM orders", input_tables=["orders"], output_table="out"
        )
        assert job1.query_hash == job2.query_hash

    def test_register_version_db_error(self) -> None:
        from odg_core.duckdb.versioned_query import VersionedDuckDBJob

        job = VersionedDuckDBJob(job_name="test", sql_query="SELECT 1", input_tables=[], output_table="out")

        with patch("sqlalchemy.create_engine", side_effect=Exception("DB Error")):
            version = job.register_version()
        assert version == 0

    def test_execute_success(self) -> None:
        from odg_core.duckdb.versioned_query import VersionedDuckDBJob

        job = VersionedDuckDBJob(
            job_name="test",
            sql_query="SELECT 1 AS id",
            input_tables=["orders"],
            output_table="out",
        )

        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.__len__ = MagicMock(return_value=5)
        mock_conn.execute.return_value.df.return_value = mock_result

        mock_iceberg = MagicMock()
        mock_iceberg.get_snapshot_id.return_value = "snap_123"

        with (
            patch.object(job, "_track_execution"),
            patch("odg_core.lineage.emitter.emit_lineage_event"),
            patch("odg_core.storage.iceberg_catalog.IcebergCatalog", return_value=mock_iceberg),
        ):
            result = job.execute(mock_conn)

        assert result is mock_result

    def test_execute_failure(self) -> None:
        from odg_core.duckdb.versioned_query import VersionedDuckDBJob

        job = VersionedDuckDBJob(
            job_name="test",
            sql_query="INVALID SQL",
            input_tables=["orders"],
            output_table="out",
        )

        mock_conn = MagicMock()
        mock_conn.execute.side_effect = RuntimeError("SQL Error")

        mock_iceberg = MagicMock()

        with (
            patch.object(job, "_track_execution"),
            patch("odg_core.storage.iceberg_catalog.IcebergCatalog", return_value=mock_iceberg),
            pytest.raises(RuntimeError, match="SQL Error"),
        ):
            job.execute(mock_conn)

    def test_execute_snapshot_error_continues(self) -> None:
        from odg_core.duckdb.versioned_query import VersionedDuckDBJob

        job = VersionedDuckDBJob(
            job_name="test",
            sql_query="SELECT 1",
            input_tables=["orders"],
            output_table="out",
        )

        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.__len__ = MagicMock(return_value=1)
        mock_conn.execute.return_value.df.return_value = mock_result

        mock_iceberg = MagicMock()
        mock_iceberg.get_snapshot_id.side_effect = Exception("No snapshot")

        with (
            patch.object(job, "_track_execution"),
            patch("odg_core.lineage.emitter.emit_lineage_event"),
            patch("odg_core.storage.iceberg_catalog.IcebergCatalog", return_value=mock_iceberg),
        ):
            result = job.execute(mock_conn)

        assert result is mock_result

    def test_track_execution_db_error(self) -> None:
        from odg_core.duckdb.versioned_query import VersionedDuckDBJob

        job = VersionedDuckDBJob(job_name="test", sql_query="SELECT 1", input_tables=[], output_table="out")
        # Should not raise
        job._track_execution(run_id="r1", status="success", rows_processed=10)

    def test_create_versioned_query(self) -> None:
        from odg_core.duckdb.versioned_query import create_versioned_query

        job = create_versioned_query("my_job", "SELECT 1", ["t"], "out")
        assert job.job_name == "my_job"


# ── VersionedDAG ──────────────────────────────────────────────


class TestVersionedDAG:
    def _make_mock_dag(self, dag_id: str = "test_dag") -> MagicMock:
        dag = MagicMock()
        dag.dag_id = dag_id
        dag.schedule_interval = "@daily"

        task1 = MagicMock()
        task1.task_id = "extract"
        task1.__class__.__name__ = "PythonOperator"
        task1.upstream_task_ids = set()

        task2 = MagicMock()
        task2.task_id = "transform"
        task2.__class__.__name__ = "SparkSubmitOperator"
        task2.upstream_task_ids = {"extract"}

        dag.tasks = [task1, task2]
        return dag

    def test_version_hash(self) -> None:
        from odg_core.airflow.dag_versioning import VersionedDAG

        dag = self._make_mock_dag()
        versioned = VersionedDAG(dag)
        assert len(versioned.version_hash) == 12

    def test_same_dag_same_hash(self) -> None:
        from odg_core.airflow.dag_versioning import VersionedDAG

        dag1 = self._make_mock_dag()
        dag2 = self._make_mock_dag()
        v1 = VersionedDAG(dag1)
        v2 = VersionedDAG(dag2)
        assert v1.version_hash == v2.version_hash

    def test_different_dag_different_hash(self) -> None:
        from odg_core.airflow.dag_versioning import VersionedDAG

        dag1 = self._make_mock_dag("dag_a")
        dag2 = self._make_mock_dag("dag_b")
        v1 = VersionedDAG(dag1)
        v2 = VersionedDAG(dag2)
        assert v1.version_hash != v2.version_hash

    def test_register_version_db_error(self) -> None:
        from odg_core.airflow.dag_versioning import VersionedDAG

        dag = self._make_mock_dag()
        versioned = VersionedDAG(dag)

        with patch("sqlalchemy.create_engine", side_effect=Exception("DB Error")):
            version = versioned.register_version()
        assert version == 0


# ── VersionedDAGRunHook ───────────────────────────────────────


class TestVersionedDAGRunHook:
    def test_get_dag_version_db_error(self) -> None:
        from odg_core.airflow.dag_versioning import VersionedDAGRunHook

        version = VersionedDAGRunHook._get_dag_version("test_dag", "hash123")
        assert version == 0

    def test_on_dagrun_success(self) -> None:
        from odg_core.airflow.dag_versioning import VersionedDAGRunHook

        mock_dag = MagicMock()
        mock_dag.dag_id = "test_dag"
        mock_dag.tasks = []
        mock_dag.schedule_interval = "@daily"

        mock_dag_run = MagicMock()
        mock_dag_run.run_id = "run-1"
        mock_dag_run.start_date = datetime(2026, 1, 1)
        mock_dag_run.end_date = datetime(2026, 1, 1, 0, 5)

        context = {"dag_run": mock_dag_run, "dag": mock_dag}

        # Should not raise even if DB fails
        VersionedDAGRunHook.on_dagrun_success(context)

    def test_on_dagrun_failure(self) -> None:
        from odg_core.airflow.dag_versioning import VersionedDAGRunHook

        mock_dag = MagicMock()
        mock_dag.dag_id = "test_dag"
        mock_dag.tasks = []
        mock_dag.schedule_interval = "@daily"

        mock_dag_run = MagicMock()
        mock_dag_run.run_id = "run-1"
        mock_dag_run.start_date = datetime(2026, 1, 1)
        mock_dag_run.end_date = datetime(2026, 1, 1, 0, 5)

        context = {"dag_run": mock_dag_run, "dag": mock_dag, "exception": ValueError("Task failed")}

        # Should not raise
        VersionedDAGRunHook.on_dagrun_failure(context)

    def test_on_dagrun_success_no_end_date(self) -> None:
        from odg_core.airflow.dag_versioning import VersionedDAGRunHook

        mock_dag = MagicMock()
        mock_dag.dag_id = "test_dag"
        mock_dag.tasks = []
        mock_dag.schedule_interval = "@daily"

        mock_dag_run = MagicMock()
        mock_dag_run.run_id = "run-1"
        mock_dag_run.start_date = datetime(2026, 1, 1)
        mock_dag_run.end_date = None

        context = {"dag_run": mock_dag_run, "dag": mock_dag}
        VersionedDAGRunHook.on_dagrun_success(context)


# ── Module-level exports ──────────────────────────────────────


class TestModuleExports:
    def test_on_dagrun_callbacks(self) -> None:
        from odg_core.airflow.dag_versioning import on_dagrun_failure, on_dagrun_success

        assert callable(on_dagrun_success)
        assert callable(on_dagrun_failure)
