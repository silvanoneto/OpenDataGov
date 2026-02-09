"""GraphQL resolvers for governance decisions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from odg_core.db.tables import GovernanceDecisionRow
from odg_core.graphql.types.decision import GovernanceDecisionGQL, PromotionMetadataGQL
from odg_core.models import GovernanceDecision

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession


async def get_decision(session: AsyncSession, decision_id: uuid.UUID) -> GovernanceDecisionGQL | None:
    """Resolve single decision by ID."""
    stmt = select(GovernanceDecisionRow).where(GovernanceDecisionRow.id == decision_id)
    result = await session.execute(stmt)
    row = result.scalar_one_or_none()

    if row is None:
        return None

    # Convert ORM row to Pydantic model
    decision = GovernanceDecision.model_validate(row)

    # Convert to GraphQL type
    return GovernanceDecisionGQL(
        id=decision.id,
        decision_type=decision.decision_type.value,
        title=decision.title,
        description=decision.description,
        status=decision.status.value,
        domain_id=decision.domain_id,
        created_by=decision.created_by,
        created_at=decision.created_at,
        updated_at=decision.updated_at,
        promotion=(
            PromotionMetadataGQL(
                source_layer=decision.promotion.source_layer.value,
                target_layer=decision.promotion.target_layer.value,
                data_classification=(
                    decision.promotion.data_classification.value if decision.promotion.data_classification else None
                ),
            )
            if decision.promotion
            else None
        ),
    )


async def list_decisions(
    session: AsyncSession,
    domain: str | None = None,
    status: str | None = None,
    limit: int = 10,
) -> list[GovernanceDecisionGQL]:
    """Resolve list of decisions with filters."""
    stmt = select(GovernanceDecisionRow)

    # Apply filters
    if domain:
        stmt = stmt.where(GovernanceDecisionRow.domain_id == domain)
    if status:
        stmt = stmt.where(GovernanceDecisionRow.status == status)

    # Order by created_at desc and limit
    stmt = stmt.order_by(GovernanceDecisionRow.created_at.desc()).limit(limit)

    result = await session.execute(stmt)
    rows = result.scalars().all()

    # Convert all rows to GraphQL types
    decisions = []
    for row in rows:
        decision = GovernanceDecision.model_validate(row)
        decisions.append(
            GovernanceDecisionGQL(
                id=decision.id,
                decision_type=decision.decision_type.value,
                title=decision.title,
                description=decision.description,
                status=decision.status.value,
                domain_id=decision.domain_id,
                created_by=decision.created_by,
                created_at=decision.created_at,
                updated_at=decision.updated_at,
                promotion=(
                    PromotionMetadataGQL(
                        source_layer=decision.promotion.source_layer.value,
                        target_layer=decision.promotion.target_layer.value,
                        data_classification=(
                            decision.promotion.data_classification.value
                            if decision.promotion.data_classification
                            else None
                        ),
                    )
                    if decision.promotion
                    else None
                ),
            )
        )

    return decisions
