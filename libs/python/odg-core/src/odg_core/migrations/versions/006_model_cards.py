"""Model cards table for AI system documentation.

Revision ID: 006
Revises: 005
Create Date: 2026-02-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "006"
down_revision: str | None = "005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "model_cards",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("model_name", sa.String(200), nullable=False, unique=True),
        sa.Column("model_version", sa.String(50), nullable=False),
        sa.Column("owner", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, server_default=""),
        sa.Column("risk_level", sa.String(20), nullable=False, server_default="minimal"),
        sa.Column("expert_capability", sa.String(100), nullable=True),
        sa.Column("model_type", sa.String(100), server_default=""),
        sa.Column("metrics", JSONB, server_default="[]"),
        sa.Column("ethics", JSONB, server_default="{}"),
        sa.Column("limitations", JSONB, server_default="[]"),
        sa.Column("regulatory_requirements", JSONB, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by", sa.String(200), nullable=True),
    )
    op.create_index("ix_model_cards_risk_level", "model_cards", ["risk_level"])


def downgrade() -> None:
    op.drop_index("ix_model_cards_risk_level")
    op.drop_table("model_cards")
