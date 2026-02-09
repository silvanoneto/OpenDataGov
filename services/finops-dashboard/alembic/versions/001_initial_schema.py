"""Initial FinOps Dashboard schema

Revision ID: 001_initial_schema
Revises:
Create Date: 2026-02-08 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create initial FinOps Dashboard schema."""

    # ==================== cloud_costs (TimescaleDB hypertable) ====================
    op.create_table(
        "cloud_costs",
        sa.Column("time", sa.DateTime(), nullable=False),
        sa.Column("cloud_provider", sa.String(length=10), nullable=False),
        sa.Column("account_id", sa.String(length=50), nullable=False),
        sa.Column("service", sa.String(length=100), nullable=False),
        sa.Column("region", sa.String(length=50), nullable=True),
        sa.Column("cost", sa.DECIMAL(precision=12, scale=4), nullable=False),
        sa.Column("currency", sa.String(length=3), server_default="USD", nullable=True),
        sa.Column("resource_id", sa.String(length=200), nullable=True),
        sa.Column("resource_name", sa.String(length=200), nullable=True),
        sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("project", sa.String(length=100), nullable=True),
        sa.Column("team", sa.String(length=100), nullable=True),
        sa.Column("environment", sa.String(length=50), nullable=True),
        sa.PrimaryKeyConstraint("time", "cloud_provider", "account_id", "service"),
    )

    # Create indexes for cloud_costs
    op.create_index("idx_cloud_costs_project", "cloud_costs", ["project", "time"])
    op.create_index("idx_cloud_costs_service", "cloud_costs", ["service", "time"])
    op.create_index("idx_cloud_costs_tags", "cloud_costs", ["tags"], postgresql_using="gin")

    # Convert to TimescaleDB hypertable
    op.execute(
        """
        SELECT create_hypertable(
            'cloud_costs',
            'time',
            chunk_time_interval => INTERVAL '1 day',
            if_not_exists => TRUE
        );
        """
    )

    # Enable compression for older chunks (> 7 days)
    op.execute(
        """
        ALTER TABLE cloud_costs SET (
            timescaledb.compress,
            timescaledb.compress_segmentby = 'cloud_provider,account_id,service'
        );
        """
    )

    op.execute(
        """
        SELECT add_compression_policy('cloud_costs', INTERVAL '7 days', if_not_exists => TRUE);
        """
    )

    # ==================== budgets ====================
    op.create_table(
        "budgets",
        sa.Column("budget_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("budget_name", sa.String(length=200), nullable=False),
        sa.Column("scope_type", sa.String(length=50), nullable=False),
        sa.Column("scope_value", sa.String(length=200), nullable=True),
        sa.Column("amount", sa.DECIMAL(precision=12, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=3), server_default="USD", nullable=True),
        sa.Column("period", sa.String(length=20), nullable=False),
        sa.Column("alert_thresholds", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("alert_channels", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_by", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
        sa.Column("active", sa.Boolean(), server_default="true", nullable=True),
        sa.PrimaryKeyConstraint("budget_id"),
    )

    # ==================== budget_status_history ====================
    op.create_table(
        "budget_status_history",
        sa.Column("history_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("budget_id", sa.Integer(), nullable=False),
        sa.Column("snapshot_date", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("spent_to_date", sa.DECIMAL(precision=12, scale=2), nullable=False),
        sa.Column("remaining", sa.DECIMAL(precision=12, scale=2), nullable=False),
        sa.Column("pct_consumed", sa.DECIMAL(precision=5, scale=2), nullable=False),
        sa.Column("burn_rate_per_day", sa.DECIMAL(precision=12, scale=2), nullable=True),
        sa.Column("forecast_exhaustion_date", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["budget_id"], ["budgets.budget_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("history_id"),
    )

    op.create_index("idx_budget_history_budget_id", "budget_status_history", ["budget_id", "snapshot_date"])

    # ==================== cost_anomalies ====================
    op.create_table(
        "cost_anomalies",
        sa.Column("anomaly_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("detected_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("cloud_provider", sa.String(length=10), nullable=True),
        sa.Column("service", sa.String(length=100), nullable=True),
        sa.Column("project", sa.String(length=100), nullable=True),
        sa.Column("resource_id", sa.String(length=200), nullable=True),
        sa.Column("expected_cost", sa.DECIMAL(precision=12, scale=4), nullable=True),
        sa.Column("actual_cost", sa.DECIMAL(precision=12, scale=4), nullable=True),
        sa.Column("deviation_pct", sa.DECIMAL(precision=5, scale=2), nullable=True),
        sa.Column("detection_method", sa.String(length=50), nullable=True),
        sa.Column("confidence_score", sa.DECIMAL(precision=3, scale=2), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="open", nullable=True),
        sa.Column("resolution_notes", sa.Text(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("resolved_by", sa.String(length=100), nullable=True),
        sa.PrimaryKeyConstraint("anomaly_id"),
    )

    op.create_index("idx_anomalies_status", "cost_anomalies", ["status", "detected_at"])
    op.create_index("idx_anomalies_service", "cost_anomalies", ["service", "detected_at"])

    # ==================== savings_recommendations ====================
    op.create_table(
        "savings_recommendations",
        sa.Column("recommendation_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("generated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("type", sa.String(length=50), nullable=False),
        sa.Column("priority", sa.String(length=20), nullable=True),
        sa.Column("cloud_provider", sa.String(length=10), nullable=True),
        sa.Column("service", sa.String(length=100), nullable=True),
        sa.Column("resource_id", sa.String(length=200), nullable=True),
        sa.Column("resource_name", sa.String(length=200), nullable=True),
        sa.Column("current_monthly_cost", sa.DECIMAL(precision=12, scale=2), nullable=True),
        sa.Column("projected_monthly_cost", sa.DECIMAL(precision=12, scale=2), nullable=True),
        sa.Column("monthly_savings", sa.DECIMAL(precision=12, scale=2), nullable=True),
        sa.Column("annual_savings", sa.DECIMAL(precision=12, scale=2), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("action_required", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=True),
        sa.Column("implemented_at", sa.DateTime(), nullable=True),
        sa.Column("implemented_by", sa.String(length=100), nullable=True),
        sa.PrimaryKeyConstraint("recommendation_id"),
    )

    op.create_index("idx_recommendations_status", "savings_recommendations", ["status", "generated_at"])
    op.create_index("idx_recommendations_savings", "savings_recommendations", ["monthly_savings"])


def downgrade() -> None:
    """Drop all FinOps Dashboard tables."""

    # Drop indexes first
    op.drop_index("idx_recommendations_savings", table_name="savings_recommendations")
    op.drop_index("idx_recommendations_status", table_name="savings_recommendations")
    op.drop_index("idx_anomalies_service", table_name="cost_anomalies")
    op.drop_index("idx_anomalies_status", table_name="cost_anomalies")
    op.drop_index("idx_budget_history_budget_id", table_name="budget_status_history")
    op.drop_index("idx_cloud_costs_tags", table_name="cloud_costs")
    op.drop_index("idx_cloud_costs_service", table_name="cloud_costs")
    op.drop_index("idx_cloud_costs_project", table_name="cloud_costs")

    # Drop tables
    op.drop_table("savings_recommendations")
    op.drop_table("cost_anomalies")
    op.drop_table("budget_status_history")
    op.drop_table("budgets")
    op.drop_table("cloud_costs")
