"""API request/response schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from odg_core.enums import (
    DecisionStatus,
    DecisionType,
    RACIRole,
    VetoStatus,
    VoteValue,
)
from odg_core.models import PromotionMetadata
from pydantic import BaseModel, Field

# ─── Decision schemas ────────────────────────────────────


class CreateDecisionRequest(BaseModel):
    decision_type: DecisionType
    title: str = Field(min_length=1, max_length=500)
    description: str = Field(default="")
    domain_id: str = Field(min_length=1, max_length=100)
    created_by: str = Field(min_length=1, max_length=200)
    promotion: PromotionMetadata | None = None
    metadata: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class DecisionResponse(BaseModel):
    id: uuid.UUID
    decision_type: DecisionType
    title: str
    description: str
    status: DecisionStatus
    domain_id: str
    created_by: str
    created_at: datetime
    updated_at: datetime
    promotion: PromotionMetadata | None = None


class SubmitDecisionRequest(BaseModel):
    actor_id: str = Field(min_length=1, max_length=200)


# ─── Approval schemas ────────────────────────────────────


class CastVoteRequest(BaseModel):
    voter_id: str = Field(min_length=1, max_length=200)
    vote: VoteValue
    comment: str = Field(default="")


class ApprovalResponse(BaseModel):
    id: uuid.UUID
    decision_id: uuid.UUID
    voter_id: str
    voter_role: RACIRole
    vote: VoteValue
    comment: str
    voted_at: datetime


# ─── Veto schemas ─────────────────────────────────────────


class ExerciseVetoRequest(BaseModel):
    vetoed_by: str = Field(min_length=1, max_length=200)
    reason: str = Field(min_length=1)


class OverrideVetoRequest(BaseModel):
    overridden_by: str = Field(min_length=1, max_length=200)


class VetoResponse(BaseModel):
    id: uuid.UUID
    decision_id: uuid.UUID
    vetoed_by: str
    vetoed_by_role: RACIRole
    reason: str
    status: VetoStatus
    vetoed_at: datetime
    expires_at: datetime | None = None
    overridden_by: str | None = None
    overridden_at: datetime | None = None


# ─── Role schemas ─────────────────────────────────────────


class AssignRoleRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=200)
    domain_id: str = Field(min_length=1, max_length=100)
    role: RACIRole
    assigned_by: str = Field(min_length=1, max_length=200)


class RoleAssignmentResponse(BaseModel):
    id: uuid.UUID
    user_id: str
    domain_id: str
    role: RACIRole
    assigned_at: datetime
    assigned_by: str


# ─── Audit schemas ────────────────────────────────────────


class AuditEventResponse(BaseModel):
    id: uuid.UUID
    event_type: str
    entity_type: str
    entity_id: str
    actor_id: str
    description: str
    occurred_at: datetime
    event_hash: str


class AuditVerifyResponse(BaseModel):
    is_valid: bool
