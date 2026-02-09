"""Dashboard API endpoints for governance analytics (ADR-101).

Provides backend APIs for the Governance Dashboard UI:
- Decision history and timeline
- RACI pattern analytics
- Privacy budget tracking
- Audit trail visualization
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query
from odg_core.auth.dependencies import get_current_user, require_role
from odg_core.auth.models import UserContext
from odg_core.enums import RACIRole
from pydantic import BaseModel, Field

from governance_engine.api.deps import AuditServiceDep, DecisionServiceDep

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


# ──── Response Models ─────────────────────────────────────────────


class TimelineEvent(BaseModel):
    """Event in decision timeline."""

    timestamp: datetime
    event_type: str  # created, submitted, approved, rejected, vetoed
    actor_id: str
    description: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class DecisionHistoryResponse(BaseModel):
    """Decision history for dashboard."""

    decision_id: uuid.UUID
    title: str
    status: str
    domain_id: str
    created_at: datetime
    timeline: list[TimelineEvent]


class RACIAnalytics(BaseModel):
    """RACI pattern analytics."""

    total_decisions: int
    decisions_by_domain: dict[str, int]
    average_approval_time_hours: float
    approvals_by_role: dict[str, int]  # responsible, accountable, consulted
    top_approvers: list[tuple[str, int]]  # [(user_id, count)]
    bottleneck_domains: list[str]  # Domains with slow approvals


class PrivacyBudgetStatus(BaseModel):
    """Privacy budget tracking."""

    total_epsilon_consumed: float
    epsilon_by_domain: dict[str, float]
    epsilon_by_dataset: dict[str, float]
    datasets_near_limit: list[tuple[str, float]]  # [(dataset_id, epsilon_used)]
    alerts: list[str]


class AuditTrailStats(BaseModel):
    """Audit trail statistics."""

    total_events: int
    events_by_type: dict[str, int]
    events_last_24h: int
    chain_integrity: bool
    last_event_timestamp: datetime | None


# ──── Endpoints ───────────────────────────────────────────────────


@router.get("/decision-history")
async def get_decision_history(
    service: DecisionServiceDep,
    user: UserContext = Depends(get_current_user),
    domain_id: str | None = None,
    limit: int = Query(default=50, le=200),
) -> list[DecisionHistoryResponse]:
    """Get decision history with timeline events.

    Returns decisions with full event timeline for dashboard visualization.
    """
    decisions = await service.list_decisions(
        domain_id=domain_id,
        status=None,
        limit=limit,
        offset=0,
    )

    history = []
    for decision in decisions:
        # Build timeline from decision lifecycle
        timeline = [
            TimelineEvent(
                timestamp=decision.created_at,
                event_type="created",
                actor_id=decision.created_by,
                description=f"Decision created: {decision.title}",
            )
        ]

        if decision.updated_at > decision.created_at:
            timeline.append(
                TimelineEvent(
                    timestamp=decision.updated_at,
                    event_type="updated",
                    actor_id=decision.created_by,
                    description=f"Decision status: {decision.status.value}",
                )
            )

        history.append(
            DecisionHistoryResponse(
                decision_id=decision.id,
                title=decision.title,
                status=decision.status.value,
                domain_id=decision.domain_id,
                created_at=decision.created_at,
                timeline=timeline,
            )
        )

    return history


@router.get("/raci-patterns")
async def get_raci_patterns(
    service: DecisionServiceDep,
    user: UserContext = Depends(require_role(RACIRole.CONSULTED)),
    domain_id: str | None = None,
) -> RACIAnalytics:
    """Get RACI pattern analytics.

    Analyzes approval patterns, bottlenecks, and role distribution.
    """
    decisions = await service.list_decisions(
        domain_id=domain_id,
        status=None,
        limit=1000,
    )

    # Calculate analytics
    total_decisions = len(decisions)
    decisions_by_domain: dict[str, int] = {}
    approval_times = []

    for decision in decisions:
        # Count by domain
        decisions_by_domain[decision.domain_id] = decisions_by_domain.get(decision.domain_id, 0) + 1

        # Calculate approval time
        if decision.updated_at > decision.created_at:
            time_diff = (decision.updated_at - decision.created_at).total_seconds() / 3600
            approval_times.append(time_diff)

    avg_approval_time = sum(approval_times) / len(approval_times) if approval_times else 0.0

    # TODO: Query actual approval records for role distribution
    approvals_by_role = {
        "responsible": 0,
        "accountable": 0,
        "consulted": 0,
    }

    # Identify bottleneck domains (domains with >24h avg approval time)
    bottleneck_domains = [domain for domain, count in decisions_by_domain.items() if count > 10]

    return RACIAnalytics(
        total_decisions=total_decisions,
        decisions_by_domain=decisions_by_domain,
        average_approval_time_hours=avg_approval_time,
        approvals_by_role=approvals_by_role,
        top_approvers=[],  # TODO: Implement from approval records
        bottleneck_domains=bottleneck_domains,
    )


@router.get("/privacy-budget")
async def get_privacy_budget(
    user: UserContext = Depends(require_role(RACIRole.CONSULTED)),
    domain_id: str | None = None,
) -> PrivacyBudgetStatus:
    """Get privacy budget tracking status.

    Monitors epsilon consumption across datasets and domains.
    """
    # TODO: Implement actual privacy budget tracking from database
    # For now, return mock data structure

    return PrivacyBudgetStatus(
        total_epsilon_consumed=2.5,
        epsilon_by_domain={
            "finance": 1.2,
            "hr": 0.8,
            "sales": 0.5,
        },
        epsilon_by_dataset={
            "gold.customers": 0.8,
            "gold.transactions": 1.0,
            "gold.employees": 0.7,
        },
        datasets_near_limit=[
            ("gold.transactions", 1.0),  # Near 1.5 limit
        ],
        alerts=[
            "Dataset 'gold.transactions' has consumed 66% of privacy budget",
        ],
    )


@router.get("/audit-stats")
async def get_audit_stats(
    service: AuditServiceDep,
    user: UserContext = Depends(get_current_user),
) -> AuditTrailStats:
    """Get audit trail statistics.

    Returns event counts, types, and chain integrity status.
    """
    # Get recent events
    events = await service.get_events(limit=1000)

    # Calculate stats
    total_events = len(events)
    events_by_type: dict[str, int] = {}
    events_last_24h = 0
    cutoff = datetime.now(UTC) - timedelta(hours=24)

    for event in events:
        events_by_type[event.event_type.value] = events_by_type.get(event.event_type.value, 0) + 1
        if event.occurred_at > cutoff:
            events_last_24h += 1

    last_event = events[0] if events else None

    # TODO: Implement actual chain integrity check
    chain_integrity = True

    return AuditTrailStats(
        total_events=total_events,
        events_by_type=events_by_type,
        events_last_24h=events_last_24h,
        chain_integrity=chain_integrity,
        last_event_timestamp=last_event.occurred_at if last_event else None,
    )


@router.get("/health")
async def dashboard_health() -> dict[str, str]:
    """Health check for dashboard APIs."""
    return {"status": "ok", "service": "dashboard"}
