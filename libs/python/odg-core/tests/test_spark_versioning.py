"""Tests for odg_core.spark.job_versioning module."""

from __future__ import annotations

import hashlib
import sys
import tempfile
from unittest.mock import MagicMock, patch

from odg_core.spark.job_versioning import ODGSparkListener, VersionedSparkJob

# ──── VersionedSparkJob.__init__ ────────────────────────────────


class TestVersionedSparkJobInit:
    """Tests for VersionedSparkJob initialization."""

    def test_init_stores_params(self, tmp_path: MagicMock) -> None:
        job_file = str(tmp_path / "job.py")
        with open(job_file, "w") as f:
            f.write("print('hello')")

        job = VersionedSparkJob(
            job_name="transform_sales",
            job_file=job_file,
            input_datasets=["bronze/sales"],
            output_datasets=["silver/sales"],
            git_commit="abc123",
        )

        assert job.job_name == "transform_sales"
        assert job.job_file == job_file
        assert job.input_datasets == ["bronze/sales"]
        assert job.output_datasets == ["silver/sales"]
        assert job.git_commit == "abc123"


# ──── _compute_job_hash ─────────────────────────────────────────


class TestComputeJobHash:
    """Tests for VersionedSparkJob._compute_job_hash."""

    def test_compute_job_hash_with_file(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("SELECT * FROM table")
            f.flush()
            job = VersionedSparkJob(
                job_name="test_job",
                job_file=f.name,
                input_datasets=[],
                output_datasets=[],
            )

        expected = hashlib.sha256(b"SELECT * FROM table").hexdigest()[:12]
        assert job.job_hash == expected

    def test_compute_job_hash_returns_12_chars(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("some content")
            f.flush()
            job = VersionedSparkJob(
                job_name="test_job",
                job_file=f.name,
                input_datasets=[],
                output_datasets=[],
            )

        assert len(job.job_hash) == 12

    def test_compute_job_hash_deterministic(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("deterministic content")
            f.flush()
            job1 = VersionedSparkJob(
                job_name="job",
                job_file=f.name,
                input_datasets=[],
                output_datasets=[],
            )
            job2 = VersionedSparkJob(
                job_name="job",
                job_file=f.name,
                input_datasets=[],
                output_datasets=[],
            )

        assert job1.job_hash == job2.job_hash

    def test_compute_job_hash_file_not_found_uses_name(self) -> None:
        job = VersionedSparkJob(
            job_name="missing_job",
            job_file="/nonexistent/path/to/job.py",
            input_datasets=[],
            output_datasets=[],
        )

        expected = hashlib.sha256(b"missing_job").hexdigest()[:12]
        assert job.job_hash == expected


# ──── emit_lineage ──────────────────────────────────────────────


class TestEmitLineage:
    """Tests for VersionedSparkJob.emit_lineage."""

    def test_emit_lineage_calls_emitter(self) -> None:
        job = VersionedSparkJob(
            job_name="test_job",
            job_file="/nonexistent.py",
            input_datasets=["bronze/sales"],
            output_datasets=["silver/sales"],
        )

        mock_emit = MagicMock()
        mock_emitter_mod = MagicMock(emit_lineage_event=mock_emit)
        with patch.dict(sys.modules, {"odg_core.lineage.emitter": mock_emitter_mod}):
            job.emit_lineage()

        mock_emit.assert_called_once_with(
            job_name="spark_test_job",
            inputs=[{"namespace": "lakehouse", "name": "bronze/sales"}],
            outputs=[{"namespace": "lakehouse", "name": "silver/sales"}],
            event_type="COMPLETE",
        )

    def test_emit_lineage_swallows_errors(self) -> None:
        job = VersionedSparkJob(
            job_name="test_job",
            job_file="/nonexistent.py",
            input_datasets=["bronze/sales"],
            output_datasets=["silver/sales"],
        )

        # emit_lineage does a lazy import that will fail; it should swallow the error
        with patch.dict(
            "sys.modules",
            {"odg_core.lineage.emitter": MagicMock(emit_lineage_event=MagicMock(side_effect=RuntimeError("boom")))},
        ):
            # Should NOT raise
            job.emit_lineage()


# ──── register_version ──────────────────────────────────────────


class TestRegisterVersion:
    """Tests for VersionedSparkJob.register_version."""

    def test_register_version_returns_0_on_error(self) -> None:
        job = VersionedSparkJob(
            job_name="test_job",
            job_file="/nonexistent.py",
            input_datasets=[],
            output_datasets=[],
        )

        # Without a database, register_version should catch the exception and return 0
        result = job.register_version()
        assert result == 0


# ──── track_execution ───────────────────────────────────────────


class TestTrackExecution:
    """Tests for VersionedSparkJob.track_execution."""

    def test_track_execution_swallows_errors(self) -> None:
        job = VersionedSparkJob(
            job_name="test_job",
            job_file="/nonexistent.py",
            input_datasets=[],
            output_datasets=[],
        )

        mock_spark = MagicMock()
        mock_spark.sparkContext.addSparkListener.side_effect = RuntimeError("no spark")

        # Should NOT raise
        job.track_execution(mock_spark, "run-123")


# ──── ODGSparkListener ──────────────────────────────────────────


class TestODGSparkListener:
    """Tests for ODGSparkListener initialization."""

    def test_listener_init_stores_params(self) -> None:
        # _create_execution_record will try to connect to DB and silently fail
        listener = ODGSparkListener(
            job_name="test_job",
            run_id="run-abc",
            job_hash="abc123def456",
            input_datasets=["input_ds"],
            output_datasets=["output_ds"],
        )

        assert listener.job_name == "test_job"
        assert listener.run_id == "run-abc"
        assert listener.job_hash == "abc123def456"
        assert listener.input_datasets == ["input_ds"]
        assert listener.output_datasets == ["output_ds"]
        assert listener.start_time is not None
