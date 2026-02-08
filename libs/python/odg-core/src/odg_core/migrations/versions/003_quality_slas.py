"""Quality SLA thresholds per DAMA dimension.

Revision ID: 003
Revises: 002
Create Date: 2026-02-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: str | None = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "quality_slas",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("dataset_id", sa.String(200), nullable=False),
        sa.Column("domain_id", sa.String(100), nullable=False),
        sa.Column("dimension", sa.String(30), nullable=False),
        sa.Column("threshold", sa.Float, nullable=False),
        sa.Column("owner_id", sa.String(200), nullable=False),
        sa.Column("review_interval_days", sa.Integer, nullable=False, server_default="90"),
        sa.Column("last_reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_quality_slas_dataset_dim", "quality_slas", ["dataset_id", "dimension"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_quality_slas_dataset_dim")
    op.drop_table("quality_slas")
