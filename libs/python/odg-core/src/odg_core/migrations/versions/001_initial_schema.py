"""Initial schema: governance, audit, RACI, expert registry.

Revision ID: 001
Revises:
Create Date: 2026-02-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

_FK_GOVERNANCE_DECISION = "governance_decisions.id"

revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Governance decisions
    op.create_table(
        "governance_decisions",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("decision_type", sa.String(50), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text, server_default=""),
        sa.Column("status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("domain_id", sa.String(100), nullable=False),
        sa.Column("created_by", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("metadata", JSONB, server_default="{}"),
        sa.Column("source_layer", sa.String(20)),
        sa.Column("target_layer", sa.String(20)),
        sa.Column("data_classification", sa.String(20)),
    )
    op.create_index("ix_decisions_domain_id", "governance_decisions", ["domain_id"])
    op.create_index("ix_decisions_status_domain", "governance_decisions", ["status", "domain_id"])

    # Approval records
    op.create_table(
        "approval_records",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("decision_id", sa.Uuid, sa.ForeignKey(_FK_GOVERNANCE_DECISION), nullable=False),
        sa.Column("voter_id", sa.String(200), nullable=False),
        sa.Column("voter_role", sa.String(20), nullable=False),
        sa.Column("vote", sa.String(10), nullable=False),
        sa.Column("comment", sa.Text, server_default=""),
        sa.Column("voted_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_approval_decision_id", "approval_records", ["decision_id"])

    # Veto records
    op.create_table(
        "veto_records",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("decision_id", sa.Uuid, sa.ForeignKey(_FK_GOVERNANCE_DECISION), nullable=False),
        sa.Column("vetoed_by", sa.String(200), nullable=False),
        sa.Column("vetoed_by_role", sa.String(20), nullable=False),
        sa.Column("reason", sa.Text, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("vetoed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("overridden_by", sa.String(200)),
        sa.Column("overridden_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_veto_decision_id", "veto_records", ["decision_id"])

    # Audit events (append-only)
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("entity_type", sa.String(100), nullable=False),
        sa.Column("entity_id", sa.String(200), nullable=False),
        sa.Column("actor_id", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, server_default=""),
        sa.Column("details", JSONB, server_default="{}"),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("previous_hash", sa.String(64), nullable=False),
        sa.Column("event_hash", sa.String(64), nullable=False),
    )
    op.create_index("ix_audit_event_type", "audit_events", ["event_type"])
    op.create_index("ix_audit_entity_id", "audit_events", ["entity_id"])
    op.create_index("ix_audit_actor_id", "audit_events", ["actor_id"])
    op.create_index("ix_audit_events_occurred", "audit_events", ["occurred_at"])

    # Immutability trigger: prevent UPDATE and DELETE on audit_events
    op.execute("""
        CREATE OR REPLACE FUNCTION prevent_audit_mutation()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION 'audit_events table is append-only: % operations are not allowed', TG_OP;
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER trg_audit_events_immutable
        BEFORE UPDATE OR DELETE ON audit_events
        FOR EACH ROW
        EXECUTE FUNCTION prevent_audit_mutation();
    """)

    # RACI assignments
    op.create_table(
        "raci_assignments",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("user_id", sa.String(200), nullable=False),
        sa.Column("domain_id", sa.String(100), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("assigned_by", sa.String(200), nullable=False),
    )
    op.create_index("ix_raci_user_id", "raci_assignments", ["user_id"])
    op.create_index("ix_raci_domain_id", "raci_assignments", ["domain_id"])
    op.create_index("ix_raci_user_domain", "raci_assignments", ["user_id", "domain_id"], unique=True)

    # Expert registry
    op.create_table(
        "expert_registry",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("name", sa.String(200), nullable=False, unique=True),
        sa.Column("description", sa.Text, server_default=""),
        sa.Column("endpoint", sa.String(500), nullable=False),
        sa.Column("capabilities", JSONB, server_default="[]"),
        sa.Column("is_active", sa.Boolean, server_default="false"),
        sa.Column("registered_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("approved_decision_id", sa.Uuid, sa.ForeignKey(_FK_GOVERNANCE_DECISION)),
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_audit_events_immutable ON audit_events")
    op.execute("DROP FUNCTION IF EXISTS prevent_audit_mutation()")
    op.drop_table("expert_registry")
    op.drop_table("raci_assignments")
    op.drop_table("audit_events")
    op.drop_table("veto_records")
    op.drop_table("approval_records")
    op.drop_table("governance_decisions")
