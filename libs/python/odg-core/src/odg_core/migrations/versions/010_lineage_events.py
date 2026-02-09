"""Create lineage_events table for OpenLineage persistence.

Revision ID: 010
Revises: 009
Create Date: 2026-02-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "010"
down_revision: str | None = "009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create lineage_events table for persisting OpenLineage events."""

    op.create_table(
        "lineage_events",
        sa.Column(
            "id",
            sa.Uuid,
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            comment="Unique event identifier",
        ),
        sa.Column(
            "event_type", sa.String(20), nullable=False, comment="Event type: START, RUNNING, COMPLETE, FAIL, ABORT"
        ),
        sa.Column("event_time", sa.DateTime(timezone=True), nullable=False, comment="When the event occurred"),
        sa.Column(
            "job_namespace",
            sa.String(200),
            nullable=False,
            index=True,
            comment="Job namespace (e.g., 'lakehouse', 'mlflow')",
        ),
        sa.Column(
            "job_name",
            sa.String(200),
            nullable=False,
            index=True,
            comment="Job name (e.g., 'transform_sales', 'train_model_churn')",
        ),
        sa.Column("run_id", sa.String(200), nullable=False, index=True, comment="Unique run identifier (UUID)"),
        sa.Column("inputs", JSONB, nullable=True, comment="Input datasets with namespaces and facets"),
        sa.Column("outputs", JSONB, nullable=True, comment="Output datasets with namespaces and facets"),
        sa.Column("job_facets", JSONB, nullable=True, comment="Additional job metadata (source code, version, etc.)"),
        sa.Column("run_facets", JSONB, nullable=True, comment="Run-specific metadata (processing stats, errors, etc.)"),
        sa.Column(
            "producer",
            sa.String(200),
            nullable=True,
            comment="Producer that emitted this event (e.g., 'odg-core/0.1.0')",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            comment="When this record was inserted",
        ),
    )

    # Indexes for common queries
    op.create_index("ix_lineage_events_job", "lineage_events", ["job_namespace", "job_name"], unique=False)
    op.create_index("ix_lineage_events_event_time", "lineage_events", ["event_time"], unique=False)
    op.create_index("ix_lineage_events_event_type", "lineage_events", ["event_type"], unique=False)


def downgrade() -> None:
    """Drop lineage_events table."""

    op.drop_index("ix_lineage_events_event_type", "lineage_events")
    op.drop_index("ix_lineage_events_event_time", "lineage_events")
    op.drop_index("ix_lineage_events_job", "lineage_events")
    op.drop_table("lineage_events")
