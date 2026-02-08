"""Quality reports table for quality-gate evaluation results.

Revision ID: 002
Revises: 001
Create Date: 2026-02-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "002"
down_revision: str | None = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "quality_reports",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("dataset_id", sa.String(200), nullable=False),
        sa.Column("domain_id", sa.String(100), nullable=False),
        sa.Column("layer", sa.String(20), nullable=False),
        sa.Column("suite_name", sa.String(200), nullable=False),
        sa.Column("dq_score", sa.Float, nullable=False),
        sa.Column("dimension_scores", JSONB, server_default="{}"),
        sa.Column("expectations_passed", sa.Integer, nullable=False, server_default="0"),
        sa.Column("expectations_failed", sa.Integer, nullable=False, server_default="0"),
        sa.Column("expectations_total", sa.Integer, nullable=False, server_default="0"),
        sa.Column("report_details", JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("triggered_by", sa.Uuid, sa.ForeignKey("governance_decisions.id"), nullable=True),
    )
    op.create_index("ix_quality_reports_dataset_id", "quality_reports", ["dataset_id"])
    op.create_index("ix_quality_reports_domain_id", "quality_reports", ["domain_id"])
    op.create_index("ix_quality_reports_dataset_layer", "quality_reports", ["dataset_id", "layer"])


def downgrade() -> None:
    op.drop_index("ix_quality_reports_dataset_layer")
    op.drop_index("ix_quality_reports_domain_id")
    op.drop_index("ix_quality_reports_dataset_id")
    op.drop_table("quality_reports")
