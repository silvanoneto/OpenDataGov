"""Tests for odg_core.polars.versioned_pipeline module."""

from __future__ import annotations

import hashlib
from unittest.mock import MagicMock

from odg_core.polars.versioned_pipeline import VersionedPolarsJob, create_versioned_pipeline

# ──── VersionedPolarsJob.__init__ ───────────────────────────────


class TestVersionedPolarsJobInit:
    """Tests for VersionedPolarsJob initialization."""

    def test_init_stores_params(self) -> None:
        mock_lazy = MagicMock()
        mock_lazy.explain.return_value = "FILTER col > 10"

        job = VersionedPolarsJob(
            job_name="aggregate_sales",
            lazy_plan=mock_lazy,
            input_datasets=["bronze/sales"],
            git_commit="abc123",
        )

        assert job.job_name == "aggregate_sales"
        assert job.lazy_plan is mock_lazy
        assert job.input_datasets == ["bronze/sales"]
        assert job.git_commit == "abc123"

    def test_input_datasets_defaults_to_empty_list(self) -> None:
        mock_lazy = MagicMock()
        mock_lazy.explain.return_value = "SCAN csv"

        job = VersionedPolarsJob(
            job_name="test_job",
            lazy_plan=mock_lazy,
        )

        assert job.input_datasets == []


# ──── _compute_plan_hash ────────────────────────────────────────


class TestComputePlanHash:
    """Tests for VersionedPolarsJob._compute_plan_hash."""

    def test_compute_plan_hash_uses_explain(self) -> None:
        mock_lazy = MagicMock()
        mock_lazy.explain.return_value = "FILTER col > 10"

        job = VersionedPolarsJob(
            job_name="test_job",
            lazy_plan=mock_lazy,
        )

        mock_lazy.explain.assert_called_with(optimized=True)
        expected = hashlib.sha256(b"FILTER col > 10").hexdigest()[:12]
        assert job.plan_hash == expected

    def test_compute_plan_hash_returns_12_chars(self) -> None:
        mock_lazy = MagicMock()
        mock_lazy.explain.return_value = "some plan string"

        job = VersionedPolarsJob(
            job_name="test_job",
            lazy_plan=mock_lazy,
        )

        assert len(job.plan_hash) == 12

    def test_compute_plan_hash_deterministic(self) -> None:
        plan_str = "GROUPBY customer_id; AGG SUM(amount)"

        mock_lazy1 = MagicMock()
        mock_lazy1.explain.return_value = plan_str

        mock_lazy2 = MagicMock()
        mock_lazy2.explain.return_value = plan_str

        job1 = VersionedPolarsJob(job_name="job", lazy_plan=mock_lazy1)
        job2 = VersionedPolarsJob(job_name="job", lazy_plan=mock_lazy2)

        assert job1.plan_hash == job2.plan_hash

    def test_compute_plan_hash_different_plans_different_hash(self) -> None:
        mock_lazy1 = MagicMock()
        mock_lazy1.explain.return_value = "FILTER col > 10"

        mock_lazy2 = MagicMock()
        mock_lazy2.explain.return_value = "FILTER col > 20"

        job1 = VersionedPolarsJob(job_name="job", lazy_plan=mock_lazy1)
        job2 = VersionedPolarsJob(job_name="job", lazy_plan=mock_lazy2)

        assert job1.plan_hash != job2.plan_hash

    def test_compute_plan_hash_fallback_on_error(self) -> None:
        mock_lazy = MagicMock()
        mock_lazy.explain.side_effect = RuntimeError("explain failed")

        job = VersionedPolarsJob(
            job_name="fallback_job",
            lazy_plan=mock_lazy,
        )

        expected = hashlib.sha256(b"fallback_job").hexdigest()[:12]
        assert job.plan_hash == expected


# ──── create_versioned_pipeline ─────────────────────────────────


class TestCreateVersionedPipeline:
    """Tests for create_versioned_pipeline factory function."""

    def test_create_versioned_pipeline_factory(self) -> None:
        mock_lazy = MagicMock()
        mock_lazy.explain.return_value = "SCAN parquet"

        job = create_versioned_pipeline("my_pipeline", mock_lazy)

        assert isinstance(job, VersionedPolarsJob)
        assert job.job_name == "my_pipeline"
        assert job.lazy_plan is mock_lazy


# ──── register_version ──────────────────────────────────────────


class TestRegisterVersion:
    """Tests for VersionedPolarsJob.register_version."""

    def test_register_version_returns_0_on_error(self) -> None:
        mock_lazy = MagicMock()
        mock_lazy.explain.return_value = "plan"

        job = VersionedPolarsJob(
            job_name="test_job",
            lazy_plan=mock_lazy,
        )

        # Without a database, register_version should catch the exception and return 0
        result = job.register_version()
        assert result == 0


# ──── _get_next_version ─────────────────────────────────────────


class TestGetNextVersion:
    """Tests for VersionedPolarsJob._get_next_version."""

    def test_get_next_version_returns_1_on_error(self) -> None:
        mock_lazy = MagicMock()
        mock_lazy.explain.return_value = "plan"

        job = VersionedPolarsJob(
            job_name="test_job",
            lazy_plan=mock_lazy,
        )

        # Without a database, _get_next_version should catch the exception and return 1
        result = job._get_next_version()
        assert result == 1
