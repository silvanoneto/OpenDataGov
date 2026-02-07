"""SQLAlchemy 2.0 ORM mapped classes for OpenDataGov."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

_FK_GOVERNANCE_DECISION = "governance_decisions.id"


class Base(DeclarativeBase):
    """Base class for all ORM models."""


class GovernanceDecisionRow(Base):
    __tablename__ = "governance_decisions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    decision_type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    domain_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )
    metadata_json: Mapped[dict[str, object] | None] = mapped_column("metadata", JSONB, default=dict)
    source_layer: Mapped[str | None] = mapped_column(String(20))
    target_layer: Mapped[str | None] = mapped_column(String(20))
    data_classification: Mapped[str | None] = mapped_column(String(20))

    approvals: Mapped[list[ApprovalRecordRow]] = relationship(back_populates="decision", cascade="all, delete-orphan")
    vetoes: Mapped[list[VetoRecordRow]] = relationship(back_populates="decision", cascade="all, delete-orphan")

    __table_args__ = (Index("ix_decisions_status_domain", "status", "domain_id"),)


class ApprovalRecordRow(Base):
    __tablename__ = "approval_records"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    decision_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(_FK_GOVERNANCE_DECISION), nullable=False, index=True)
    voter_id: Mapped[str] = mapped_column(String(200), nullable=False)
    voter_role: Mapped[str] = mapped_column(String(20), nullable=False)
    vote: Mapped[str] = mapped_column(String(10), nullable=False)
    comment: Mapped[str] = mapped_column(Text, default="")
    voted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    decision: Mapped[GovernanceDecisionRow] = relationship(back_populates="approvals")


class VetoRecordRow(Base):
    __tablename__ = "veto_records"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    decision_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(_FK_GOVERNANCE_DECISION), nullable=False, index=True)
    vetoed_by: Mapped[str] = mapped_column(String(200), nullable=False)
    vetoed_by_role: Mapped[str] = mapped_column(String(20), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    vetoed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    overridden_by: Mapped[str | None] = mapped_column(String(200))
    overridden_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    decision: Mapped[GovernanceDecisionRow] = relationship(back_populates="vetoes")


class AuditEventRow(Base):
    """Append-only audit events with hash chain.

    PostgreSQL trigger prevents UPDATE and DELETE on this table.
    """

    __tablename__ = "audit_events"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    actor_id: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    details: Mapped[dict[str, object] | None] = mapped_column(JSONB, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    previous_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    event_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    __table_args__ = (Index("ix_audit_events_occurred", "occurred_at"),)


class RACIAssignmentRow(Base):
    __tablename__ = "raci_assignments"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    domain_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    assigned_by: Mapped[str] = mapped_column(String(200), nullable=False)

    __table_args__ = (Index("ix_raci_user_domain", "user_id", "domain_id", unique=True),)


class ExpertRegistryRow(Base):
    __tablename__ = "expert_registry"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    endpoint: Mapped[str] = mapped_column(String(500), nullable=False)
    capabilities: Mapped[list[str] | None] = mapped_column(JSONB, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    registered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    approved_decision_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey(_FK_GOVERNANCE_DECISION))
