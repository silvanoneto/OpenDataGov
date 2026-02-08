"""Domain enums for OpenDataGov governance platform."""

from enum import StrEnum


class RACIRole(StrEnum):
    """RACI governance roles (ADR-013)."""

    RESPONSIBLE = "responsible"
    ACCOUNTABLE = "accountable"
    CONSULTED = "consulted"
    INFORMED = "informed"


class DataClassification(StrEnum):
    """Data classification levels (ADR-071)."""

    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"
    TOP_SECRET = "top_secret"


class MedallionLayer(StrEnum):
    """Medallion architecture layers (ADR-024)."""

    BRONZE = "bronze"
    SILVER = "silver"
    GOLD = "gold"
    PLATINUM = "platinum"


class DecisionType(StrEnum):
    """Types of governance decisions (ADR-010)."""

    DATA_PROMOTION = "data_promotion"
    SCHEMA_CHANGE = "schema_change"
    ACCESS_GRANT = "access_grant"
    EXPERT_REGISTRATION = "expert_registration"
    POLICY_CHANGE = "policy_change"
    EMERGENCY = "emergency"


class DecisionStatus(StrEnum):
    """Lifecycle states for governance decisions (ADR-010)."""

    PENDING = "pending"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    VETOED = "vetoed"
    ESCALATED = "escalated"


class VoteValue(StrEnum):
    """Possible vote values in approval workflows."""

    APPROVE = "approve"
    REJECT = "reject"
    ABSTAIN = "abstain"


class VetoStatus(StrEnum):
    """Status of a veto action (ADR-014)."""

    ACTIVE = "active"
    EXPIRED = "expired"
    OVERRIDDEN = "overridden"


class AuditEventType(StrEnum):
    """Types of auditable events."""

    DECISION_CREATED = "decision_created"
    DECISION_SUBMITTED = "decision_submitted"
    APPROVAL_CAST = "approval_cast"
    DECISION_APPROVED = "decision_approved"
    DECISION_REJECTED = "decision_rejected"
    VETO_EXERCISED = "veto_exercised"
    VETO_OVERRIDDEN = "veto_overridden"
    VETO_EXPIRED = "veto_expired"
    DECISION_ESCALATED = "decision_escalated"
    EXPERT_REGISTERED = "expert_registered"
    EXPERT_DEREGISTERED = "expert_deregistered"
    DATA_PROMOTED = "data_promoted"
    ROLE_ASSIGNED = "role_assigned"
    ROLE_REVOKED = "role_revoked"


class ExpertCapability(StrEnum):
    """Capabilities that an AI expert can provide (ADR-034)."""

    SQL_GENERATION = "sql_generation"
    DATA_ANALYSIS = "data_analysis"
    DATA_PROFILING = "data_profiling"
    SCHEMA_INFERENCE = "schema_inference"
    METADATA_DISCOVERY = "metadata_discovery"


class DAMADimension(StrEnum):
    """DAMA DMBOK data quality dimensions (ADR-052)."""

    COMPLETENESS = "completeness"
    ACCURACY = "accuracy"
    CONSISTENCY = "consistency"
    TIMELINESS = "timeliness"
    UNIQUENESS = "uniqueness"
    VALIDITY = "validity"


class ComplianceFramework(StrEnum):
    """Supported compliance frameworks (ADR-110)."""

    LGPD = "lgpd"
    GDPR = "gdpr"
    EU_AI_ACT = "eu_ai_act"
    NIST_AI_RMF = "nist_ai_rmf"
    ISO_42001 = "iso_42001"
    SOX = "sox"
    DAMA_DMBOK = "dama_dmbok"


class AIRiskLevel(StrEnum):
    """EU AI Act risk classification levels (ADR-111)."""

    HIGH = "high"
    LIMITED = "limited"
    MINIMAL = "minimal"


class Jurisdiction(StrEnum):
    """Data jurisdiction for residency and compliance (ADR-074)."""

    BR = "br"
    EU = "eu"
    US = "us"
    GLOBAL = "global"
