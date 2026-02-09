"""Tests for odg_core.duckdb.versioned_query module."""

from __future__ import annotations

import hashlib

from odg_core.duckdb.versioned_query import VersionedDuckDBJob, create_versioned_query

# ──── VersionedDuckDBJob.__init__ ───────────────────────────────


class TestVersionedDuckDBJobInit:
    """Tests for VersionedDuckDBJob initialization."""

    def test_init_stores_params(self) -> None:
        job = VersionedDuckDBJob(
            job_name="aggregate_orders",
            sql_query="SELECT * FROM orders",
            input_tables=["orders"],
            output_table="order_summary",
            git_commit="abc123",
        )

        assert job.job_name == "aggregate_orders"
        assert job.sql_query == "SELECT * FROM orders"
        assert job.input_tables == ["orders"]
        assert job.output_table == "order_summary"
        assert job.git_commit == "abc123"

    def test_init_strips_sql_query(self) -> None:
        job = VersionedDuckDBJob(
            job_name="test_job",
            sql_query="  \n  SELECT 1  \n  ",
            input_tables=[],
            output_table="out",
        )

        assert job.sql_query == "SELECT 1"


# ──── _compute_query_hash ───────────────────────────────────────


class TestComputeQueryHash:
    """Tests for VersionedDuckDBJob._compute_query_hash."""

    def test_compute_query_hash_returns_12_chars(self) -> None:
        job = VersionedDuckDBJob(
            job_name="test_job",
            sql_query="SELECT * FROM t",
            input_tables=["t"],
            output_table="out",
        )

        assert len(job.query_hash) == 12

    def test_compute_query_hash_deterministic(self) -> None:
        job1 = VersionedDuckDBJob(
            job_name="job",
            sql_query="SELECT * FROM t",
            input_tables=["t"],
            output_table="out",
        )
        job2 = VersionedDuckDBJob(
            job_name="job",
            sql_query="SELECT * FROM t",
            input_tables=["t"],
            output_table="out",
        )

        assert job1.query_hash == job2.query_hash

    def test_compute_query_hash_normalizes_case(self) -> None:
        job_upper = VersionedDuckDBJob(
            job_name="job",
            sql_query="SELECT * FROM ORDERS",
            input_tables=["orders"],
            output_table="out",
        )
        job_lower = VersionedDuckDBJob(
            job_name="job",
            sql_query="select * from orders",
            input_tables=["orders"],
            output_table="out",
        )

        assert job_upper.query_hash == job_lower.query_hash

    def test_compute_query_hash_normalizes_whitespace(self) -> None:
        job_compact = VersionedDuckDBJob(
            job_name="job",
            sql_query="SELECT * FROM orders WHERE id > 1",
            input_tables=["orders"],
            output_table="out",
        )
        job_spacey = VersionedDuckDBJob(
            job_name="job",
            sql_query="SELECT  *   FROM   orders   WHERE  id  >  1",
            input_tables=["orders"],
            output_table="out",
        )

        assert job_compact.query_hash == job_spacey.query_hash

    def test_compute_query_hash_different_queries_different_hash(self) -> None:
        job1 = VersionedDuckDBJob(
            job_name="job",
            sql_query="SELECT * FROM orders",
            input_tables=["orders"],
            output_table="out",
        )
        job2 = VersionedDuckDBJob(
            job_name="job",
            sql_query="SELECT * FROM customers",
            input_tables=["customers"],
            output_table="out",
        )

        assert job1.query_hash != job2.query_hash

    def test_compute_query_hash_matches_expected_value(self) -> None:
        job = VersionedDuckDBJob(
            job_name="job",
            sql_query="SELECT id FROM users",
            input_tables=["users"],
            output_table="out",
        )

        # The normalization: lowercase, strip, join whitespace
        normalized = " ".join("SELECT id FROM users".lower().split())
        expected = hashlib.sha256(normalized.encode()).hexdigest()[:12]
        assert job.query_hash == expected


# ──── create_versioned_query ────────────────────────────────────


class TestCreateVersionedQuery:
    """Tests for create_versioned_query factory function."""

    def test_create_versioned_query_factory(self) -> None:
        job = create_versioned_query(
            job_name="daily_summary",
            sql_query="SELECT date, SUM(amount) FROM sales GROUP BY date",
            input_tables=["sales"],
            output_table="sales_summary",
        )

        assert isinstance(job, VersionedDuckDBJob)
        assert job.job_name == "daily_summary"
        assert job.input_tables == ["sales"]
        assert job.output_table == "sales_summary"


# ──── register_version ──────────────────────────────────────────


class TestRegisterVersion:
    """Tests for VersionedDuckDBJob.register_version."""

    def test_register_version_returns_0_on_error(self) -> None:
        job = VersionedDuckDBJob(
            job_name="test_job",
            sql_query="SELECT 1",
            input_tables=[],
            output_table="out",
        )

        # Without a database, register_version should catch the exception and return 0
        result = job.register_version()
        assert result == 0


# ──── _track_execution ──────────────────────────────────────────


class TestTrackExecution:
    """Tests for VersionedDuckDBJob._track_execution."""

    def test_track_execution_swallows_errors(self) -> None:
        job = VersionedDuckDBJob(
            job_name="test_job",
            sql_query="SELECT 1",
            input_tables=[],
            output_table="out",
        )

        # _track_execution tries to connect to DB; it should silently fail
        # Should NOT raise
        job._track_execution(
            run_id="run-123",
            status="success",
            rows_processed=100,
        )
