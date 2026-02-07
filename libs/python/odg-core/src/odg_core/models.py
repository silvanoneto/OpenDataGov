"""Pydantic V2 domain models for OpenDataGov governance platform."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from odg_core.enums import (
    DataClassification,
    DecisionStatus,
    DecisionType,
    MedallionLayer,
    RACIRole,
    VetoStatus,
    VoteValue,
)


def _utcnow() -> datetime:
    return datetime.now(UTC)


class PromotionMetadata(BaseModel):
    """Promotion-specific metadata for governance decisions (ADR-024).

    Groups the fields that only apply to ``data_promotion`` decisions,
    keeping ``GovernanceDecision`` free of type-specific optional fields.
    """

    source_layer: MedallionLayer
    target_layer: MedallionLayer
    data_classification: DataClassification | None = None


class GovernanceDecision(BaseModel):
    """A governance decision requiring approval workflow (ADR-010)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    decision_type: DecisionType
    title: str = Field(min_length=1, max_length=500)
    description: str = Field(default="")
    status: DecisionStatus = Field(default=DecisionStatus.PENDING)
    domain_id: str = Field(min_length=1, max_length=100)
    created_by: str = Field(min_length=1, max_length=200)
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)
    metadata: dict[str, str | int | float | bool | None] = Field(default_factory=dict)

    # Promotion-specific fields (composed via PromotionMetadata)
    promotion: PromotionMetadata | None = None

    @model_validator(mode="before")
    @classmethod
    def _assemble_promotion(cls, data: Any) -> Any:
        """Support flat ORM rows alongside nested ``PromotionMetadata``.

        ORM rows and legacy dicts carry ``source_layer``, ``target_layer``,
        ``data_classification`` as top-level keys.  This validator folds
        them into a ``promotion`` sub-model so the domain layer always
        sees the composed form.
        """
        if isinstance(data, dict):
            sl = data.pop("source_layer", None)
            tl = data.pop("target_layer", None)
            dc = data.pop("data_classification", None)
            if sl is not None and tl is not None and "promotion" not in data:
                data["promotion"] = {
                    "source_layer": sl,
                    "target_layer": tl,
                    "data_classification": dc,
                }
            return data
        # ORM object — read flat attributes and re-emit as dict
        sl = getattr(data, "source_layer", None)
        tl = getattr(data, "target_layer", None)
        dc = getattr(data, "data_classification", None)
        md = getattr(data, "metadata_json", getattr(data, "metadata", {}))
        result: dict[str, Any] = {
            "id": getattr(data, "id", None),
            "decision_type": getattr(data, "decision_type", None),
            "title": getattr(data, "title", None),
            "description": getattr(data, "description", ""),
            "status": getattr(data, "status", None),
            "domain_id": getattr(data, "domain_id", None),
            "created_by": getattr(data, "created_by", None),
            "created_at": getattr(data, "created_at", None),
            "updated_at": getattr(data, "updated_at", None),
            "metadata": md,
        }
        if sl is not None and tl is not None:
            result["promotion"] = {
                "source_layer": sl,
                "target_layer": tl,
                "data_classification": dc,
            }
        return result


class ApprovalRecord(BaseModel):
    """An individual approval vote on a governance decision."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    decision_id: uuid.UUID
    voter_id: str = Field(min_length=1, max_length=200)
    voter_role: RACIRole
    vote: VoteValue
    comment: str = Field(default="")
    voted_at: datetime = Field(default_factory=_utcnow)


class VetoRecord(BaseModel):
    """A veto exercised on a governance decision (ADR-014).

    Time-bound: 24h for normal decisions, 1h for emergency.
    Can be overridden by a role with higher authority.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    decision_id: uuid.UUID
    vetoed_by: str = Field(min_length=1, max_length=200)
    vetoed_by_role: RACIRole
    reason: str = Field(min_length=1)
    status: VetoStatus = Field(default=VetoStatus.ACTIVE)
    vetoed_at: datetime = Field(default_factory=_utcnow)
    expires_at: datetime | None = None
    overridden_by: str | None = None
    overridden_at: datetime | None = None

    def compute_expiry(self, *, is_emergency: bool = False) -> datetime:
        """Compute the expiry time based on decision urgency."""
        timeout = timedelta(hours=1) if is_emergency else timedelta(hours=24)
        return self.vetoed_at + timeout

    @property
    def is_expired(self) -> bool:
        """Check if the veto has expired."""
        if self.status != VetoStatus.ACTIVE:
            return False
        if self.expires_at is None:
            return False
        return datetime.now(UTC) > self.expires_at


class RACIAssignment(BaseModel):
    """Assignment of a RACI role to a user for a domain (ADR-013)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    user_id: str = Field(min_length=1, max_length=200)
    domain_id: str = Field(min_length=1, max_length=100)
    role: RACIRole
    assigned_at: datetime = Field(default_factory=_utcnow)
    assigned_by: str = Field(min_length=1, max_length=200)


class ExpertRegistration(BaseModel):
    """Registration record for an AI expert in the system (ADR-034)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="")
    endpoint: str = Field(min_length=1)
    capabilities: list[str] = Field(default_factory=list)
    is_active: bool = Field(default=False)
    registered_at: datetime = Field(default_factory=_utcnow)
    approved_decision_id: uuid.UUID | None = None
