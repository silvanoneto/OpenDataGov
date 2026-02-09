"""Create pipeline versioning tables.

Revision ID: 009
Revises: 008
Create Date: 2026-02-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "009"
down_revision: str | None = "008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create pipeline_versions and pipeline_executions tables."""

    # Pipeline versions table
    op.create_table(
        "pipeline_versions",
        sa.Column(
            "pipeline_id",
            sa.String(200),
            primary_key=True,
            nullable=False,
            comment="Pipeline identifier (e.g., 'train_customer_churn')",
        ),
        sa.Column("version", sa.Integer, primary_key=True, nullable=False, comment="Sequential version number"),
        sa.Column(
            "dag_definition", JSONB, nullable=False, comment="DAG definition (KFP YAML, Airflow structure, etc.)"
        ),
        sa.Column("dag_hash", sa.String(64), nullable=False, comment="SHA256 hash of the DAG definition"),
        sa.Column("git_commit", sa.String(100), nullable=True, comment="Git commit that created this version"),
        sa.Column("transformation_code", sa.Text, nullable=True, comment="Transformation code (SQL/Python)"),
        sa.Column("transformation_hash", sa.String(64), nullable=True, comment="SHA256 hash of transformation code"),
        sa.Column("created_by", sa.String(200), nullable=False, comment="User or system that created this version"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            comment="When this version was created",
        ),
        sa.Column(
            "is_active",
            sa.Boolean,
            server_default="true",
            nullable=False,
            comment="Whether this pipeline is currently active",
        ),
    )

    op.create_index("ix_pipeline_active", "pipeline_versions", ["pipeline_id", "is_active"], unique=False)

    # Pipeline executions table
    op.create_table(
        "pipeline_executions",
        sa.Column(
            "run_id", sa.String(200), primary_key=True, nullable=False, comment="Unique execution identifier (UUID)"
        ),
        sa.Column("pipeline_id", sa.String(200), nullable=False, comment="Pipeline identifier"),
        sa.Column("pipeline_version", sa.Integer, nullable=False, comment="Version of the pipeline that was executed"),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="pending",
            comment="Execution status: pending, running, success, failed, cancelled",
        ),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False, comment="When execution started"),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=True, comment="When execution completed"),
        sa.Column("duration_ms", sa.Integer, nullable=True, comment="Execution duration in milliseconds"),
        sa.Column("input_datasets", JSONB, nullable=True, comment="Input datasets with snapshot IDs"),
        sa.Column("output_datasets", JSONB, nullable=True, comment="Output datasets with snapshot IDs"),
        sa.Column("error_message", sa.Text, nullable=True, comment="Error message if execution failed"),
        sa.Column("error_stacktrace", sa.Text, nullable=True, comment="Full error stacktrace"),
        sa.Column("rows_processed", sa.BigInteger, nullable=True, comment="Number of rows processed"),
        sa.Column("bytes_processed", sa.BigInteger, nullable=True, comment="Number of bytes processed"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            comment="When execution record was created",
        ),
    )

    op.create_index(
        "ix_pipeline_executions_pipeline", "pipeline_executions", ["pipeline_id", "pipeline_version"], unique=False
    )
    op.create_index("ix_pipeline_executions_status", "pipeline_executions", ["status"], unique=False)
    op.create_index("ix_pipeline_executions_start_time", "pipeline_executions", ["start_time"], unique=False)


def downgrade() -> None:
    """Drop pipeline versioning tables."""

    # Drop pipeline_executions table and indexes
    op.drop_index("ix_pipeline_executions_start_time", "pipeline_executions")
    op.drop_index("ix_pipeline_executions_status", "pipeline_executions")
    op.drop_index("ix_pipeline_executions_pipeline", "pipeline_executions")
    op.drop_table("pipeline_executions")

    # Drop pipeline_versions table and indexes
    op.drop_index("ix_pipeline_active", "pipeline_versions")
    op.drop_table("pipeline_versions")
