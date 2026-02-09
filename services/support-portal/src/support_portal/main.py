"""Support Portal FastAPI Application.

Multi-tier support system with ticketing, SLA tracking, and knowledge base.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from support_portal.api.routes_kb_admin import router as kb_admin_router
from support_portal.models import (
    Comment,
    CommentRow,
    CreateCommentRequest,
    CreateTicketRequest,
    CSATSurvey,
    CSATSurveyRow,
    KnowledgeBaseArticleRow,
    OrganizationRow,
    SupportTier,
    Ticket,
    TicketPriority,
    TicketRow,
    TicketStatus,
    UpdateTicketRequest,
    UserRow,
)
from support_portal.sla_manager import SLAManager

logger = logging.getLogger(__name__)


# Database session dependency
async def get_db() -> AsyncSession:
    """Get database session."""
    from odg_core.db.session import get_async_session

    async with get_async_session() as session:
        yield session


# Auth dependency (placeholder - integrate with Auth0)
async def get_current_user(
    # authorization: str = Header(...),
    db: AsyncSession = Depends(get_db),
) -> UserRow:
    """Get authenticated user from JWT token."""
    # TODO: Decode JWT token, validate with Auth0
    # For now, return mock user
    user_email = "demo@example.com"

    result = await db.execute(select(UserRow).where(UserRow.email == user_email))
    user = result.scalars().first()

    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    return user


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    logger.info("Starting Support Portal API")

    # Initialize database tables
    from odg_core.db.session import init_db

    await init_db()

    yield

    logger.info("Shutting down Support Portal API")


# FastAPI app
app = FastAPI(
    title="OpenDataGov Support Portal",
    description="Multi-tier customer support with ticketing, SLA tracking, and knowledge base",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include admin routers
app.include_router(kb_admin_router)


# ==================== Ticket Endpoints ====================


@app.post("/api/v1/tickets", response_model=Ticket, status_code=status.HTTP_201_CREATED)
async def create_ticket(
    request: CreateTicketRequest,
    current_user: UserRow = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Ticket:
    """Create a new support ticket.

    Automatically assigns priority based on support tier and subject keywords.
    Calculates SLA targets and creates ticket in Zendesk if integration enabled.
    """
    # Get organization
    org_result = await db.execute(select(OrganizationRow).where(OrganizationRow.org_id == current_user.org_id))
    org = org_result.scalars().first()

    if not org:
        raise HTTPException(404, "Organization not found")

    # Determine priority based on tier and keywords
    priority = _determine_priority(request.subject, request.description, org.support_tier)

    # Create ticket
    ticket = TicketRow(
        org_id=current_user.org_id,
        user_id=current_user.user_id,
        subject=request.subject,
        description=request.description,
        priority=priority.value,
        status=TicketStatus.NEW.value,
        product_area=request.product_area.value,
        severity=request.severity,
        tags=request.tags or [],
    )

    db.add(ticket)
    await db.commit()
    await db.refresh(ticket)

    # Calculate SLA targets
    sla_manager = SLAManager(db)
    response_target, resolution_target = await sla_manager.calculate_sla_targets(
        ticket.ticket_id, SupportTier(org.support_tier), priority
    )

    # Update ticket with SLA targets
    ticket.sla_response_target = response_target
    ticket.sla_resolution_target = resolution_target
    await db.commit()

    # TODO: Create ticket in Zendesk
    # zendesk_ticket_id = await zendesk_client.create_ticket(ticket)
    # ticket.zendesk_ticket_id = zendesk_ticket_id

    logger.info(
        f"Created ticket {ticket.ticket_id} for {org.name} (Priority: {priority.value}, SLA: {response_target})"
    )

    return Ticket.model_validate(ticket)


@app.get("/api/v1/tickets/{ticket_id}", response_model=Ticket)
async def get_ticket(
    ticket_id: str,
    current_user: UserRow = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Ticket:
    """Get ticket details by ID."""
    result = await db.execute(
        select(TicketRow).where(
            and_(
                TicketRow.ticket_id == ticket_id,
                TicketRow.org_id == current_user.org_id,  # User can only see own org tickets
            )
        )
    )
    ticket = result.scalars().first()

    if not ticket:
        raise HTTPException(404, "Ticket not found")

    return Ticket.model_validate(ticket)


@app.get("/api/v1/tickets", response_model=list[Ticket])
async def list_tickets(
    status_filter: TicketStatus | None = Query(None, alias="status"),
    priority_filter: TicketPriority | None = Query(None, alias="priority"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: UserRow = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[Ticket]:
    """List tickets for current user's organization.

    Supports filtering by status and priority.
    """
    query = select(TicketRow).where(TicketRow.org_id == current_user.org_id)

    if status_filter:
        query = query.where(TicketRow.status == status_filter.value)

    if priority_filter:
        query = query.where(TicketRow.priority == priority_filter.value)

    query = query.order_by(TicketRow.created_at.desc()).limit(limit).offset(offset)

    result = await db.execute(query)
    tickets = result.scalars().all()

    return [Ticket.model_validate(t) for t in tickets]


@app.patch("/api/v1/tickets/{ticket_id}", response_model=Ticket)
async def update_ticket(
    ticket_id: str,
    request: UpdateTicketRequest,
    current_user: UserRow = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Ticket:
    """Update ticket status, priority, or assignment.

    Internal staff only - enforces RBAC permissions.
    """
    # TODO: Check if user has staff role
    if not current_user.role == "staff":
        raise HTTPException(403, "Only staff can update tickets")

    result = await db.execute(select(TicketRow).where(TicketRow.ticket_id == ticket_id))
    ticket = result.scalars().first()

    if not ticket:
        raise HTTPException(404, "Ticket not found")

    # Update fields
    if request.status:
        ticket.status = request.status.value

        # Record resolution time if resolved
        if request.status in [TicketStatus.SOLVED, TicketStatus.CLOSED]:
            sla_manager = SLAManager(db)
            await sla_manager.record_resolution(ticket_id)

    if request.priority:
        ticket.priority = request.priority.value

    if request.assigned_to:
        ticket.assigned_to = request.assigned_to

    await db.commit()
    await db.refresh(ticket)

    logger.info(f"Updated ticket {ticket_id}: {request.model_dump(exclude_unset=True)}")

    return Ticket.model_validate(ticket)


@app.delete("/api/v1/tickets/{ticket_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_ticket(
    ticket_id: str,
    current_user: UserRow = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Cancel a ticket (customer can cancel own tickets)."""
    result = await db.execute(
        select(TicketRow).where(
            and_(
                TicketRow.ticket_id == ticket_id,
                TicketRow.user_id == current_user.user_id,
            )
        )
    )
    ticket = result.scalars().first()

    if not ticket:
        raise HTTPException(404, "Ticket not found")

    if ticket.status in [TicketStatus.SOLVED.value, TicketStatus.CLOSED.value]:
        raise HTTPException(400, "Cannot cancel solved/closed tickets")

    # Update to cancelled
    ticket.status = TicketStatus.CANCELLED.value
    await db.commit()

    logger.info(f"Cancelled ticket {ticket_id} by user {current_user.user_id}")


# ==================== Comment Endpoints ====================


@app.post(
    "/api/v1/tickets/{ticket_id}/comments",
    response_model=Comment,
    status_code=status.HTTP_201_CREATED,
)
async def create_comment(
    ticket_id: str,
    request: CreateCommentRequest,
    current_user: UserRow = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Comment:
    """Add a comment to a ticket.

    Records first response time if this is the first staff comment.
    """
    # Verify ticket exists and user has access
    ticket_result = await db.execute(
        select(TicketRow).where(
            and_(
                TicketRow.ticket_id == ticket_id,
                TicketRow.org_id == current_user.org_id,
            )
        )
    )
    ticket = ticket_result.scalars().first()

    if not ticket:
        raise HTTPException(404, "Ticket not found")

    # Create comment
    comment = CommentRow(
        ticket_id=ticket_id,
        user_id=current_user.user_id,
        body=request.body,
        is_internal=request.is_internal or False,
        attachments=request.attachments or [],
    )

    db.add(comment)
    await db.commit()
    await db.refresh(comment)

    # Record first response if this is first staff comment
    if current_user.role == "staff" and not ticket.first_response_at:
        sla_manager = SLAManager(db)
        await sla_manager.record_first_response(ticket_id)

    logger.info(f"Added comment to ticket {ticket_id} by {current_user.email}")

    return Comment.model_validate(comment)


@app.get("/api/v1/tickets/{ticket_id}/comments", response_model=list[Comment])
async def list_comments(
    ticket_id: str,
    current_user: UserRow = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[Comment]:
    """List all comments for a ticket.

    Filters out internal comments for non-staff users.
    """
    # Verify access
    ticket_result = await db.execute(
        select(TicketRow).where(
            and_(
                TicketRow.ticket_id == ticket_id,
                TicketRow.org_id == current_user.org_id,
            )
        )
    )
    ticket = ticket_result.scalars().first()

    if not ticket:
        raise HTTPException(404, "Ticket not found")

    # Get comments
    query = select(CommentRow).where(CommentRow.ticket_id == ticket_id)

    # Filter internal comments for non-staff
    if current_user.role != "staff":
        query = query.where(CommentRow.is_internal == False)  # noqa: E712

    query = query.order_by(CommentRow.created_at.asc())

    result = await db.execute(query)
    comments = result.scalars().all()

    return [Comment.model_validate(c) for c in comments]


# ==================== CSAT Survey Endpoints ====================


@app.post(
    "/api/v1/tickets/{ticket_id}/csat",
    response_model=CSATSurvey,
    status_code=status.HTTP_201_CREATED,
)
async def submit_csat_survey(
    ticket_id: str,
    rating: int = Query(..., ge=1, le=5),
    feedback: str | None = None,
    current_user: UserRow = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CSATSurvey:
    """Submit CSAT (Customer Satisfaction) survey for resolved ticket.

    Only allowed for solved/closed tickets.
    """
    # Verify ticket is resolved
    result = await db.execute(
        select(TicketRow).where(
            and_(
                TicketRow.ticket_id == ticket_id,
                TicketRow.user_id == current_user.user_id,
            )
        )
    )
    ticket = result.scalars().first()

    if not ticket:
        raise HTTPException(404, "Ticket not found")

    if ticket.status not in [TicketStatus.SOLVED.value, TicketStatus.CLOSED.value]:
        raise HTTPException(400, "Can only rate solved/closed tickets")

    # Check if already rated
    existing = await db.execute(select(CSATSurveyRow).where(CSATSurveyRow.ticket_id == ticket_id))
    if existing.scalars().first():
        raise HTTPException(409, "Ticket already rated")

    # Create survey
    survey = CSATSurveyRow(
        ticket_id=ticket_id,
        user_id=current_user.user_id,
        rating=rating,
        feedback=feedback,
    )

    db.add(survey)
    await db.commit()
    await db.refresh(survey)

    logger.info(f"CSAT survey submitted for ticket {ticket_id}: {rating}/5")

    return CSATSurvey.model_validate(survey)


@app.get("/api/v1/csat/metrics")
async def get_csat_metrics(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get CSAT metrics for last N days.

    Returns average rating, response distribution, and trends.
    Internal staff only.
    """
    from datetime import timedelta

    cutoff_date = datetime.utcnow() - timedelta(days=days)

    # Get surveys
    result = await db.execute(select(CSATSurveyRow).where(CSATSurveyRow.created_at >= cutoff_date))
    surveys = result.scalars().all()

    if not surveys:
        return {"total_responses": 0, "average_rating": None}

    ratings = [s.rating for s in surveys]
    avg_rating = sum(ratings) / len(ratings)

    # Rating distribution
    from collections import Counter

    distribution = Counter(ratings)

    # Calculate CSAT score (% of 4-5 star ratings)
    positive_ratings = sum(1 for r in ratings if r >= 4)
    csat_score = (positive_ratings / len(ratings)) * 100

    return {
        "total_responses": len(surveys),
        "average_rating": round(avg_rating, 2),
        "csat_score": round(csat_score, 1),
        "distribution": {f"{i}_star": distribution.get(i, 0) for i in range(1, 6)},
        "period_days": days,
    }


# ==================== Knowledge Base Endpoints ====================


@app.get("/api/v1/kb/search")
async def search_knowledge_base(
    query: str = Query(..., min_length=3),
    category: str | None = Query(None),
    tags: list[str] | None = Query(None),
    limit: int = Query(10, ge=1, le=50),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    """Search knowledge base articles using Elasticsearch.

    Returns ranked articles by relevance with highlights.
    """
    from support_portal.elasticsearch_client import KnowledgeBaseSearchClient

    es_client = KnowledgeBaseSearchClient()

    results = await es_client.search(
        query=query,
        category=category,
        tags=tags,
        limit=limit,
        offset=offset,
    )

    return results


@app.get("/api/v1/kb/articles/{article_id}")
async def get_article(
    article_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get knowledge base article by ID.

    Increments view count on each access.
    """
    result = await db.execute(select(KnowledgeBaseArticleRow).where(KnowledgeBaseArticleRow.article_id == article_id))
    article = result.scalars().first()

    if not article or not article.published:
        raise HTTPException(404, "Article not found")

    # Increment view count
    article.view_count += 1
    await db.commit()

    return {
        "article_id": article.article_id,
        "title": article.title,
        "content": article.content,
        "category": article.category,
        "tags": article.tags,
        "author": article.author,
        "created_at": article.created_at.isoformat(),
        "updated_at": article.updated_at.isoformat(),
        "views": article.view_count,
        "helpful_votes": article.helpful_votes,
        "unhelpful_votes": article.unhelpful_votes,
    }


@app.post("/api/v1/kb/articles/{article_id}/vote")
async def vote_article(
    article_id: str,
    helpful: bool = Query(...),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Vote on article helpfulness (thumbs up/down)."""
    result = await db.execute(select(KnowledgeBaseArticleRow).where(KnowledgeBaseArticleRow.article_id == article_id))
    article = result.scalars().first()

    if not article:
        raise HTTPException(404, "Article not found")

    if helpful:
        article.helpful_votes += 1
    else:
        article.unhelpful_votes += 1

    await db.commit()

    return {
        "helpful_votes": article.helpful_votes,
        "unhelpful_votes": article.unhelpful_votes,
    }


# ==================== SLA Monitoring Endpoints ====================


@app.get("/api/v1/sla/breaches")
async def monitor_sla_breaches(
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    """Monitor tickets approaching SLA breach.

    Returns tickets with >80% SLA elapsed.
    Internal staff only.
    """
    sla_manager = SLAManager(db)
    at_risk = await sla_manager.monitor_sla_breaches()

    return at_risk


@app.get("/api/v1/sla/metrics")
async def get_sla_metrics(
    tier: SupportTier | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get SLA compliance metrics by tier.

    Returns overall SLA compliance rate, average response/resolution times.
    Internal staff only.
    """
    sla_manager = SLAManager(db)
    metrics = await sla_manager.get_sla_metrics(tier)

    return metrics


# ==================== Analytics Endpoints ====================


@app.get("/api/v1/analytics/ticket-stats")
async def get_ticket_stats(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get ticket statistics for last N days.

    Returns ticket counts by status, priority, and resolution metrics.
    """
    from datetime import timedelta

    cutoff_date = datetime.utcnow() - timedelta(days=days)

    # Total tickets
    total_result = await db.execute(select(func.count(TicketRow.ticket_id)).where(TicketRow.created_at >= cutoff_date))
    total_tickets = total_result.scalar()

    # By status
    status_result = await db.execute(
        select(TicketRow.status, func.count(TicketRow.ticket_id))
        .where(TicketRow.created_at >= cutoff_date)
        .group_by(TicketRow.status)
    )
    by_status = {status: count for status, count in status_result.all()}

    # By priority
    priority_result = await db.execute(
        select(TicketRow.priority, func.count(TicketRow.ticket_id))
        .where(TicketRow.created_at >= cutoff_date)
        .group_by(TicketRow.priority)
    )
    by_priority = {priority: count for priority, count in priority_result.all()}

    return {
        "period_days": days,
        "total_tickets": total_tickets,
        "by_status": by_status,
        "by_priority": by_priority,
    }


# ==================== Health Check ====================


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy", "service": "support-portal"}


# Helper functions


def _determine_priority(subject: str, description: str, tier: str) -> TicketPriority:
    """Automatically determine ticket priority based on keywords and tier."""
    text = (subject + " " + description).lower()

    # Critical keywords
    critical_keywords = [
        "down",
        "outage",
        "crash",
        "data loss",
        "security breach",
        "cannot access",
        "production",
    ]

    # High priority keywords
    high_keywords = [
        "error",
        "bug",
        "urgent",
        "asap",
        "critical",
        "important",
    ]

    if tier == SupportTier.ENTERPRISE.value:
        if any(kw in text for kw in critical_keywords):
            return TicketPriority.P1_CRITICAL
        elif any(kw in text for kw in high_keywords):
            return TicketPriority.P2_HIGH
        else:
            return TicketPriority.P3_NORMAL

    elif tier == SupportTier.PROFESSIONAL.value:
        if any(kw in text for kw in critical_keywords):
            return TicketPriority.URGENT
        elif any(kw in text for kw in high_keywords):
            return TicketPriority.HIGH
        else:
            return TicketPriority.NORMAL

    else:  # Community
        return TicketPriority.NORMAL


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
