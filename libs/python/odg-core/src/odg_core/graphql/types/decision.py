"""GraphQL types for governance decisions."""

import uuid
from datetime import datetime

import strawberry


@strawberry.type
class PromotionMetadataGQL:
    """Promotion metadata for data_promotion decisions."""

    source_layer: str
    target_layer: str
    data_classification: str | None = None


@strawberry.type
class GovernanceDecisionGQL:
    """A governance decision requiring approval workflow (ADR-010)."""

    id: uuid.UUID
    decision_type: str
    title: str
    description: str
    status: str
    domain_id: str
    created_by: str
    created_at: datetime
    updated_at: datetime
    promotion: PromotionMetadataGQL | None = None


@strawberry.type
class ApprovalRecordGQL:
    """An approval or rejection vote on a decision."""

    id: uuid.UUID
    decision_id: uuid.UUID
    user_id: str
    role: str
    vote: str
    comment: str
    voted_at: datetime
