"""FinOps Dashboard Models - Cloud Cost Tracking.

Database models for tracking cloud costs, budgets, anomalies, and savings recommendations.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field
from sqlalchemy import (
    DECIMAL,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

if TYPE_CHECKING:
    from decimal import Decimal

Base = declarative_base()


# ==================== Enums ====================


class CloudProvider(StrEnum):
    """Supported cloud providers."""

    AWS = "aws"
    GCP = "gcp"
    AZURE = "azure"


class BudgetPeriod(StrEnum):
    """Budget time periods."""

    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"


class AnomalyStatus(StrEnum):
    """Cost anomaly status."""

    OPEN = "open"
    INVESTIGATING = "investigating"
    RESOLVED = "resolved"
    FALSE_POSITIVE = "false_positive"


class RecommendationType(StrEnum):
    """Types of cost savings recommendations."""

    RIGHTSIZING = "rightsizing"
    RESERVED_INSTANCE = "reserved_instance"
    SPOT_INSTANCE = "spot_instance"
    IDLE_RESOURCE = "idle_resource"
    STORAGE_OPTIMIZATION = "storage_optimization"


class RecommendationStatus(StrEnum):
    """Recommendation implementation status."""

    PENDING = "pending"
    APPROVED = "approved"
    IMPLEMENTED = "implemented"
    REJECTED = "rejected"


# ==================== SQLAlchemy Models ====================


class CloudCostRow(Base):
    """Cloud cost data (TimescaleDB hypertable)."""

    __tablename__ = "cloud_costs"

    # Primary key (time-series)
    time = Column(DateTime, primary_key=True, nullable=False)
    cloud_provider = Column(String(10), primary_key=True, nullable=False)
    account_id = Column(String(50), primary_key=True, nullable=False)
    service = Column(String(100), primary_key=True, nullable=False)

    # Location
    region = Column(String(50))

    # Cost data
    cost = Column(DECIMAL(12, 4), nullable=False)
    currency = Column(String(3), default="USD")

    # Resource details
    resource_id = Column(String(200))
    resource_name = Column(String(200))

    # Tags (for cost allocation)
    tags = Column(JSONB)  # {project: "lakehouse-agent", team: "platform", env: "prod"}

    # Derived fields (from tags)
    project = Column(String(100))
    team = Column(String(100))
    environment = Column(String(50))

    # Indexes
    __table_args__ = (
        Index("idx_cloud_costs_project", "project", "time"),
        Index("idx_cloud_costs_service", "service", "time"),
        Index("idx_cloud_costs_tags", "tags", postgresql_using="gin"),
    )


class BudgetRow(Base):
    """Budget definitions for cost tracking."""

    __tablename__ = "budgets"

    budget_id = Column(Integer, primary_key=True, autoincrement=True)
    budget_name = Column(String(200), nullable=False)

    # Scope
    scope_type = Column(String(50), nullable=False)  # organization, project, team, service, environment
    scope_value = Column(String(200))  # e.g., "lakehouse-agent", "platform", "prod"

    # Budget config
    amount = Column(DECIMAL(12, 2), nullable=False)
    currency = Column(String(3), default="USD")
    period = Column(String(20), nullable=False)  # monthly, quarterly, yearly

    # Alerts
    alert_thresholds = Column(JSONB)  # [50, 80, 100, 120]
    alert_channels = Column(JSONB)  # {slack: "#finops", email: ["team@..."], pagerduty: false}

    # Metadata
    created_by = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)
    active = Column(Boolean, default=True)

    # Relationship
    status_history = relationship("BudgetStatusHistoryRow", back_populates="budget")


class BudgetStatusHistoryRow(Base):
    """Historical budget status snapshots."""

    __tablename__ = "budget_status_history"

    history_id = Column(Integer, primary_key=True, autoincrement=True)
    budget_id = Column(Integer, ForeignKey("budgets.budget_id"), nullable=False)
    snapshot_date = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Status at snapshot time
    spent_to_date = Column(DECIMAL(12, 2), nullable=False)
    remaining = Column(DECIMAL(12, 2), nullable=False)
    pct_consumed = Column(DECIMAL(5, 2), nullable=False)
    burn_rate_per_day = Column(DECIMAL(12, 2))
    forecast_exhaustion_date = Column(DateTime)

    # Relationship
    budget = relationship("BudgetRow", back_populates="status_history")


class CostAnomalyRow(Base):
    """Detected cost anomalies."""

    __tablename__ = "cost_anomalies"

    anomaly_id = Column(Integer, primary_key=True, autoincrement=True)
    detected_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Anomaly details
    cloud_provider = Column(String(10))
    service = Column(String(100))
    project = Column(String(100))
    resource_id = Column(String(200))

    # Cost info
    expected_cost = Column(DECIMAL(12, 4))
    actual_cost = Column(DECIMAL(12, 4))
    deviation_pct = Column(DECIMAL(5, 2))  # 300 = 3x expected

    # Detection method
    detection_method = Column(String(50))  # zscore, iqr, ml_model
    confidence_score = Column(DECIMAL(3, 2))  # 0.95 = 95% confidence

    # Status
    status = Column(String(20), default="open")
    resolution_notes = Column(Text)
    resolved_at = Column(DateTime)
    resolved_by = Column(String(100))

    # Indexes
    __table_args__ = (
        Index("idx_anomalies_status", "status", "detected_at"),
        Index("idx_anomalies_service", "service", "detected_at"),
    )


class SavingsRecommendationRow(Base):
    """Cost savings recommendations."""

    __tablename__ = "savings_recommendations"

    recommendation_id = Column(Integer, primary_key=True, autoincrement=True)
    generated_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Recommendation type
    type = Column(String(50), nullable=False)
    priority = Column(String(20))  # critical, high, medium, low

    # Resource details
    cloud_provider = Column(String(10))
    service = Column(String(100))
    resource_id = Column(String(200))
    resource_name = Column(String(200))

    # Savings potential
    current_monthly_cost = Column(DECIMAL(12, 2))
    projected_monthly_cost = Column(DECIMAL(12, 2))
    monthly_savings = Column(DECIMAL(12, 2))
    annual_savings = Column(DECIMAL(12, 2))

    # Recommendation details
    description = Column(Text)
    action_required = Column(Text)

    # Implementation
    status = Column(String(20), default="pending")
    implemented_at = Column(DateTime)
    implemented_by = Column(String(100))

    # Indexes
    __table_args__ = (
        Index("idx_recommendations_status", "status", "generated_at"),
        Index("idx_recommendations_savings", "monthly_savings"),
    )


# ==================== Pydantic Models ====================


class CloudCost(BaseModel):
    """Cloud cost data point."""

    time: datetime
    cloud_provider: CloudProvider
    account_id: str
    service: str
    region: str | None = None
    cost: Decimal
    currency: str = "USD"
    resource_id: str | None = None
    resource_name: str | None = None
    tags: dict[str, Any] | None = None
    project: str | None = None
    team: str | None = None
    environment: str | None = None

    class Config:
        from_attributes = True


class BudgetCreate(BaseModel):
    """Budget creation request."""

    budget_name: str = Field(..., min_length=1, max_length=200)
    scope_type: str = Field(..., pattern="^(organization|project|team|service|environment)$")
    scope_value: str | None = None
    amount: Decimal = Field(..., gt=0)
    currency: str = "USD"
    period: BudgetPeriod
    alert_thresholds: list[int] = Field(default=[50, 80, 100, 120])
    alert_channels: dict[str, Any] = Field(default={"slack": "#finops", "email": [], "pagerduty": False})
    created_by: str


class Budget(BudgetCreate):
    """Budget response."""

    budget_id: int
    created_at: datetime
    active: bool

    class Config:
        from_attributes = True


class BudgetStatus(BaseModel):
    """Current budget status."""

    budget_id: int
    budget_name: str
    amount: Decimal
    spent_to_date: Decimal
    remaining: Decimal
    pct_consumed: Decimal
    burn_rate_per_day: Decimal | None = None
    forecast_exhaustion_date: datetime | None = None
    on_track: bool
    alert_level: str | None = None  # green, yellow, orange, red


class Anomaly(BaseModel):
    """Cost anomaly."""

    anomaly_id: int
    detected_at: datetime
    cloud_provider: CloudProvider | None = None
    service: str | None = None
    project: str | None = None
    resource_id: str | None = None
    expected_cost: Decimal | None = None
    actual_cost: Decimal | None = None
    deviation_pct: Decimal | None = None
    detection_method: str | None = None
    confidence_score: Decimal | None = None
    status: AnomalyStatus
    resolution_notes: str | None = None

    class Config:
        from_attributes = True


class AnomalyResolution(BaseModel):
    """Anomaly resolution request."""

    status: AnomalyStatus
    resolution_notes: str
    resolved_by: str


class Recommendation(BaseModel):
    """Savings recommendation."""

    recommendation_id: int
    generated_at: datetime
    type: RecommendationType
    priority: str | None = None
    cloud_provider: CloudProvider | None = None
    service: str | None = None
    resource_id: str | None = None
    resource_name: str | None = None
    current_monthly_cost: Decimal | None = None
    projected_monthly_cost: Decimal | None = None
    monthly_savings: Decimal | None = None
    annual_savings: Decimal | None = None
    description: str | None = None
    action_required: str | None = None
    status: RecommendationStatus

    class Config:
        from_attributes = True


class CollectionResult(BaseModel):
    """Cost collection result."""

    cloud_provider: CloudProvider
    records_inserted: int
    total_cost: Decimal
    date_range: tuple[datetime, datetime]
    collection_time: datetime = Field(default_factory=datetime.utcnow)


class CostSummary(BaseModel):
    """Cost summary for a period."""

    total_cost: Decimal
    daily_average: Decimal
    breakdown_by_service: dict[str, Decimal]
    breakdown_by_project: dict[str, Decimal]
    breakdown_by_environment: dict[str, Decimal]
    top_spenders: list[dict[str, Any]]  # [{service: "EC2", cost: 5000}, ...]


class ForecastResult(BaseModel):
    """Cost forecast."""

    forecast_date: datetime
    predicted_cost: Decimal
    confidence_interval_lower: Decimal
    confidence_interval_upper: Decimal
    model: str  # linear, prophet, arima


# ==================== Helper Functions ====================


def extract_tags_from_cost(cost: dict[str, Any]) -> dict[str, Any]:
    """Extract and normalize tags from cost data."""
    tags = cost.get("Tags", {})

    # Normalize tag keys (lowercase, replace spaces)
    normalized = {k.lower().replace(" ", "_"): v for k, v in tags.items()}

    return normalized


def derive_cost_allocation(tags: dict[str, Any]) -> tuple[str | None, str | None, str | None]:
    """Derive project, team, environment from tags."""
    project = tags.get("project") or tags.get("app") or tags.get("application")
    team = tags.get("team") or tags.get("owner")
    environment = tags.get("environment") or tags.get("env") or tags.get("stage")

    return project, team, environment
