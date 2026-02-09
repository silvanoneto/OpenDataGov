"""Create TimescaleDB hypertables for time-series metrics

Revision ID: 012_timescaledb_hypertables
Revises: 011_feast_materialization
Create Date: 2026-02-08 16:00:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "012_timescaledb_hypertables"
down_revision = "011_feast_materialization"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create TimescaleDB hypertables for time-series data."""

    # Enable TimescaleDB extension
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE")

    # 1. Model Performance Metrics (hypertable)
    op.create_table(
        "model_performance_ts",
        sa.Column("time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("model_name", sa.String(200), nullable=False),
        sa.Column("model_version", sa.Integer(), nullable=False),
        sa.Column("dataset_id", sa.String(500), nullable=True),
        sa.Column("dataset_version", sa.String(100), nullable=True),
        # Metrics
        sa.Column("accuracy", sa.Float(), nullable=True),
        sa.Column("precision", sa.Float(), nullable=True),
        sa.Column("recall", sa.Float(), nullable=True),
        sa.Column("f1_score", sa.Float(), nullable=True),
        sa.Column("auc_roc", sa.Float(), nullable=True),
        sa.Column("log_loss", sa.Float(), nullable=True),
        # Prediction stats
        sa.Column("prediction_count", sa.BigInteger(), nullable=True),
        sa.Column("avg_prediction_time_ms", sa.Float(), nullable=True),
        # Drift scores
        sa.Column("data_drift_score", sa.Float(), nullable=True),
        sa.Column("concept_drift_score", sa.Float(), nullable=True),
        # Custom metrics (JSONB for flexibility)
        sa.Column("custom_metrics", postgresql.JSONB(), nullable=True),
        # Metadata
        sa.Column("environment", sa.String(50), nullable=True),  # dev, staging, prod
        sa.Column("tags", postgresql.JSONB(), nullable=True),
        sa.PrimaryKeyConstraint("time", "model_name", "model_version"),
    )

    # Convert to hypertable (partitioned by time)
    op.execute("""
        SELECT create_hypertable(
            'model_performance_ts',
            'time',
            chunk_time_interval => INTERVAL '1 day',
            if_not_exists => TRUE
        )
    """)

    # Create indexes for efficient querying
    op.create_index("ix_model_perf_ts_model", "model_performance_ts", ["model_name", "model_version"])
    op.create_index("ix_model_perf_ts_dataset", "model_performance_ts", ["dataset_id"])
    op.create_index("ix_model_perf_ts_env", "model_performance_ts", ["environment"])

    # Compression policy (compress chunks older than 7 days)
    op.execute("""
        SELECT add_compression_policy('model_performance_ts', INTERVAL '7 days')
    """)

    # Retention policy (drop chunks older than 2 years)
    op.execute("""
        SELECT add_retention_policy('model_performance_ts', INTERVAL '2 years')
    """)

    # 2. Data Quality Metrics (hypertable)
    op.create_table(
        "quality_metrics_ts",
        sa.Column("time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("dataset_id", sa.String(500), nullable=False),
        sa.Column("dataset_version", sa.String(100), nullable=True),
        sa.Column("layer", sa.String(20), nullable=False),  # bronze, silver, gold
        # Completeness
        sa.Column("completeness_score", sa.Float(), nullable=True),
        sa.Column("missing_values_pct", sa.Float(), nullable=True),
        sa.Column("null_count", sa.BigInteger(), nullable=True),
        # Validity
        sa.Column("validity_score", sa.Float(), nullable=True),
        sa.Column("schema_violations", sa.Integer(), nullable=True),
        sa.Column("type_violations", sa.Integer(), nullable=True),
        # Uniqueness
        sa.Column("uniqueness_score", sa.Float(), nullable=True),
        sa.Column("duplicate_count", sa.BigInteger(), nullable=True),
        # Consistency
        sa.Column("consistency_score", sa.Float(), nullable=True),
        sa.Column("referential_integrity_violations", sa.Integer(), nullable=True),
        # Freshness
        sa.Column("freshness_score", sa.Float(), nullable=True),
        sa.Column("data_age_hours", sa.Float(), nullable=True),
        # Overall
        sa.Column("overall_dq_score", sa.Float(), nullable=True),
        # Volume metrics
        sa.Column("row_count", sa.BigInteger(), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        # Custom checks (JSONB)
        sa.Column("custom_checks", postgresql.JSONB(), nullable=True),
        sa.PrimaryKeyConstraint("time", "dataset_id", "layer"),
    )

    # Convert to hypertable
    op.execute("""
        SELECT create_hypertable(
            'quality_metrics_ts',
            'time',
            chunk_time_interval => INTERVAL '1 day',
            if_not_exists => TRUE
        )
    """)

    # Create indexes
    op.create_index("ix_quality_ts_dataset", "quality_metrics_ts", ["dataset_id"])
    op.create_index("ix_quality_ts_layer", "quality_metrics_ts", ["layer"])

    # Compression and retention
    op.execute("SELECT add_compression_policy('quality_metrics_ts', INTERVAL '7 days')")
    op.execute("SELECT add_retention_policy('quality_metrics_ts', INTERVAL '2 years')")

    # 3. Pipeline Execution Metrics (hypertable)
    op.create_table(
        "pipeline_metrics_ts",
        sa.Column("time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("pipeline_id", sa.String(200), nullable=False),
        sa.Column("pipeline_version", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.String(200), nullable=False),
        # Execution metrics
        sa.Column("status", sa.String(20), nullable=False),  # success, failed, running
        sa.Column("duration_ms", sa.BigInteger(), nullable=True),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=True),
        # Resource usage
        sa.Column("cpu_usage_percent", sa.Float(), nullable=True),
        sa.Column("memory_usage_mb", sa.Float(), nullable=True),
        sa.Column("disk_io_mb", sa.Float(), nullable=True),
        # Data volume
        sa.Column("rows_processed", sa.BigInteger(), nullable=True),
        sa.Column("bytes_processed", sa.BigInteger(), nullable=True),
        # Error tracking
        sa.Column("error_count", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        # Spark-specific metrics (if applicable)
        sa.Column("spark_metrics", postgresql.JSONB(), nullable=True),
        # Environment
        sa.Column("executor_type", sa.String(50), nullable=True),  # spark, airflow, kubeflow
        sa.Column("cluster_id", sa.String(100), nullable=True),
        sa.PrimaryKeyConstraint("time", "pipeline_id", "run_id"),
    )

    # Convert to hypertable
    op.execute("""
        SELECT create_hypertable(
            'pipeline_metrics_ts',
            'time',
            chunk_time_interval => INTERVAL '1 day',
            if_not_exists => TRUE
        )
    """)

    # Create indexes
    op.create_index("ix_pipeline_ts_pipeline", "pipeline_metrics_ts", ["pipeline_id", "pipeline_version"])
    op.create_index("ix_pipeline_ts_status", "pipeline_metrics_ts", ["status"])
    op.create_index("ix_pipeline_ts_executor", "pipeline_metrics_ts", ["executor_type"])

    # Compression and retention
    op.execute("SELECT add_compression_policy('pipeline_metrics_ts', INTERVAL '7 days')")
    op.execute("SELECT add_retention_policy('pipeline_metrics_ts', INTERVAL '2 years')")

    # 4. Create continuous aggregates for dashboards (pre-computed rollups)

    # Model performance - hourly rollup
    op.execute("""
        CREATE MATERIALIZED VIEW model_performance_hourly
        WITH (timescaledb.continuous) AS
        SELECT
            time_bucket('1 hour', time) AS bucket,
            model_name,
            model_version,
            AVG(accuracy) AS avg_accuracy,
            AVG(f1_score) AS avg_f1_score,
            AVG(data_drift_score) AS avg_drift_score,
            SUM(prediction_count) AS total_predictions
        FROM model_performance_ts
        GROUP BY bucket, model_name, model_version
        WITH NO DATA
    """)

    # Refresh policy for continuous aggregate
    op.execute("""
        SELECT add_continuous_aggregate_policy('model_performance_hourly',
            start_offset => INTERVAL '1 day',
            end_offset => INTERVAL '1 hour',
            schedule_interval => INTERVAL '1 hour')
    """)

    # Quality metrics - daily rollup
    op.execute("""
        CREATE MATERIALIZED VIEW quality_metrics_daily
        WITH (timescaledb.continuous) AS
        SELECT
            time_bucket('1 day', time) AS bucket,
            dataset_id,
            layer,
            AVG(overall_dq_score) AS avg_dq_score,
            AVG(completeness_score) AS avg_completeness,
            AVG(freshness_score) AS avg_freshness,
            SUM(row_count) AS total_rows
        FROM quality_metrics_ts
        GROUP BY bucket, dataset_id, layer
        WITH NO DATA
    """)

    op.execute("""
        SELECT add_continuous_aggregate_policy('quality_metrics_daily',
            start_offset => INTERVAL '7 days',
            end_offset => INTERVAL '1 day',
            schedule_interval => INTERVAL '1 day')
    """)

    # Pipeline metrics - hourly rollup
    op.execute("""
        CREATE MATERIALIZED VIEW pipeline_metrics_hourly
        WITH (timescaledb.continuous) AS
        SELECT
            time_bucket('1 hour', time) AS bucket,
            pipeline_id,
            executor_type,
            COUNT(*) AS execution_count,
            COUNT(*) FILTER (WHERE status = 'success') AS success_count,
            COUNT(*) FILTER (WHERE status = 'failed') AS failed_count,
            AVG(duration_ms) AS avg_duration_ms,
            PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration_ms) AS p95_duration_ms,
            SUM(rows_processed) AS total_rows_processed
        FROM pipeline_metrics_ts
        GROUP BY bucket, pipeline_id, executor_type
        WITH NO DATA
    """)

    op.execute("""
        SELECT add_continuous_aggregate_policy('pipeline_metrics_hourly',
            start_offset => INTERVAL '1 day',
            end_offset => INTERVAL '1 hour',
            schedule_interval => INTERVAL '1 hour')
    """)


def downgrade() -> None:
    """Drop TimescaleDB hypertables and continuous aggregates."""

    # Drop continuous aggregates
    op.execute("DROP MATERIALIZED VIEW IF EXISTS pipeline_metrics_hourly CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS quality_metrics_daily CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS model_performance_hourly CASCADE")

    # Drop hypertables
    op.drop_table("pipeline_metrics_ts")
    op.drop_table("quality_metrics_ts")
    op.drop_table("model_performance_ts")
