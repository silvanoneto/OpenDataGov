"""Add model versioning and lineage fields to model_cards.

Revision ID: 008
Revises: 007
Create Date: 2026-02-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "008"
down_revision: str | None = "007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add versioning and lineage tracking fields to model_cards table."""

    # Training data lineage
    op.add_column(
        "model_cards",
        sa.Column("training_dataset_id", sa.String(500), nullable=True, comment="Dataset ID used for training"),
    )
    op.add_column(
        "model_cards",
        sa.Column(
            "training_dataset_version",
            sa.String(100),
            nullable=True,
            comment="Snapshot/version ID of the training dataset (e.g., Iceberg snapshot)",
        ),
    )
    op.add_column(
        "model_cards",
        sa.Column(
            "training_timestamp", sa.DateTime(timezone=True), nullable=True, comment="When the model was trained"
        ),
    )

    # Model ancestry for retraining lineage
    op.add_column(
        "model_cards",
        sa.Column(
            "parent_model_version",
            sa.String(100),
            nullable=True,
            comment="Previous model version (for retraining lineage)",
        ),
    )
    op.add_column(
        "model_cards",
        sa.Column(
            "is_retrained",
            sa.Boolean,
            server_default="false",
            nullable=False,
            comment="Whether this model is a result of retraining",
        ),
    )

    # Training environment tracking
    op.add_column(
        "model_cards",
        sa.Column(
            "training_environment",
            JSONB,
            nullable=True,
            comment="Environment info: python_version, library versions, CUDA, docker image",
        ),
    )

    # Performance history tracking
    op.add_column(
        "model_cards",
        sa.Column(
            "performance_history", JSONB, nullable=True, comment="Historical performance metrics and drift scores"
        ),
    )

    # Create indexes for common queries
    op.create_index("ix_model_cards_training_dataset", "model_cards", ["training_dataset_id"], unique=False)
    op.create_index("ix_model_cards_parent_version", "model_cards", ["parent_model_version"], unique=False)
    op.create_index("ix_model_cards_training_timestamp", "model_cards", ["training_timestamp"], unique=False)


def downgrade() -> None:
    """Remove versioning and lineage fields from model_cards table."""

    # Drop indexes
    op.drop_index("ix_model_cards_training_timestamp", "model_cards")
    op.drop_index("ix_model_cards_parent_version", "model_cards")
    op.drop_index("ix_model_cards_training_dataset", "model_cards")

    # Drop columns
    op.drop_column("model_cards", "performance_history")
    op.drop_column("model_cards", "training_environment")
    op.drop_column("model_cards", "is_retrained")
    op.drop_column("model_cards", "parent_model_version")
    op.drop_column("model_cards", "training_timestamp")
    op.drop_column("model_cards", "training_dataset_version")
    op.drop_column("model_cards", "training_dataset_id")
