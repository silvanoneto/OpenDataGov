"""Data contracts and versioned snapshots.

Revision ID: 004
Revises: 003
Create Date: 2026-02-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "004"
down_revision: str | None = "003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "data_contracts",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("name", sa.String(200), nullable=False, unique=True),
        sa.Column("dataset_id", sa.String(200), nullable=False),
        sa.Column("domain_id", sa.String(100), nullable=False),
        sa.Column("owner_id", sa.String(200), nullable=False),
        sa.Column("schema_definition", JSONB, nullable=False),
        sa.Column("sla_definition", JSONB, server_default="{}"),
        sa.Column("jurisdiction", sa.String(20), nullable=True),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_data_contracts_dataset_id", "data_contracts", ["dataset_id"])
    op.create_index("ix_data_contracts_domain", "data_contracts", ["domain_id"])

    op.create_table(
        "contract_versions",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("contract_id", sa.Uuid, sa.ForeignKey("data_contracts.id"), nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("schema_definition", JSONB, nullable=False),
        sa.Column("change_type", sa.String(30), nullable=False),
        sa.Column("changed_by", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_contract_versions_contract_id", "contract_versions", ["contract_id"])


def downgrade() -> None:
    op.drop_index("ix_contract_versions_contract_id")
    op.drop_table("contract_versions")
    op.drop_index("ix_data_contracts_domain")
    op.drop_index("ix_data_contracts_dataset_id")
    op.drop_table("data_contracts")
