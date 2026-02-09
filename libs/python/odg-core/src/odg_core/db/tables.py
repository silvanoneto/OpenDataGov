"""SQLAlchemy 2.0 ORM mapped classes for OpenDataGov."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

_FK_GOVERNANCE_DECISION = "governance_decisions.id"
_CASCADE_ALL_DELETE_ORPHAN = "all, delete-orphan"


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

    approvals: Mapped[list[ApprovalRecordRow]] = relationship(
        back_populates="decision", cascade=_CASCADE_ALL_DELETE_ORPHAN
    )
    vetoes: Mapped[list[VetoRecordRow]] = relationship(back_populates="decision", cascade=_CASCADE_ALL_DELETE_ORPHAN)

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


class QualityReportRow(Base):
    """Quality gate evaluation reports (ADR-050)."""

    __tablename__ = "quality_reports"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    dataset_id: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    domain_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    layer: Mapped[str] = mapped_column(String(20), nullable=False)
    suite_name: Mapped[str] = mapped_column(String(200), nullable=False)
    dq_score: Mapped[float] = mapped_column(nullable=False)
    dimension_scores: Mapped[dict[str, object] | None] = mapped_column(JSONB, default=dict)
    expectations_passed: Mapped[int] = mapped_column(nullable=False, default=0)
    expectations_failed: Mapped[int] = mapped_column(nullable=False, default=0)
    expectations_total: Mapped[int] = mapped_column(nullable=False, default=0)
    report_details: Mapped[dict[str, object] | None] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    triggered_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey(_FK_GOVERNANCE_DECISION))

    __table_args__ = (Index("ix_quality_reports_dataset_layer", "dataset_id", "layer"),)


class QualitySLARow(Base):
    """Quality SLA thresholds per dimension (ADR-052)."""

    __tablename__ = "quality_slas"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    dataset_id: Mapped[str] = mapped_column(String(200), nullable=False)
    domain_id: Mapped[str] = mapped_column(String(100), nullable=False)
    dimension: Mapped[str] = mapped_column(String(30), nullable=False)
    threshold: Mapped[float] = mapped_column(nullable=False)
    owner_id: Mapped[str] = mapped_column(String(200), nullable=False)
    review_interval_days: Mapped[int] = mapped_column(nullable=False, default=90)
    last_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (Index("ix_quality_slas_dataset_dim", "dataset_id", "dimension", unique=True),)


class DataContractRow(Base):
    """Data contracts for datasets (ADR-051)."""

    __tablename__ = "data_contracts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    dataset_id: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    domain_id: Mapped[str] = mapped_column(String(100), nullable=False)
    owner_id: Mapped[str] = mapped_column(String(200), nullable=False)
    schema_definition: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=False)
    sla_definition: Mapped[dict[str, object] | None] = mapped_column(JSONB, default=dict)
    jurisdiction: Mapped[str | None] = mapped_column(String(20))
    version: Mapped[int] = mapped_column(nullable=False, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )

    versions: Mapped[list[ContractVersionRow]] = relationship(
        back_populates="contract", cascade=_CASCADE_ALL_DELETE_ORPHAN
    )

    __table_args__ = (Index("ix_data_contracts_domain", "domain_id"),)


class ContractVersionRow(Base):
    """Versioned snapshots of data contracts (ADR-051)."""

    __tablename__ = "contract_versions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    contract_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("data_contracts.id"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(nullable=False)
    schema_definition: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=False)
    change_type: Mapped[str] = mapped_column(String(30), nullable=False)
    changed_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    contract: Mapped[DataContractRow] = relationship(back_populates="versions")


class PipelineVersionRow(Base):
    """Versions of data pipelines (Kubeflow, Airflow, Spark, etc.)."""

    __tablename__ = "pipeline_versions"

    pipeline_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, primary_key=True)

    # DAG definition (KFP YAML, Airflow Python code structure, etc.)
    dag_definition: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=False)
    dag_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    git_commit: Mapped[str | None] = mapped_column(String(100))

    # Transformation code (SQL/Python)
    transformation_code: Mapped[str | None] = mapped_column(Text)
    transformation_hash: Mapped[str | None] = mapped_column(String(64))

    # Metadata
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    __table_args__ = (Index("ix_pipeline_active", "pipeline_id", "is_active"),)


class PipelineExecutionRow(Base):
    """Historical executions of data pipelines."""

    __tablename__ = "pipeline_executions"

    run_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    pipeline_id: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    pipeline_version: Mapped[int] = mapped_column(Integer, nullable=False)

    # Execution metadata
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int | None] = mapped_column(Integer)

    # Input/Output dataset tracking
    input_datasets: Mapped[list[dict[str, object]] | None] = mapped_column(JSONB)
    output_datasets: Mapped[list[dict[str, object]] | None] = mapped_column(JSONB)

    # Error tracking
    error_message: Mapped[str | None] = mapped_column(Text)
    error_stacktrace: Mapped[str | None] = mapped_column(Text)

    # Metrics
    rows_processed: Mapped[int | None] = mapped_column(BigInteger)
    bytes_processed: Mapped[int | None] = mapped_column(BigInteger)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    __table_args__ = (
        Index("ix_pipeline_executions_pipeline", "pipeline_id", "pipeline_version"),
        Index("ix_pipeline_executions_status", "status"),
        Index("ix_pipeline_executions_start_time", "start_time"),
    )


class LineageEventRow(Base):
    """OpenLineage events persisted to database for queryability.

    Stores lineage events from all jobs (Spark, Airflow, Kubeflow, etc.)
    for auditability and impact analysis.
    """

    __tablename__ = "lineage_events"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    event_type: Mapped[str] = mapped_column(String(20), nullable=False)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Job identification
    job_namespace: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    job_name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    run_id: Mapped[str] = mapped_column(String(200), nullable=False, index=True)

    # Lineage data
    inputs: Mapped[list[dict[str, object]] | None] = mapped_column(JSONB)
    outputs: Mapped[list[dict[str, object]] | None] = mapped_column(JSONB)

    # Facets (metadata)
    job_facets: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    run_facets: Mapped[dict[str, object] | None] = mapped_column(JSONB)

    # Producer info
    producer: Mapped[str | None] = mapped_column(String(200))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    __table_args__ = (
        Index("ix_lineage_events_job", "job_namespace", "job_name"),
        Index("ix_lineage_events_event_time", "event_time"),
        Index("ix_lineage_events_event_type", "event_type"),
    )


class FeastMaterializationRow(Base):
    """Tracks Feast feature materialization jobs with source lineage.

    Records which pipeline/dataset generated which feature version,
    enabling reproducibility and debugging of feature engineering.
    """

    __tablename__ = "feast_materializations"

    run_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    feature_view: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    feature_names: Mapped[list[str] | None] = mapped_column(JSONB)

    # Source lineage
    source_pipeline_id: Mapped[str | None] = mapped_column(String(200), index=True)
    source_pipeline_version: Mapped[int | None] = mapped_column(Integer)
    source_dataset_id: Mapped[str | None] = mapped_column(String(500))
    source_dataset_version: Mapped[str | None] = mapped_column(String(100))

    # Materialization window
    start_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    end_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    materialization_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Feature view version (hash of FeatureView definition)
    feature_view_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    __table_args__ = (
        Index("ix_feast_mat_feature_view", "feature_view"),
        Index("ix_feast_mat_source_pipeline", "source_pipeline_id", "source_pipeline_version"),
        Index("ix_feast_mat_time", "materialization_time"),
    )
