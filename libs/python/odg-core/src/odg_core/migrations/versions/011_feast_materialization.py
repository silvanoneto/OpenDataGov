"""Add Feast materialization tracking table

Revision ID: 011_feast_materialization
Revises: 010_lineage_events
Create Date: 2026-02-08 15:00:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "011_feast_materialization"
down_revision = "010_lineage_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create feast_materializations table for tracking feature store jobs."""
    op.create_table(
        "feast_materializations",
        sa.Column("run_id", sa.String(length=200), nullable=False),
        sa.Column("feature_view", sa.String(length=200), nullable=False),
        sa.Column("feature_names", postgresql.JSONB(), nullable=True),
        # Source lineage
        sa.Column("source_pipeline_id", sa.String(length=200), nullable=True),
        sa.Column("source_pipeline_version", sa.Integer(), nullable=True),
        sa.Column("source_dataset_id", sa.String(length=500), nullable=True),
        sa.Column("source_dataset_version", sa.String(length=100), nullable=True),
        # Materialization window
        sa.Column("start_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("end_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("materialization_time", sa.DateTime(timezone=True), nullable=False),
        # Feature view version
        sa.Column("feature_view_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("run_id"),
    )

    # Create indexes for efficient querying
    op.create_index("ix_feast_mat_feature_view", "feast_materializations", ["feature_view"])
    op.create_index(
        "ix_feast_mat_source_pipeline", "feast_materializations", ["source_pipeline_id", "source_pipeline_version"]
    )
    op.create_index("ix_feast_mat_time", "feast_materializations", ["materialization_time"])


def downgrade() -> None:
    """Drop feast_materializations table."""
    op.drop_index("ix_feast_mat_time", table_name="feast_materializations")
    op.drop_index("ix_feast_mat_source_pipeline", table_name="feast_materializations")
    op.drop_index("ix_feast_mat_feature_view", table_name="feast_materializations")
    op.drop_table("feast_materializations")
