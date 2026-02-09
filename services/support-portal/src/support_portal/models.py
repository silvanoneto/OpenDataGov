"""Support Portal - Database models and schemas."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field
from sqlalchemy import JSON, Boolean, Column, DateTime, Float, Integer, String, Text
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class SupportTier(StrEnum):
    """Support tier levels."""

    COMMUNITY = "community"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


class TicketPriority(StrEnum):
    """Ticket priority levels."""

    # Enterprise priorities
    P1_CRITICAL = "P1"  # Production down, 4h SLA
    P2_HIGH = "P2"  # Major feature broken, 8h SLA
    P3_NORMAL = "P3"  # Minor issue, 24h SLA
    P4_LOW = "P4"  # Enhancement, 48h SLA

    # Professional priorities
    URGENT = "urgent"  # 8h SLA
    HIGH = "high"  # 24h SLA
    NORMAL = "normal"  # 48h SLA

    # Community (no SLA)
    COMMUNITY = "community"


class TicketStatus(StrEnum):
    """Ticket status."""

    NEW = "new"
    OPEN = "open"
    PENDING = "pending"  # Waiting for customer
    ON_HOLD = "on_hold"
    SOLVED = "solved"
    CLOSED = "closed"


class ProductArea(StrEnum):
    """Product areas for categorization."""

    DATA_CATALOG = "data_catalog"
    GOVERNANCE = "governance"
    QUALITY = "quality"
    LINEAGE = "lineage"
    GPU_CLUSTER = "gpu_cluster"
    FEDERATION = "federation"
    MLOPS = "mlops"
    INFRASTRUCTURE = "infrastructure"
    OTHER = "other"


# Database Tables


class OrganizationRow(Base):
    """Organization/customer table."""

    __tablename__ = "organizations"

    org_id = Column(String, primary_key=True)
    org_name = Column(String, nullable=False)
    support_tier = Column(String, nullable=False, default=SupportTier.COMMUNITY.value)

    # Billing
    stripe_customer_id = Column(String, nullable=True)
    subscription_status = Column(String, nullable=True)  # active, cancelled, past_due
    monthly_rate_usd = Column(Float, nullable=True)

    # Support allocation
    support_hours_included = Column(Integer, nullable=True)  # Professional: 40h/month
    support_hours_used = Column(Integer, nullable=False, default=0)
    support_hours_reset_date = Column(DateTime, nullable=True)

    # Enterprise features
    has_slack_channel = Column(Boolean, nullable=False, default=False)
    slack_channel_id = Column(String, nullable=True)
    dedicated_csm = Column(String, nullable=True)  # Customer Success Manager
    next_qbr_date = Column(DateTime, nullable=True)  # Quarterly Business Review

    # Metadata
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class UserRow(Base):
    """User table."""

    __tablename__ = "users"

    user_id = Column(String, primary_key=True)
    email = Column(String, nullable=False, unique=True, index=True)
    name = Column(String, nullable=False)
    org_id = Column(String, nullable=False, index=True)

    # Auth
    auth0_user_id = Column(String, nullable=True, unique=True)
    is_verified = Column(Boolean, nullable=False, default=False)

    # Role
    is_admin = Column(Boolean, nullable=False, default=False)  # Org admin
    can_create_tickets = Column(Boolean, nullable=False, default=True)

    # Metadata
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_login_at = Column(DateTime, nullable=True)


class TicketRow(Base):
    """Ticket table (synced with Zendesk)."""

    __tablename__ = "tickets"

    ticket_id = Column(String, primary_key=True)  # Zendesk ticket ID
    org_id = Column(String, nullable=False, index=True)
    user_id = Column(String, nullable=False, index=True)

    # Content
    subject = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    priority = Column(String, nullable=False)
    status = Column(String, nullable=False, default=TicketStatus.NEW.value)

    # Categorization
    product_area = Column(String, nullable=True)
    opendatagov_version = Column(String, nullable=True)
    environment = Column(String, nullable=True)  # production, staging, development

    # SLA
    sla_target_first_response = Column(DateTime, nullable=True)
    sla_target_resolution = Column(DateTime, nullable=True)
    first_response_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    sla_breached = Column(Boolean, nullable=False, default=False)

    # Assignment
    assigned_to = Column(String, nullable=True)  # Support agent email
    escalated_to = Column(String, nullable=True)  # Manager/VP email

    # Zendesk sync
    zendesk_ticket_id = Column(Integer, nullable=True, unique=True)
    zendesk_url = Column(String, nullable=True)
    last_synced_at = Column(DateTime, nullable=True)

    # Metadata
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class CommentRow(Base):
    """Ticket comments."""

    __tablename__ = "comments"

    comment_id = Column(String, primary_key=True)
    ticket_id = Column(String, nullable=False, index=True)
    user_id = Column(String, nullable=True)  # None if internal comment

    # Content
    body = Column(Text, nullable=False)
    is_public = Column(Boolean, nullable=False, default=True)

    # Metadata
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class CSATSurveyRow(Base):
    """Customer Satisfaction survey responses."""

    __tablename__ = "csat_surveys"

    survey_id = Column(String, primary_key=True)
    ticket_id = Column(String, nullable=False, index=True)
    org_id = Column(String, nullable=False, index=True)

    # Survey
    score = Column(Integer, nullable=False)  # 1-5 stars
    feedback = Column(Text, nullable=True)

    # Metadata
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class KnowledgeBaseArticleRow(Base):
    """Knowledge base articles."""

    __tablename__ = "kb_articles"

    article_id = Column(String, primary_key=True)
    title = Column(String, nullable=False)
    slug = Column(String, nullable=False, unique=True, index=True)
    content = Column(Text, nullable=False)

    # Categorization
    category = Column(String, nullable=False)  # Getting Started, Deployment, etc.
    tags = Column(JSON, nullable=True)  # ["kubernetes", "helm", "aws"]
    product_area = Column(String, nullable=True)

    # Status
    is_published = Column(Boolean, nullable=False, default=False)
    author = Column(String, nullable=False)

    # Analytics
    view_count = Column(Integer, nullable=False, default=0)
    helpful_count = Column(Integer, nullable=False, default=0)
    not_helpful_count = Column(Integer, nullable=False, default=0)

    # Search
    search_vector = Column(Text, nullable=True)  # PostgreSQL tsvector

    # Metadata
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


# Pydantic Models for API


class Organization(BaseModel):
    """Organization schema."""

    org_id: str
    org_name: str
    support_tier: SupportTier
    monthly_rate_usd: float | None
    support_hours_included: int | None
    support_hours_used: int
    has_slack_channel: bool
    dedicated_csm: str | None

    class Config:
        from_attributes = True


class CreateTicketRequest(BaseModel):
    """Request to create a ticket."""

    subject: str = Field(..., min_length=10, max_length=200)
    description: str = Field(..., min_length=50)
    priority: TicketPriority
    product_area: ProductArea | None = None
    opendatagov_version: str | None = None
    environment: str | None = None
    attachments: list[str] = Field(default_factory=list)  # S3 URLs


class Ticket(BaseModel):
    """Ticket response."""

    ticket_id: str
    subject: str
    description: str
    priority: TicketPriority
    status: TicketStatus
    product_area: str | None
    sla_target_first_response: datetime | None
    sla_target_resolution: datetime | None
    first_response_at: datetime | None
    resolved_at: datetime | None
    sla_breached: bool
    zendesk_url: str | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class Comment(BaseModel):
    """Comment schema."""

    comment_id: str
    ticket_id: str
    user_id: str | None
    body: str
    is_public: bool
    created_at: datetime

    class Config:
        from_attributes = True


class CSATSurvey(BaseModel):
    """CSAT survey response."""

    score: int = Field(ge=1, le=5)
    feedback: str | None = None


class KnowledgeBaseArticle(BaseModel):
    """Knowledge base article."""

    article_id: str
    title: str
    slug: str
    content: str
    category: str
    tags: list[str]
    helpful_count: int
    not_helpful_count: int
    created_at: datetime

    class Config:
        from_attributes = True


class SearchResult(BaseModel):
    """Knowledge base search result."""

    article_id: str
    title: str
    slug: str
    excerpt: str  # First 200 chars
    category: str
    relevance_score: float


class SupportTierInfo(BaseModel):
    """Support tier information."""

    tier: SupportTier
    monthly_cost_usd: float
    first_response_sla: str  # "4h", "48h", etc.
    channels: list[str]
    features: list[str]


# Support Tier Definitions

SUPPORT_TIERS = {
    SupportTier.COMMUNITY: SupportTierInfo(
        tier=SupportTier.COMMUNITY,
        monthly_cost_usd=0.0,
        first_response_sla="Best effort (24-72h)",
        channels=["GitHub Discussions", "Stack Overflow", "Public Docs"],
        features=["Access to knowledge base", "Public bug reports", "Feature requests", "Community forum"],
    ),
    SupportTier.PROFESSIONAL: SupportTierInfo(
        tier=SupportTier.PROFESSIONAL,
        monthly_cost_usd=499.0,
        first_response_sla="48h (business hours)",
        channels=["Email", "Customer Portal", "Knowledge Base"],
        features=[
            "Email support",
            "Ticket tracking",
            "40 hours/month included",
            "Named support contact",
            "Monthly support reports",
        ],
    ),
    SupportTier.ENTERPRISE: SupportTierInfo(
        tier=SupportTier.ENTERPRISE,
        monthly_cost_usd=2999.0,
        first_response_sla="4h critical (24/7), 8h high, 24h normal",
        channels=["Email", "Portal", "Dedicated Slack", "Phone (callback)"],
        features=[
            "24/7 critical support",
            "Unlimited support hours",
            "Dedicated Slack channel",
            "Phone support (callback)",
            "Customer Success Manager",
            "Quarterly Business Reviews",
            "Architecture reviews",
            "Performance tuning",
            "Early access to features",
            "Priority bug fixes",
            "Custom training",
            "On-premise support",
        ],
    ),
}
