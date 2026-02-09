"""Deep tests for DB interaction paths in data processing versioning modules.

Covers uncovered lines in:
- spark/job_versioning.py  (lines 124-158, 254-295, 316-332, 353-367)
- polars/versioned_pipeline.py  (lines 93-98, 121-167, 256-289)
- duckdb/versioned_query.py  (lines 99-143, 236-266)
- airflow/dag_versioning.py  (lines 102-146, 188-199, 227-241, 270-285)
"""

from __future__ import annotations

import os
import tempfile
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_session_mock() -> MagicMock:
    """Build a MagicMock that behaves as a SQLAlchemy Session context manager."""
    session = MagicMock()
    session.__enter__ = MagicMock(return_value=session)
    session.__exit__ = MagicMock(return_value=False)
    return session


def _result_returning(row: object) -> MagicMock:
    """Build a mock execute() result whose .scalars().first() returns *row*."""
    result = MagicMock()
    result.scalars.return_value.first.return_value = row
    return result


def _make_airflow_dag(dag_id: str = "test_dag", schedule: str = "@daily") -> MagicMock:
    """Build a mock Airflow DAG with one task."""
    task = MagicMock()
    task.task_id = "task_1"
    task.__class__.__name__ = "PythonOperator"
    task.upstream_task_ids = set()

    dag = MagicMock()
    dag.dag_id = dag_id
    dag.tasks = [task]
    dag.schedule_interval = schedule
    return dag


def _make_airflow_dag_run(
    run_id: str = "run-abc",
    start: datetime | None = None,
    end: datetime | None = None,
) -> MagicMock:
    """Build a mock Airflow DagRun."""
    dag_run = MagicMock()
    dag_run.run_id = run_id
    dag_run.start_date = start or datetime(2026, 1, 1, tzinfo=UTC)
    dag_run.end_date = end or datetime(2026, 1, 1, 0, 5, tzinfo=UTC)
    return dag_run


# Common set of patches needed for all DB-interacting methods.
# The code does local imports:
#   from sqlalchemy import create_engine, select, func
#   from sqlalchemy.orm import Session
#   from odg_core.db.tables import PipelineVersionRow, PipelineExecutionRow
#
# We must patch at source (sqlalchemy.* and odg_core.db.tables.*) so the
# local imports pick up our mocks. We must also patch `select` and `func`
# because the real `select()` chokes on a MagicMock PipelineVersionRow.

_PATCH_CREATE_ENGINE = "sqlalchemy.create_engine"
_PATCH_SESSION = "sqlalchemy.orm.Session"
_PATCH_SELECT = "sqlalchemy.select"
_PATCH_FUNC = "sqlalchemy.func"
_PATCH_VERSION_ROW = "odg_core.db.tables.PipelineVersionRow"
_PATCH_EXECUTION_ROW = "odg_core.db.tables.PipelineExecutionRow"


# ===================================================================
# 1. Spark  --  VersionedSparkJob.register_version (new version path)
# ===================================================================


class TestSparkRegisterVersionNewVersion:
    """Cover lines 124-158: existing hash NOT found, creates PipelineVersionRow."""

    @patch(_PATCH_VERSION_ROW)
    @patch(_PATCH_FUNC)
    @patch(_PATCH_SELECT)
    @patch(_PATCH_SESSION)
    @patch(_PATCH_CREATE_ENGINE)
    def test_creates_new_version_when_hash_not_found(
        self, mock_create_engine, mock_session_cls, mock_select, mock_func, mock_version_row
    ):
        mock_engine = MagicMock()
        mock_create_engine.return_value = mock_engine

        session = _make_session_mock()
        mock_session_cls.return_value = session

        # First execute -> scalars().first() returns None (no existing row)
        # Second execute -> .scalar() returns 3 (last version)
        session.execute.side_effect = [
            _result_returning(None),  # existing hash lookup
            MagicMock(scalar=MagicMock(return_value=3)),  # func.max
        ]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("# spark job code\nprint('hello')\n")
            job_file = f.name

        try:
            from odg_core.spark.job_versioning import VersionedSparkJob

            job = VersionedSparkJob(
                job_name="transform_sales",
                job_file=job_file,
                input_datasets=["bronze/sales"],
                output_datasets=["silver/sales"],
                git_commit="abc123",
            )
            version = job.register_version()

            assert version == 4
            session.add.assert_called_once()
            session.commit.assert_called_once()

            call_kwargs = mock_version_row.call_args[1]
            assert call_kwargs["pipeline_id"] == "transform_sales"
            assert call_kwargs["version"] == 4
            assert call_kwargs["created_by"] == "spark"
            assert call_kwargs["is_active"] is True
        finally:
            os.unlink(job_file)

    @patch(_PATCH_VERSION_ROW)
    @patch(_PATCH_FUNC)
    @patch(_PATCH_SELECT)
    @patch(_PATCH_SESSION)
    @patch(_PATCH_CREATE_ENGINE)
    def test_new_version_when_no_previous_versions_exist(
        self, mock_create_engine, mock_session_cls, mock_select, mock_func, mock_version_row
    ):
        """last_version is None -> next_version should be 1."""
        mock_create_engine.return_value = MagicMock()
        session = _make_session_mock()
        mock_session_cls.return_value = session

        session.execute.side_effect = [
            _result_returning(None),  # no existing hash
            MagicMock(scalar=MagicMock(return_value=None)),  # no previous versions
        ]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("# brand new job\n")
            job_file = f.name

        try:
            from odg_core.spark.job_versioning import VersionedSparkJob

            job = VersionedSparkJob(
                job_name="new_job",
                job_file=job_file,
                input_datasets=["raw/events"],
                output_datasets=["bronze/events"],
            )
            version = job.register_version()
            assert version == 1
            session.add.assert_called_once()
            session.commit.assert_called_once()
        finally:
            os.unlink(job_file)

    @patch(_PATCH_VERSION_ROW)
    @patch(_PATCH_FUNC)
    @patch(_PATCH_SELECT)
    @patch(_PATCH_SESSION)
    @patch(_PATCH_CREATE_ENGINE)
    def test_job_file_not_found_during_register(
        self, mock_create_engine, mock_session_cls, mock_select, mock_func, mock_version_row
    ):
        """When job_file doesn't exist during register_version, job_code=None."""
        mock_create_engine.return_value = MagicMock()
        session = _make_session_mock()
        mock_session_cls.return_value = session

        session.execute.side_effect = [
            _result_returning(None),
            MagicMock(scalar=MagicMock(return_value=0)),
        ]

        from odg_core.spark.job_versioning import VersionedSparkJob

        job = VersionedSparkJob(
            job_name="missing_file_job",
            job_file="/nonexistent/path/job.py",
            input_datasets=[],
            output_datasets=[],
        )
        version = job.register_version()
        assert version == 1

        call_kwargs = mock_version_row.call_args[1]
        assert call_kwargs["transformation_code"] is None


# ===================================================================
# 2. Spark  --  ODGSparkListener._create_execution_record (lines 254-295)
# ===================================================================


class TestSparkCreateExecutionRecord:
    """Cover lines 254-295: creating new and updating existing PipelineExecutionRow."""

    @patch(_PATCH_EXECUTION_ROW)
    @patch(_PATCH_VERSION_ROW)
    @patch(_PATCH_SELECT)
    @patch(_PATCH_SESSION)
    @patch(_PATCH_CREATE_ENGINE)
    def test_creates_new_execution_record(
        self, mock_create_engine, mock_session_cls, mock_select, mock_version_row, mock_execution_row
    ):
        mock_create_engine.return_value = MagicMock()
        session = _make_session_mock()
        mock_session_cls.return_value = session

        # Version row exists with version=2
        version_row = MagicMock()
        version_row.version = 2

        # First call: version lookup -> found
        # Second call: existing execution lookup -> not found
        session.execute.side_effect = [
            _result_returning(version_row),  # version lookup
            _result_returning(None),  # no existing execution
        ]

        from odg_core.spark.job_versioning import ODGSparkListener

        ODGSparkListener(
            job_name="etl_job",
            run_id="run-123",
            job_hash="abc123def456",
            input_datasets=["bronze/data"],
            output_datasets=["silver/data"],
        )

        # __init__ calls _create_execution_record("running")
        session.add.assert_called_once()
        session.commit.assert_called_once()

        call_kwargs = mock_execution_row.call_args[1]
        assert call_kwargs["run_id"] == "run-123"
        assert call_kwargs["pipeline_id"] == "etl_job"
        assert call_kwargs["pipeline_version"] == 2
        assert call_kwargs["status"] == "running"

    @patch(_PATCH_EXECUTION_ROW)
    @patch(_PATCH_VERSION_ROW)
    @patch(_PATCH_SELECT)
    @patch(_PATCH_SESSION)
    @patch(_PATCH_CREATE_ENGINE)
    def test_updates_existing_execution_record(
        self, mock_create_engine, mock_session_cls, mock_select, mock_version_row, mock_execution_row
    ):
        mock_create_engine.return_value = MagicMock()
        session = _make_session_mock()
        mock_session_cls.return_value = session

        version_row = MagicMock()
        version_row.version = 1

        existing_execution = MagicMock()
        existing_execution.start_time = datetime(2026, 1, 1, tzinfo=UTC)

        # version lookup -> found, execution lookup -> found
        session.execute.side_effect = [
            _result_returning(version_row),
            _result_returning(existing_execution),
        ]

        from odg_core.spark.job_versioning import ODGSparkListener

        ODGSparkListener(
            job_name="etl_job",
            run_id="run-456",
            job_hash="abc",
            input_datasets=[],
            output_datasets=[],
        )

        # Since existing was found, it should update status, not add new row
        assert existing_execution.status == "running"
        session.add.assert_not_called()
        session.commit.assert_called_once()

    @patch(_PATCH_EXECUTION_ROW)
    @patch(_PATCH_VERSION_ROW)
    @patch(_PATCH_SELECT)
    @patch(_PATCH_SESSION)
    @patch(_PATCH_CREATE_ENGINE)
    def test_version_row_not_found_defaults_to_zero(
        self, mock_create_engine, mock_session_cls, mock_select, mock_version_row, mock_execution_row
    ):
        mock_create_engine.return_value = MagicMock()
        session = _make_session_mock()
        mock_session_cls.return_value = session

        session.execute.side_effect = [
            _result_returning(None),  # version not found
            _result_returning(None),  # no existing execution
        ]

        from odg_core.spark.job_versioning import ODGSparkListener

        ODGSparkListener(
            job_name="unknown_job",
            run_id="run-789",
            job_hash="xyz",
            input_datasets=[],
            output_datasets=[],
        )

        call_kwargs = mock_execution_row.call_args[1]
        assert call_kwargs["pipeline_version"] == 0


# ===================================================================
# 3. Spark  --  ODGSparkListener.mark_success (lines 316-332)
# ===================================================================


class TestSparkMarkSuccess:
    """Cover lines 316-332: updates execution status to 'success'."""

    @patch(_PATCH_EXECUTION_ROW)
    @patch(_PATCH_VERSION_ROW)
    @patch(_PATCH_SELECT)
    @patch(_PATCH_SESSION)
    @patch(_PATCH_CREATE_ENGINE)
    def test_mark_success_updates_execution(
        self, mock_create_engine, mock_session_cls, mock_select, mock_version_row, mock_execution_row
    ):
        mock_create_engine.return_value = MagicMock()
        session = _make_session_mock()
        mock_session_cls.return_value = session

        # First: __init__ calls _create_execution_record
        session.execute.side_effect = [
            _result_returning(MagicMock(version=1)),  # version lookup
            _result_returning(None),  # no existing execution
        ]

        from odg_core.spark.job_versioning import ODGSparkListener

        listener = ODGSparkListener(
            job_name="job_1",
            run_id="run-success",
            job_hash="hash1",
            input_datasets=["in"],
            output_datasets=["out"],
        )

        # Reset mocks for mark_success call and re-establish context manager
        session.reset_mock()
        session.execute.side_effect = None
        session.__enter__ = MagicMock(return_value=session)
        session.__exit__ = MagicMock(return_value=False)
        mock_create_engine.reset_mock()

        execution_row = MagicMock()
        execution_row.start_time = datetime(2026, 1, 1)
        session.execute.return_value = _result_returning(execution_row)

        listener.mark_success(rows_processed=1000, bytes_processed=2048)

        assert execution_row.status == "success"
        assert execution_row.rows_processed == 1000
        assert execution_row.bytes_processed == 2048
        assert execution_row.end_time is not None
        assert execution_row.duration_ms is not None
        session.commit.assert_called_once()

    @patch(_PATCH_EXECUTION_ROW)
    @patch(_PATCH_VERSION_ROW)
    @patch(_PATCH_SELECT)
    @patch(_PATCH_SESSION)
    @patch(_PATCH_CREATE_ENGINE)
    def test_mark_success_no_execution_found(
        self, mock_create_engine, mock_session_cls, mock_select, mock_version_row, mock_execution_row
    ):
        """When execution row is not found, commit should NOT be called."""
        mock_create_engine.return_value = MagicMock()
        session = _make_session_mock()
        mock_session_cls.return_value = session

        session.execute.side_effect = [
            _result_returning(MagicMock(version=1)),
            _result_returning(None),
        ]

        from odg_core.spark.job_versioning import ODGSparkListener

        listener = ODGSparkListener(
            job_name="job_x",
            run_id="run-no-exec",
            job_hash="h",
            input_datasets=[],
            output_datasets=[],
        )

        session.reset_mock()
        session.execute.side_effect = None
        session.__enter__ = MagicMock(return_value=session)
        session.__exit__ = MagicMock(return_value=False)
        session.execute.return_value = _result_returning(None)

        listener.mark_success()
        session.commit.assert_not_called()

    @patch(_PATCH_EXECUTION_ROW)
    @patch(_PATCH_VERSION_ROW)
    @patch(_PATCH_SELECT)
    @patch(_PATCH_SESSION)
    @patch(_PATCH_CREATE_ENGINE)
    def test_mark_success_without_optional_metrics(
        self, mock_create_engine, mock_session_cls, mock_select, mock_version_row, mock_execution_row
    ):
        mock_create_engine.return_value = MagicMock()
        session = _make_session_mock()
        mock_session_cls.return_value = session

        session.execute.side_effect = [
            _result_returning(MagicMock(version=1)),
            _result_returning(None),
        ]

        from odg_core.spark.job_versioning import ODGSparkListener

        listener = ODGSparkListener(
            job_name="job_y",
            run_id="run-no-metrics",
            job_hash="h2",
            input_datasets=[],
            output_datasets=[],
        )

        session.reset_mock()
        session.execute.side_effect = None
        session.__enter__ = MagicMock(return_value=session)
        session.__exit__ = MagicMock(return_value=False)
        execution_row = MagicMock()
        execution_row.start_time = datetime(2026, 1, 1)
        execution_row.rows_processed = None
        execution_row.bytes_processed = None
        session.execute.return_value = _result_returning(execution_row)

        listener.mark_success()

        assert execution_row.status == "success"
        session.commit.assert_called_once()


# ===================================================================
# 4. Spark  --  ODGSparkListener.mark_failure (lines 353-367)
# ===================================================================


class TestSparkMarkFailure:
    """Cover lines 353-367: updates execution status to 'failed'."""

    @patch(_PATCH_EXECUTION_ROW)
    @patch(_PATCH_VERSION_ROW)
    @patch(_PATCH_SELECT)
    @patch(_PATCH_SESSION)
    @patch(_PATCH_CREATE_ENGINE)
    def test_mark_failure_updates_execution(
        self, mock_create_engine, mock_session_cls, mock_select, mock_version_row, mock_execution_row
    ):
        mock_create_engine.return_value = MagicMock()
        session = _make_session_mock()
        mock_session_cls.return_value = session

        session.execute.side_effect = [
            _result_returning(MagicMock(version=1)),
            _result_returning(None),
        ]

        from odg_core.spark.job_versioning import ODGSparkListener

        listener = ODGSparkListener(
            job_name="job_fail",
            run_id="run-fail",
            job_hash="hf",
            input_datasets=[],
            output_datasets=[],
        )

        session.reset_mock()
        session.execute.side_effect = None
        session.__enter__ = MagicMock(return_value=session)
        session.__exit__ = MagicMock(return_value=False)
        execution_row = MagicMock()
        execution_row.start_time = datetime(2026, 1, 1)
        session.execute.return_value = _result_returning(execution_row)

        listener.mark_failure("OOM error", stacktrace="Traceback ...")

        assert execution_row.status == "failed"
        assert execution_row.error_message == "OOM error"
        assert execution_row.error_stacktrace == "Traceback ..."
        assert execution_row.end_time is not None
        assert execution_row.duration_ms is not None
        session.commit.assert_called_once()

    @patch(_PATCH_EXECUTION_ROW)
    @patch(_PATCH_VERSION_ROW)
    @patch(_PATCH_SELECT)
    @patch(_PATCH_SESSION)
    @patch(_PATCH_CREATE_ENGINE)
    def test_mark_failure_no_execution_found(
        self, mock_create_engine, mock_session_cls, mock_select, mock_version_row, mock_execution_row
    ):
        mock_create_engine.return_value = MagicMock()
        session = _make_session_mock()
        mock_session_cls.return_value = session

        session.execute.side_effect = [
            _result_returning(MagicMock(version=1)),
            _result_returning(None),
        ]

        from odg_core.spark.job_versioning import ODGSparkListener

        listener = ODGSparkListener(
            job_name="job_fail2",
            run_id="run-fail2",
            job_hash="hf2",
            input_datasets=[],
            output_datasets=[],
        )

        session.reset_mock()
        session.execute.side_effect = None
        session.__enter__ = MagicMock(return_value=session)
        session.__exit__ = MagicMock(return_value=False)
        session.execute.return_value = _result_returning(None)

        listener.mark_failure("some error")
        session.commit.assert_not_called()

    @patch(_PATCH_EXECUTION_ROW)
    @patch(_PATCH_VERSION_ROW)
    @patch(_PATCH_SELECT)
    @patch(_PATCH_SESSION)
    @patch(_PATCH_CREATE_ENGINE)
    def test_mark_failure_without_stacktrace(
        self, mock_create_engine, mock_session_cls, mock_select, mock_version_row, mock_execution_row
    ):
        mock_create_engine.return_value = MagicMock()
        session = _make_session_mock()
        mock_session_cls.return_value = session

        session.execute.side_effect = [
            _result_returning(MagicMock(version=1)),
            _result_returning(None),
        ]

        from odg_core.spark.job_versioning import ODGSparkListener

        listener = ODGSparkListener(
            job_name="job_fail3",
            run_id="run-fail3",
            job_hash="hf3",
            input_datasets=[],
            output_datasets=[],
        )

        session.reset_mock()
        session.execute.side_effect = None
        session.__enter__ = MagicMock(return_value=session)
        session.__exit__ = MagicMock(return_value=False)
        execution_row = MagicMock()
        execution_row.start_time = datetime(2026, 1, 1)
        session.execute.return_value = _result_returning(execution_row)

        listener.mark_failure("timeout error")

        assert execution_row.error_message == "timeout error"
        assert execution_row.error_stacktrace is None


# ===================================================================
# 5. Polars  --  VersionedPolarsJob._get_next_version (lines 93-98)
# ===================================================================


class TestPolarsGetNextVersion:
    """Cover lines 93-98: DB query for max version."""

    @patch(_PATCH_VERSION_ROW)
    @patch(_PATCH_FUNC)
    @patch(_PATCH_SELECT)
    @patch(_PATCH_SESSION)
    @patch(_PATCH_CREATE_ENGINE)
    def test_returns_incremented_version(
        self, mock_create_engine, mock_session_cls, mock_select, mock_func, mock_version_row
    ):
        mock_create_engine.return_value = MagicMock()
        session = _make_session_mock()
        mock_session_cls.return_value = session

        session.execute.return_value.scalar.return_value = 5

        lazy_plan = MagicMock()
        lazy_plan.explain.return_value = "FILTER col > 10"

        from odg_core.polars.versioned_pipeline import VersionedPolarsJob

        job = VersionedPolarsJob(
            job_name="agg_sales",
            lazy_plan=lazy_plan,
            input_datasets=["silver/sales"],
        )
        result = job._get_next_version()
        assert result == 6

    @patch(_PATCH_VERSION_ROW)
    @patch(_PATCH_FUNC)
    @patch(_PATCH_SELECT)
    @patch(_PATCH_SESSION)
    @patch(_PATCH_CREATE_ENGINE)
    def test_returns_one_when_no_versions_exist(
        self, mock_create_engine, mock_session_cls, mock_select, mock_func, mock_version_row
    ):
        mock_create_engine.return_value = MagicMock()
        session = _make_session_mock()
        mock_session_cls.return_value = session

        session.execute.return_value.scalar.return_value = None

        lazy_plan = MagicMock()
        lazy_plan.explain.return_value = "SCAN csv"

        from odg_core.polars.versioned_pipeline import VersionedPolarsJob

        job = VersionedPolarsJob(job_name="new_job", lazy_plan=lazy_plan)
        result = job._get_next_version()
        assert result == 1

    @patch(_PATCH_CREATE_ENGINE, side_effect=Exception("connection refused"))
    def test_returns_one_on_db_error(self, mock_create_engine):
        lazy_plan = MagicMock()
        lazy_plan.explain.return_value = "SCAN"

        from odg_core.polars.versioned_pipeline import VersionedPolarsJob

        job = VersionedPolarsJob(job_name="err_job", lazy_plan=lazy_plan)
        result = job._get_next_version()
        assert result == 1


# ===================================================================
# 6. Polars  --  VersionedPolarsJob.register_version (lines 121-167)
# ===================================================================


class TestPolarsRegisterVersion:
    """Cover lines 121-167: full new-version path."""

    @patch(_PATCH_VERSION_ROW)
    @patch(_PATCH_SELECT)
    @patch(_PATCH_SESSION)
    @patch(_PATCH_CREATE_ENGINE)
    def test_creates_new_version_when_hash_not_found(
        self, mock_create_engine, mock_session_cls, mock_select, mock_version_row
    ):
        mock_create_engine.return_value = MagicMock()
        session = _make_session_mock()
        mock_session_cls.return_value = session

        # register_version: existing lookup returns None
        session.execute.side_effect = [
            _result_returning(None),  # existing hash lookup
        ]

        lazy_plan = MagicMock()
        lazy_plan.explain.return_value = "FILTER col > 0"

        from odg_core.polars.versioned_pipeline import VersionedPolarsJob

        job = VersionedPolarsJob(
            job_name="polars_agg",
            lazy_plan=lazy_plan,
            input_datasets=["silver/events"],
            git_commit="def456",
        )

        # Patch _get_next_version to avoid a second DB call within register_version
        with patch.object(job, "_get_next_version", return_value=3):
            version = job.register_version()

        assert version == 3
        session.add.assert_called_once()
        session.commit.assert_called_once()

        call_kwargs = mock_version_row.call_args[1]
        assert call_kwargs["pipeline_id"] == "polars_agg"
        assert call_kwargs["version"] == 3
        assert call_kwargs["created_by"] == "polars"
        assert call_kwargs["is_active"] is True
        assert call_kwargs["dag_definition"]["type"] == "polars"

    @patch(_PATCH_VERSION_ROW)
    @patch(_PATCH_SELECT)
    @patch(_PATCH_SESSION)
    @patch(_PATCH_CREATE_ENGINE)
    def test_returns_existing_version_when_hash_found(
        self, mock_create_engine, mock_session_cls, mock_select, mock_version_row
    ):
        mock_create_engine.return_value = MagicMock()
        session = _make_session_mock()
        mock_session_cls.return_value = session

        existing_row = MagicMock()
        existing_row.version = 7
        session.execute.return_value = _result_returning(existing_row)

        lazy_plan = MagicMock()
        lazy_plan.explain.return_value = "FILTER"

        from odg_core.polars.versioned_pipeline import VersionedPolarsJob

        job = VersionedPolarsJob(job_name="existing_polars", lazy_plan=lazy_plan)
        version = job.register_version()

        assert version == 7
        session.add.assert_not_called()

    @patch(_PATCH_VERSION_ROW)
    @patch(_PATCH_SELECT)
    @patch(_PATCH_SESSION)
    @patch(_PATCH_CREATE_ENGINE)
    def test_plan_explain_fails_during_register(
        self, mock_create_engine, mock_session_cls, mock_select, mock_version_row
    ):
        """When lazy_plan.explain() raises inside register_version, fallback text."""
        mock_create_engine.return_value = MagicMock()
        session = _make_session_mock()
        mock_session_cls.return_value = session

        session.execute.side_effect = [
            _result_returning(None),  # no existing hash
        ]

        lazy_plan = MagicMock()
        # explain() works in __init__ for hash computation but fails in register
        call_count = {"n": 0}

        def explain_side_effect(optimized=True):
            call_count["n"] += 1
            # First call is in _compute_plan_hash (from __init__)
            if call_count["n"] <= 1:
                return "PLAN HASH SOURCE"
            raise RuntimeError("explain failed")

        lazy_plan.explain.side_effect = explain_side_effect

        from odg_core.polars.versioned_pipeline import VersionedPolarsJob

        job = VersionedPolarsJob(job_name="fail_explain", lazy_plan=lazy_plan)

        with patch.object(job, "_get_next_version", return_value=1):
            version = job.register_version()

        assert version == 1
        call_kwargs = mock_version_row.call_args[1]
        assert call_kwargs["transformation_code"] == "Plan explain not available"


# ===================================================================
# 7. Polars  --  VersionedPolarsJob._track_execution (lines 256-289)
# ===================================================================


class TestPolarsTrackExecution:
    """Cover lines 256-289: creating PipelineExecutionRow."""

    @patch(_PATCH_EXECUTION_ROW)
    @patch(_PATCH_VERSION_ROW)
    @patch(_PATCH_SELECT)
    @patch(_PATCH_SESSION)
    @patch(_PATCH_CREATE_ENGINE)
    def test_tracks_successful_execution_with_version(
        self, mock_create_engine, mock_session_cls, mock_select, mock_version_row, mock_execution_row
    ):
        mock_create_engine.return_value = MagicMock()
        session = _make_session_mock()
        mock_session_cls.return_value = session

        version_row = MagicMock()
        version_row.version = 4
        session.execute.return_value = _result_returning(version_row)

        lazy_plan = MagicMock()
        lazy_plan.explain.return_value = "AGGREGATE"

        from odg_core.polars.versioned_pipeline import VersionedPolarsJob

        job = VersionedPolarsJob(
            job_name="tracked_polars",
            lazy_plan=lazy_plan,
            input_datasets=["silver/data"],
        )

        start = datetime(2026, 1, 1, tzinfo=UTC)
        job._track_execution(
            run_id="run-polars-1",
            status="success",
            start_time=start,
            rows_processed=500,
            output_path="/output/data.parquet",
        )

        session.add.assert_called_once()
        session.commit.assert_called_once()

        call_kwargs = mock_execution_row.call_args[1]
        assert call_kwargs["run_id"] == "run-polars-1"
        assert call_kwargs["pipeline_version"] == 4
        assert call_kwargs["status"] == "success"
        assert call_kwargs["rows_processed"] == 500
        assert call_kwargs["output_datasets"] == [{"path": "/output/data.parquet"}]

    @patch(_PATCH_EXECUTION_ROW)
    @patch(_PATCH_VERSION_ROW)
    @patch(_PATCH_SELECT)
    @patch(_PATCH_SESSION)
    @patch(_PATCH_CREATE_ENGINE)
    def test_tracks_failed_execution_without_version(
        self, mock_create_engine, mock_session_cls, mock_select, mock_version_row, mock_execution_row
    ):
        mock_create_engine.return_value = MagicMock()
        session = _make_session_mock()
        mock_session_cls.return_value = session

        session.execute.return_value = _result_returning(None)  # no version row

        lazy_plan = MagicMock()
        lazy_plan.explain.return_value = "SCAN"

        from odg_core.polars.versioned_pipeline import VersionedPolarsJob

        job = VersionedPolarsJob(job_name="failed_polars", lazy_plan=lazy_plan)

        start = datetime(2026, 1, 1, tzinfo=UTC)
        job._track_execution(
            run_id="run-polars-fail",
            status="failed",
            start_time=start,
            error_message="column not found",
        )

        call_kwargs = mock_execution_row.call_args[1]
        assert call_kwargs["pipeline_version"] == 0
        assert call_kwargs["status"] == "failed"
        assert call_kwargs["error_message"] == "column not found"
        assert call_kwargs["output_datasets"] is None

    @patch(_PATCH_EXECUTION_ROW)
    @patch(_PATCH_VERSION_ROW)
    @patch(_PATCH_SELECT)
    @patch(_PATCH_SESSION)
    @patch(_PATCH_CREATE_ENGINE)
    def test_track_execution_db_error_handled_gracefully(
        self, mock_create_engine, mock_session_cls, mock_select, mock_version_row, mock_execution_row
    ):
        """DB errors should be caught and not propagate."""
        mock_create_engine.return_value = MagicMock()
        session = _make_session_mock()
        mock_session_cls.return_value = session
        session.execute.side_effect = Exception("DB timeout")

        lazy_plan = MagicMock()
        lazy_plan.explain.return_value = "SCAN"

        from odg_core.polars.versioned_pipeline import VersionedPolarsJob

        job = VersionedPolarsJob(job_name="err_polars", lazy_plan=lazy_plan)

        # Should not raise
        job._track_execution(
            run_id="run-err",
            status="failed",
            start_time=datetime(2026, 1, 1, tzinfo=UTC),
        )


# ===================================================================
# 8. DuckDB  --  VersionedDuckDBJob.register_version (lines 99-143)
# ===================================================================


class TestDuckDBRegisterVersion:
    """Cover lines 99-143: check existing hash, get next version, create row."""

    @patch(_PATCH_VERSION_ROW)
    @patch(_PATCH_FUNC)
    @patch(_PATCH_SELECT)
    @patch(_PATCH_SESSION)
    @patch(_PATCH_CREATE_ENGINE)
    def test_creates_new_version_when_hash_not_found(
        self, mock_create_engine, mock_session_cls, mock_select, mock_func, mock_version_row
    ):
        mock_create_engine.return_value = MagicMock()
        session = _make_session_mock()
        mock_session_cls.return_value = session

        session.execute.side_effect = [
            _result_returning(None),  # existing hash lookup
            MagicMock(scalar=MagicMock(return_value=2)),  # func.max
        ]

        from odg_core.duckdb.versioned_query import VersionedDuckDBJob

        job = VersionedDuckDBJob(
            job_name="aggregate_orders",
            sql_query="SELECT customer_id, SUM(amount) FROM orders GROUP BY customer_id",
            input_tables=["orders"],
            output_table="customer_aggregates",
            git_commit="commit-789",
        )
        version = job.register_version()

        assert version == 3
        session.add.assert_called_once()
        session.commit.assert_called_once()

        call_kwargs = mock_version_row.call_args[1]
        assert call_kwargs["pipeline_id"] == "aggregate_orders"
        assert call_kwargs["version"] == 3
        assert call_kwargs["created_by"] == "duckdb"
        assert call_kwargs["is_active"] is True
        assert call_kwargs["dag_definition"]["type"] == "duckdb"
        assert call_kwargs["dag_definition"]["output"] == "customer_aggregates"
        assert "orders" in call_kwargs["dag_definition"]["inputs"]
        assert call_kwargs["transformation_code"] == job.sql_query

    @patch(_PATCH_VERSION_ROW)
    @patch(_PATCH_SELECT)
    @patch(_PATCH_SESSION)
    @patch(_PATCH_CREATE_ENGINE)
    def test_returns_existing_version_when_hash_found(
        self, mock_create_engine, mock_session_cls, mock_select, mock_version_row
    ):
        mock_create_engine.return_value = MagicMock()
        session = _make_session_mock()
        mock_session_cls.return_value = session

        existing = MagicMock()
        existing.version = 5
        session.execute.return_value = _result_returning(existing)

        from odg_core.duckdb.versioned_query import VersionedDuckDBJob

        job = VersionedDuckDBJob(
            job_name="existing_query",
            sql_query="SELECT 1",
            input_tables=["t"],
            output_table="o",
        )
        version = job.register_version()

        assert version == 5
        session.add.assert_not_called()

    @patch(_PATCH_VERSION_ROW)
    @patch(_PATCH_FUNC)
    @patch(_PATCH_SELECT)
    @patch(_PATCH_SESSION)
    @patch(_PATCH_CREATE_ENGINE)
    def test_first_version_when_max_is_none(
        self, mock_create_engine, mock_session_cls, mock_select, mock_func, mock_version_row
    ):
        mock_create_engine.return_value = MagicMock()
        session = _make_session_mock()
        mock_session_cls.return_value = session

        session.execute.side_effect = [
            _result_returning(None),  # no existing hash
            MagicMock(scalar=MagicMock(return_value=None)),  # no previous versions
        ]

        from odg_core.duckdb.versioned_query import VersionedDuckDBJob

        job = VersionedDuckDBJob(
            job_name="brand_new",
            sql_query="SELECT * FROM raw_data",
            input_tables=["raw_data"],
            output_table="clean_data",
        )
        version = job.register_version()
        assert version == 1

    @patch(_PATCH_CREATE_ENGINE, side_effect=Exception("DB unreachable"))
    def test_register_returns_zero_on_db_error(self, mock_create_engine):
        from odg_core.duckdb.versioned_query import VersionedDuckDBJob

        job = VersionedDuckDBJob(
            job_name="err_job",
            sql_query="SELECT 1",
            input_tables=["t"],
            output_table="o",
        )
        version = job.register_version()
        assert version == 0


# ===================================================================
# 9. DuckDB  --  VersionedDuckDBJob._track_execution (lines 236-266)
# ===================================================================


class TestDuckDBTrackExecution:
    """Cover lines 236-266: create PipelineExecutionRow."""

    @patch(_PATCH_EXECUTION_ROW)
    @patch(_PATCH_VERSION_ROW)
    @patch(_PATCH_SELECT)
    @patch(_PATCH_SESSION)
    @patch(_PATCH_CREATE_ENGINE)
    def test_tracks_successful_execution(
        self, mock_create_engine, mock_session_cls, mock_select, mock_version_row, mock_execution_row
    ):
        mock_create_engine.return_value = MagicMock()
        session = _make_session_mock()
        mock_session_cls.return_value = session

        version_row = MagicMock()
        version_row.version = 2
        session.execute.return_value = _result_returning(version_row)

        from odg_core.duckdb.versioned_query import VersionedDuckDBJob

        job = VersionedDuckDBJob(
            job_name="duckdb_agg",
            sql_query="SELECT SUM(x) FROM t",
            input_tables=["t"],
            output_table="t_agg",
        )

        job._track_execution(
            run_id="run-duck-1",
            status="success",
            rows_processed=42,
            input_snapshots=[{"name": "t", "snapshot": "snap-1"}],
        )

        session.add.assert_called_once()
        session.commit.assert_called_once()

        call_kwargs = mock_execution_row.call_args[1]
        assert call_kwargs["run_id"] == "run-duck-1"
        assert call_kwargs["pipeline_version"] == 2
        assert call_kwargs["status"] == "success"
        assert call_kwargs["rows_processed"] == 42
        assert call_kwargs["input_datasets"] == [{"name": "t", "snapshot": "snap-1"}]

    @patch(_PATCH_EXECUTION_ROW)
    @patch(_PATCH_VERSION_ROW)
    @patch(_PATCH_SELECT)
    @patch(_PATCH_SESSION)
    @patch(_PATCH_CREATE_ENGINE)
    def test_tracks_failed_execution_without_version(
        self, mock_create_engine, mock_session_cls, mock_select, mock_version_row, mock_execution_row
    ):
        mock_create_engine.return_value = MagicMock()
        session = _make_session_mock()
        mock_session_cls.return_value = session

        session.execute.return_value = _result_returning(None)  # no version

        from odg_core.duckdb.versioned_query import VersionedDuckDBJob

        job = VersionedDuckDBJob(
            job_name="duck_fail",
            sql_query="SELECT bad_col FROM t",
            input_tables=["t"],
            output_table="t_out",
        )

        job._track_execution(
            run_id="run-duck-fail",
            status="failed",
            error_message="column not found: bad_col",
        )

        call_kwargs = mock_execution_row.call_args[1]
        assert call_kwargs["pipeline_version"] == 0
        assert call_kwargs["error_message"] == "column not found: bad_col"
        assert call_kwargs["rows_processed"] is None

    @patch(_PATCH_EXECUTION_ROW)
    @patch(_PATCH_VERSION_ROW)
    @patch(_PATCH_SELECT)
    @patch(_PATCH_SESSION)
    @patch(_PATCH_CREATE_ENGINE)
    def test_track_execution_db_error_handled(
        self, mock_create_engine, mock_session_cls, mock_select, mock_version_row, mock_execution_row
    ):
        mock_create_engine.return_value = MagicMock()
        session = _make_session_mock()
        mock_session_cls.return_value = session
        session.execute.side_effect = Exception("connection lost")

        from odg_core.duckdb.versioned_query import VersionedDuckDBJob

        job = VersionedDuckDBJob(
            job_name="duck_err",
            sql_query="SELECT 1",
            input_tables=["t"],
            output_table="o",
        )

        # Should not raise
        job._track_execution(run_id="run-err", status="failed")


# ===================================================================
# 10. Airflow  --  VersionedDAG.register_version (lines 102-146)
# ===================================================================


class TestAirflowRegisterVersion:
    """Cover lines 102-146: create new version in DB."""

    @patch(_PATCH_VERSION_ROW)
    @patch(_PATCH_FUNC)
    @patch(_PATCH_SELECT)
    @patch(_PATCH_SESSION)
    @patch(_PATCH_CREATE_ENGINE)
    def test_creates_new_version_when_hash_not_found(
        self, mock_create_engine, mock_session_cls, mock_select, mock_func, mock_version_row
    ):
        mock_create_engine.return_value = MagicMock()
        session = _make_session_mock()
        mock_session_cls.return_value = session

        session.execute.side_effect = [
            _result_returning(None),  # no existing hash
            MagicMock(scalar=MagicMock(return_value=4)),  # last version = 4
        ]

        dag = _make_airflow_dag("etl_pipeline")

        from odg_core.airflow.dag_versioning import VersionedDAG

        versioned = VersionedDAG(dag, git_commit="gitabc")
        version = versioned.register_version()

        assert version == 5
        session.add.assert_called_once()
        session.commit.assert_called_once()

        call_kwargs = mock_version_row.call_args[1]
        assert call_kwargs["pipeline_id"] == "etl_pipeline"
        assert call_kwargs["version"] == 5
        assert call_kwargs["created_by"] == "airflow"
        assert call_kwargs["is_active"] is True
        assert call_kwargs["dag_definition"]["dag_id"] == "etl_pipeline"
        assert "task_1" in call_kwargs["dag_definition"]["tasks"]

    @patch(_PATCH_VERSION_ROW)
    @patch(_PATCH_SELECT)
    @patch(_PATCH_SESSION)
    @patch(_PATCH_CREATE_ENGINE)
    def test_returns_existing_version_when_hash_found(
        self, mock_create_engine, mock_session_cls, mock_select, mock_version_row
    ):
        mock_create_engine.return_value = MagicMock()
        session = _make_session_mock()
        mock_session_cls.return_value = session

        existing = MagicMock()
        existing.version = 3
        session.execute.return_value = _result_returning(existing)

        dag = _make_airflow_dag("existing_dag")

        from odg_core.airflow.dag_versioning import VersionedDAG

        versioned = VersionedDAG(dag)
        version = versioned.register_version()

        assert version == 3
        session.add.assert_not_called()

    @patch(_PATCH_VERSION_ROW)
    @patch(_PATCH_FUNC)
    @patch(_PATCH_SELECT)
    @patch(_PATCH_SESSION)
    @patch(_PATCH_CREATE_ENGINE)
    def test_first_version_when_none_exist(
        self, mock_create_engine, mock_session_cls, mock_select, mock_func, mock_version_row
    ):
        mock_create_engine.return_value = MagicMock()
        session = _make_session_mock()
        mock_session_cls.return_value = session

        session.execute.side_effect = [
            _result_returning(None),  # no existing hash
            MagicMock(scalar=MagicMock(return_value=None)),  # no previous versions
        ]

        dag = _make_airflow_dag("brand_new_dag")

        from odg_core.airflow.dag_versioning import VersionedDAG

        versioned = VersionedDAG(dag)
        version = versioned.register_version()

        assert version == 1

    @patch(_PATCH_CREATE_ENGINE, side_effect=Exception("DB down"))
    def test_register_returns_zero_on_error(self, mock_create_engine):
        dag = _make_airflow_dag("failing_dag")

        from odg_core.airflow.dag_versioning import VersionedDAG

        versioned = VersionedDAG(dag)
        version = versioned.register_version()
        assert version == 0


# ===================================================================
# 11. Airflow  --  VersionedDAGRunHook._get_dag_version (lines 188-199)
# ===================================================================


class TestAirflowGetDagVersion:
    """Cover lines 188-199: looks up version from DB."""

    @patch(_PATCH_VERSION_ROW)
    @patch(_PATCH_SELECT)
    @patch(_PATCH_SESSION)
    @patch(_PATCH_CREATE_ENGINE)
    def test_returns_version_when_found(self, mock_create_engine, mock_session_cls, mock_select, mock_version_row):
        mock_create_engine.return_value = MagicMock()
        session = _make_session_mock()
        mock_session_cls.return_value = session

        version_row = MagicMock()
        version_row.version = 8
        session.execute.return_value = _result_returning(version_row)

        from odg_core.airflow.dag_versioning import VersionedDAGRunHook

        result = VersionedDAGRunHook._get_dag_version("test_dag", "hash123")
        assert result == 8

    @patch(_PATCH_VERSION_ROW)
    @patch(_PATCH_SELECT)
    @patch(_PATCH_SESSION)
    @patch(_PATCH_CREATE_ENGINE)
    def test_returns_zero_when_not_found(self, mock_create_engine, mock_session_cls, mock_select, mock_version_row):
        mock_create_engine.return_value = MagicMock()
        session = _make_session_mock()
        mock_session_cls.return_value = session

        session.execute.return_value = _result_returning(None)

        from odg_core.airflow.dag_versioning import VersionedDAGRunHook

        result = VersionedDAGRunHook._get_dag_version("missing_dag", "hash-x")
        assert result == 0

    @patch(_PATCH_CREATE_ENGINE, side_effect=Exception("connection refused"))
    def test_returns_zero_on_error(self, mock_create_engine):
        from odg_core.airflow.dag_versioning import VersionedDAGRunHook

        result = VersionedDAGRunHook._get_dag_version("any_dag", "any_hash")
        assert result == 0


# ===================================================================
# 12. Airflow  --  on_dagrun_success (lines 227-241)
# ===================================================================


class TestAirflowOnDagrunSuccess:
    """Cover lines 227-241: creates PipelineExecutionRow for success."""

    @patch(_PATCH_EXECUTION_ROW)
    @patch(_PATCH_SESSION)
    @patch(_PATCH_CREATE_ENGINE)
    def test_records_successful_dag_run(self, mock_create_engine, mock_session_cls, mock_execution_row):
        mock_create_engine.return_value = MagicMock()
        session = _make_session_mock()
        mock_session_cls.return_value = session

        dag = _make_airflow_dag("success_dag")
        dag_run = _make_airflow_dag_run("run-success-1")

        context = {"dag_run": dag_run, "dag": dag}

        from odg_core.airflow.dag_versioning import VersionedDAGRunHook

        with patch.object(VersionedDAGRunHook, "_get_dag_version", return_value=3):
            VersionedDAGRunHook.on_dagrun_success(context)

        session.add.assert_called_once()
        session.commit.assert_called_once()

        call_kwargs = mock_execution_row.call_args[1]
        assert call_kwargs["run_id"] == "run-success-1"
        assert call_kwargs["pipeline_id"] == "success_dag"
        assert call_kwargs["pipeline_version"] == 3
        assert call_kwargs["status"] == "success"
        assert call_kwargs["start_time"] == dag_run.start_date
        assert call_kwargs["end_time"] == dag_run.end_date
        assert call_kwargs["duration_ms"] == 300000  # 5 minutes in ms

    @patch(_PATCH_EXECUTION_ROW)
    @patch(_PATCH_SESSION)
    @patch(_PATCH_CREATE_ENGINE)
    def test_records_success_with_no_end_date(self, mock_create_engine, mock_session_cls, mock_execution_row):
        """When end_date is None, duration_ms should be None."""
        mock_create_engine.return_value = MagicMock()
        session = _make_session_mock()
        mock_session_cls.return_value = session

        dag = _make_airflow_dag("no_end_dag")
        dag_run = _make_airflow_dag_run("run-no-end")
        dag_run.end_date = None

        context = {"dag_run": dag_run, "dag": dag}

        from odg_core.airflow.dag_versioning import VersionedDAGRunHook

        with patch.object(VersionedDAGRunHook, "_get_dag_version", return_value=1):
            VersionedDAGRunHook.on_dagrun_success(context)

        call_kwargs = mock_execution_row.call_args[1]
        assert call_kwargs["duration_ms"] is None

    @patch(_PATCH_EXECUTION_ROW)
    @patch(_PATCH_SESSION)
    @patch(_PATCH_CREATE_ENGINE)
    def test_on_dagrun_success_handles_error_gracefully(self, mock_create_engine, mock_session_cls, mock_execution_row):
        mock_create_engine.return_value = MagicMock()
        session = _make_session_mock()
        mock_session_cls.return_value = session
        session.commit.side_effect = Exception("commit failed")

        dag = _make_airflow_dag("err_dag")
        dag_run = _make_airflow_dag_run("run-err")

        context = {"dag_run": dag_run, "dag": dag}

        from odg_core.airflow.dag_versioning import VersionedDAGRunHook

        with patch.object(VersionedDAGRunHook, "_get_dag_version", return_value=1):
            # Should not raise
            VersionedDAGRunHook.on_dagrun_success(context)


# ===================================================================
# 13. Airflow  --  on_dagrun_failure (lines 270-285)
# ===================================================================


class TestAirflowOnDagrunFailure:
    """Cover lines 270-285: creates PipelineExecutionRow for failure."""

    @patch(_PATCH_EXECUTION_ROW)
    @patch(_PATCH_SESSION)
    @patch(_PATCH_CREATE_ENGINE)
    def test_records_failed_dag_run_with_exception(self, mock_create_engine, mock_session_cls, mock_execution_row):
        mock_create_engine.return_value = MagicMock()
        session = _make_session_mock()
        mock_session_cls.return_value = session

        dag = _make_airflow_dag("fail_dag")
        dag_run = _make_airflow_dag_run("run-fail-1")

        context = {
            "dag_run": dag_run,
            "dag": dag,
            "exception": ValueError("task failed"),
        }

        from odg_core.airflow.dag_versioning import VersionedDAGRunHook

        with patch.object(VersionedDAGRunHook, "_get_dag_version", return_value=2):
            VersionedDAGRunHook.on_dagrun_failure(context)

        session.add.assert_called_once()
        session.commit.assert_called_once()

        call_kwargs = mock_execution_row.call_args[1]
        assert call_kwargs["run_id"] == "run-fail-1"
        assert call_kwargs["pipeline_id"] == "fail_dag"
        assert call_kwargs["pipeline_version"] == 2
        assert call_kwargs["status"] == "failed"
        assert call_kwargs["error_message"] == "task failed"
        assert call_kwargs["duration_ms"] == 300000

    @patch(_PATCH_EXECUTION_ROW)
    @patch(_PATCH_SESSION)
    @patch(_PATCH_CREATE_ENGINE)
    def test_records_failure_without_exception(self, mock_create_engine, mock_session_cls, mock_execution_row):
        mock_create_engine.return_value = MagicMock()
        session = _make_session_mock()
        mock_session_cls.return_value = session

        dag = _make_airflow_dag("fail_dag_no_exc")
        dag_run = _make_airflow_dag_run("run-fail-no-exc")

        context = {"dag_run": dag_run, "dag": dag}  # no "exception" key

        from odg_core.airflow.dag_versioning import VersionedDAGRunHook

        with patch.object(VersionedDAGRunHook, "_get_dag_version", return_value=1):
            VersionedDAGRunHook.on_dagrun_failure(context)

        call_kwargs = mock_execution_row.call_args[1]
        assert call_kwargs["error_message"] is None

    @patch(_PATCH_EXECUTION_ROW)
    @patch(_PATCH_SESSION)
    @patch(_PATCH_CREATE_ENGINE)
    def test_records_failure_with_no_dates(self, mock_create_engine, mock_session_cls, mock_execution_row):
        """When start_date and end_date are None, duration_ms is None."""
        mock_create_engine.return_value = MagicMock()
        session = _make_session_mock()
        mock_session_cls.return_value = session

        dag = _make_airflow_dag("fail_no_dates")
        dag_run = _make_airflow_dag_run("run-no-dates")
        dag_run.start_date = None
        dag_run.end_date = None

        context = {
            "dag_run": dag_run,
            "dag": dag,
            "exception": RuntimeError("timeout"),
        }

        from odg_core.airflow.dag_versioning import VersionedDAGRunHook

        with patch.object(VersionedDAGRunHook, "_get_dag_version", return_value=1):
            VersionedDAGRunHook.on_dagrun_failure(context)

        call_kwargs = mock_execution_row.call_args[1]
        assert call_kwargs["duration_ms"] is None
        assert call_kwargs["error_message"] == "timeout"

    @patch(_PATCH_EXECUTION_ROW)
    @patch(_PATCH_SESSION)
    @patch(_PATCH_CREATE_ENGINE)
    def test_on_dagrun_failure_handles_error_gracefully(self, mock_create_engine, mock_session_cls, mock_execution_row):
        mock_create_engine.return_value = MagicMock()
        session = _make_session_mock()
        mock_session_cls.return_value = session
        session.commit.side_effect = Exception("DB locked")

        dag = _make_airflow_dag("err_fail_dag")
        dag_run = _make_airflow_dag_run("run-err-fail")

        context = {"dag_run": dag_run, "dag": dag}

        from odg_core.airflow.dag_versioning import VersionedDAGRunHook

        with patch.object(VersionedDAGRunHook, "_get_dag_version", return_value=1):
            # Should not raise
            VersionedDAGRunHook.on_dagrun_failure(context)


# ===================================================================
# 14. Airflow  --  module-level on_dagrun_success / on_dagrun_failure aliases
# ===================================================================


class TestAirflowModuleLevelCallbacks:
    """Verify the module-level callback aliases point to the right methods."""

    def test_on_dagrun_success_alias(self):
        from odg_core.airflow.dag_versioning import (
            VersionedDAGRunHook,
            on_dagrun_success,
        )

        assert on_dagrun_success is VersionedDAGRunHook.on_dagrun_success

    def test_on_dagrun_failure_alias(self):
        from odg_core.airflow.dag_versioning import (
            VersionedDAGRunHook,
            on_dagrun_failure,
        )

        assert on_dagrun_failure is VersionedDAGRunHook.on_dagrun_failure


# ===================================================================
# 15. Spark  --  emit_lineage (bonus coverage)
# ===================================================================


class TestSparkEmitLineage:
    """Cover emit_lineage which calls odg_core.lineage.emitter.emit_lineage_event."""

    @patch("odg_core.lineage.emitter.emit_lineage_event")
    def test_emit_lineage_calls_emitter(self, mock_emit):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("# spark job\n")
            job_file = f.name

        try:
            from odg_core.spark.job_versioning import VersionedSparkJob

            job = VersionedSparkJob(
                job_name="lineage_job",
                job_file=job_file,
                input_datasets=["bronze/a", "bronze/b"],
                output_datasets=["silver/c"],
            )
            job.emit_lineage()

            mock_emit.assert_called_once()
            call_kwargs = mock_emit.call_args[1]
            assert call_kwargs["job_name"] == "spark_lineage_job"
            assert call_kwargs["event_type"] == "COMPLETE"
            assert len(call_kwargs["inputs"]) == 2
            assert len(call_kwargs["outputs"]) == 1
        finally:
            os.unlink(job_file)

    @patch("odg_core.lineage.emitter.emit_lineage_event", side_effect=Exception("emit failed"))
    def test_emit_lineage_handles_error(self, mock_emit):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("# job\n")
            job_file = f.name

        try:
            from odg_core.spark.job_versioning import VersionedSparkJob

            job = VersionedSparkJob(
                job_name="fail_lineage",
                job_file=job_file,
                input_datasets=[],
                output_datasets=[],
            )
            # Should not raise
            job.emit_lineage()
        finally:
            os.unlink(job_file)


# ===================================================================
# 16. DuckDB / Polars factory functions (bonus coverage)
# ===================================================================


class TestFactoryFunctions:
    """Cover create_versioned_query and create_versioned_pipeline."""

    def test_duckdb_factory(self):
        from odg_core.duckdb.versioned_query import create_versioned_query

        job = create_versioned_query(
            job_name="factory_duckdb",
            sql_query="SELECT 1",
            input_tables=["t"],
            output_table="o",
        )
        assert job.job_name == "factory_duckdb"
        assert job.sql_query == "SELECT 1"

    def test_polars_factory(self):
        lazy_plan = MagicMock()
        lazy_plan.explain.return_value = "SCAN"

        from odg_core.polars.versioned_pipeline import create_versioned_pipeline

        job = create_versioned_pipeline("factory_polars", lazy_plan)
        assert job.job_name == "factory_polars"
        assert job.lazy_plan is lazy_plan
