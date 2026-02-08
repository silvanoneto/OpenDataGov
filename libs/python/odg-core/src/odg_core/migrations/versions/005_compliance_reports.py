"""Compliance reports and findings tables.

Revision ID: 005
Revises: 004
Create Date: 2026-02-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "005"
down_revision: str | None = "004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "compliance_reports",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("framework", sa.String(50), nullable=False),
        sa.Column("jurisdiction", sa.String(20), nullable=True),
        sa.Column("passed", sa.Boolean, nullable=False),
        sa.Column("score", sa.Float, nullable=False),
        sa.Column("metadata", JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("created_by", sa.String(200), nullable=True),
    )
    op.create_index("ix_compliance_reports_framework", "compliance_reports", ["framework"])

    op.create_table(
        "compliance_findings",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("report_id", sa.Uuid, sa.ForeignKey("compliance_reports.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rule_id", sa.String(100), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("recommendation", sa.Text, nullable=False),
    )
    op.create_index("ix_compliance_findings_report_id", "compliance_findings", ["report_id"])
    op.create_index("ix_compliance_findings_severity", "compliance_findings", ["severity"])


def downgrade() -> None:
    op.drop_index("ix_compliance_findings_severity")
    op.drop_index("ix_compliance_findings_report_id")
    op.drop_table("compliance_findings")
    op.drop_index("ix_compliance_reports_framework")
    op.drop_table("compliance_reports")
