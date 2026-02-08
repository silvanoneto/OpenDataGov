"""Metadata catalog and lineage edges tables.

Revision ID: 007
Revises: 006
Create Date: 2026-02-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "007"
down_revision: str | None = "006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "dataset_metadata",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("dataset_id", sa.String(200), nullable=False, unique=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("domain", sa.String(100), nullable=True),
        sa.Column("layer", sa.String(20), nullable=True),
        sa.Column("owner", sa.String(200), nullable=True),
        sa.Column("classification", sa.String(20), nullable=True),
        sa.Column("jurisdiction", sa.String(20), nullable=True),
        sa.Column("schema_definition", JSONB, server_default="{}"),
        sa.Column("quality_score", sa.Float, nullable=True),
        sa.Column("tags", JSONB, server_default="[]"),
        sa.Column("custom_properties", JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index("ix_dataset_metadata_domain", "dataset_metadata", ["domain"])
    op.create_index("ix_dataset_metadata_layer", "dataset_metadata", ["layer"])
    op.create_index("ix_dataset_metadata_classification", "dataset_metadata", ["classification"])

    op.create_table(
        "lineage_edges",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("source_dataset_id", sa.String(200), nullable=False),
        sa.Column("target_dataset_id", sa.String(200), nullable=False),
        sa.Column("job_name", sa.String(200), nullable=False),
        sa.Column("job_namespace", sa.String(200), server_default=""),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("facets", JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_lineage_edges_source", "lineage_edges", ["source_dataset_id"])
    op.create_index("ix_lineage_edges_target", "lineage_edges", ["target_dataset_id"])
    op.create_index("ix_lineage_edges_job", "lineage_edges", ["job_name"])


def downgrade() -> None:
    op.drop_index("ix_lineage_edges_job")
    op.drop_index("ix_lineage_edges_target")
    op.drop_index("ix_lineage_edges_source")
    op.drop_table("lineage_edges")
    op.drop_index("ix_dataset_metadata_classification")
    op.drop_index("ix_dataset_metadata_layer")
    op.drop_index("ix_dataset_metadata_domain")
    op.drop_table("dataset_metadata")
