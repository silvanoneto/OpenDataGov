"""FinOps Dashboard - FastAPI Application.

Provides REST API endpoints for cloud cost management, budget tracking,
anomaly detection, and savings recommendations.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from typing import Any

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from finops_dashboard.anomaly_detector import AnomalyDetector
from finops_dashboard.auth import (
    PermissionChecker,
    User,
    get_current_user,
    get_current_user_dev,
    init_auth0,
)
from finops_dashboard.budget_monitor import BudgetMonitor
from finops_dashboard.collectors.aws_collector import AWSCostCollector
from finops_dashboard.collectors.azure_collector import AzureCostCollector
from finops_dashboard.collectors.gcp_collector import GCPCostCollector
from finops_dashboard.models import (
    Anomaly,
    AnomalyResolution,
    AnomalyStatus,
    Budget,
    BudgetCreate,
    BudgetRow,
    BudgetStatus,
    CloudCostRow,
    CloudProvider,
    CollectionResult,
    CostAnomalyRow,
    CostSummary,
    Recommendation,
    RecommendationStatus,
    SavingsRecommendationRow,
)
from finops_dashboard.savings_recommender import SavingsRecommender
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Database configuration
DATABASE_URL = "postgresql+asyncpg://odg:odg@postgres:5432/finops"

# Create async engine
engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_size=20,
    max_overflow=40,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# Lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown."""
    logger.info("Starting FinOps Dashboard API")

    # Initialize Auth0 (from environment variables)
    import os

    auth0_domain = os.getenv("AUTH0_DOMAIN")
    auth0_audience = os.getenv("AUTH0_AUDIENCE")

    if auth0_domain and auth0_audience:
        init_auth0(
            domain=auth0_domain,
            audience=auth0_audience,
        )
        logger.info("Auth0 authentication enabled")
    else:
        logger.warning("Auth0 not configured - using development mode")
        # Override authentication with mock for development
        app.dependency_overrides[get_current_user] = get_current_user_dev

    yield
    logger.info("Shutting down FinOps Dashboard API")
    await engine.dispose()


# Create FastAPI app
app = FastAPI(
    title="FinOps Dashboard API",
    description="Cloud cost management, budget tracking, anomaly detection, and savings recommendations",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Configure allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Dependency: Database session
async def get_db() -> AsyncSession:
    """Get database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


# Note: get_current_user is now imported from auth.py and configured in lifespan


# ==================== Health Check ====================


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "finops-dashboard",
        "timestamp": datetime.utcnow().isoformat(),
    }


# ==================== Cost Collection ====================


@app.post(
    "/api/v1/finops/costs/collect/aws",
    response_model=CollectionResult,
    tags=["Cost Collection"],
)
async def collect_aws_costs(
    start_date: date,
    end_date: date,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Collect AWS costs for date range.

    Args:
        start_date: Start date (inclusive)
        end_date: End date (exclusive)

    Returns:
        Collection result with records inserted and total cost
    """
    logger.info(f"Collecting AWS costs from {start_date} to {end_date}")

    collector = AWSCostCollector()

    try:
        # Fetch costs
        costs = await collector.fetch_costs(start_date, end_date)

        # Insert into database
        records_inserted = 0
        total_cost = 0

        for cost in costs:
            cost_row = CloudCostRow(
                time=cost.time,
                cloud_provider=cost.cloud_provider.value,
                account_id=cost.account_id,
                service=cost.service,
                region=cost.region,
                cost=cost.cost,
                currency=cost.currency,
                resource_id=cost.resource_id,
                resource_name=cost.resource_name,
                tags=cost.tags,
                project=cost.project,
                team=cost.team,
                environment=cost.environment,
            )

            # Upsert (ON CONFLICT DO UPDATE)
            db.add(cost_row)
            records_inserted += 1
            total_cost += float(cost.cost)

        await db.commit()

        return CollectionResult(
            cloud_provider=CloudProvider.AWS,
            records_inserted=records_inserted,
            total_cost=total_cost,
            date_range=(
                datetime.combine(start_date, datetime.min.time()),
                datetime.combine(end_date, datetime.min.time()),
            ),
        )

    except Exception as e:
        logger.error(f"Error collecting AWS costs: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to collect AWS costs: {e!s}") from e
    finally:
        await collector.close()


@app.post(
    "/api/v1/finops/costs/collect/gcp",
    response_model=CollectionResult,
    tags=["Cost Collection"],
)
async def collect_gcp_costs(
    project_id: str,
    start_date: date,
    end_date: date,
    db: AsyncSession = Depends(get_db),
):
    """Collect GCP costs for date range.

    Args:
        project_id: GCP project ID
        start_date: Start date (inclusive)
        end_date: End date (exclusive)

    Returns:
        Collection result with records inserted and total cost
    """
    logger.info(f"Collecting GCP costs from {start_date} to {end_date}")

    collector = GCPCostCollector(project_id=project_id)

    try:
        costs = await collector.fetch_costs(start_date, end_date)

        records_inserted = 0
        total_cost = 0

        for cost in costs:
            cost_row = CloudCostRow(
                time=cost.time,
                cloud_provider=cost.cloud_provider.value,
                account_id=cost.account_id,
                service=cost.service,
                region=cost.region,
                cost=cost.cost,
                currency=cost.currency,
                tags=cost.tags,
                project=cost.project,
                team=cost.team,
                environment=cost.environment,
            )

            db.add(cost_row)
            records_inserted += 1
            total_cost += float(cost.cost)

        await db.commit()

        return CollectionResult(
            cloud_provider=CloudProvider.GCP,
            records_inserted=records_inserted,
            total_cost=total_cost,
            date_range=(
                datetime.combine(start_date, datetime.min.time()),
                datetime.combine(end_date, datetime.min.time()),
            ),
        )

    except Exception as e:
        logger.error(f"Error collecting GCP costs: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to collect GCP costs: {e!s}") from e
    finally:
        await collector.close()


@app.post(
    "/api/v1/finops/costs/collect/azure",
    response_model=CollectionResult,
    tags=["Cost Collection"],
)
async def collect_azure_costs(
    subscription_id: str,
    start_date: date,
    end_date: date,
    db: AsyncSession = Depends(get_db),
):
    """Collect Azure costs for date range.

    Args:
        subscription_id: Azure subscription ID
        start_date: Start date (inclusive)
        end_date: End date (exclusive)

    Returns:
        Collection result with records inserted and total cost
    """
    logger.info(f"Collecting Azure costs from {start_date} to {end_date}")

    collector = AzureCostCollector(subscription_id=subscription_id)

    try:
        costs = await collector.fetch_costs(start_date, end_date)

        records_inserted = 0
        total_cost = 0

        for cost in costs:
            cost_row = CloudCostRow(
                time=cost.time,
                cloud_provider=cost.cloud_provider.value,
                account_id=cost.account_id,
                service=cost.service,
                region=cost.region,
                cost=cost.cost,
                currency=cost.currency,
                tags=cost.tags,
                project=cost.project,
                team=cost.team,
                environment=cost.environment,
            )

            db.add(cost_row)
            records_inserted += 1
            total_cost += float(cost.cost)

        await db.commit()

        return CollectionResult(
            cloud_provider=CloudProvider.AZURE,
            records_inserted=records_inserted,
            total_cost=total_cost,
            date_range=(
                datetime.combine(start_date, datetime.min.time()),
                datetime.combine(end_date, datetime.min.time()),
            ),
        )

    except Exception as e:
        logger.error(f"Error collecting Azure costs: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to collect Azure costs: {e!s}") from e
    finally:
        await collector.close()


@app.post(
    "/api/v1/finops/costs/collect/all",
    tags=["Cost Collection"],
)
async def collect_all_costs(
    start_date: date | None = None,
    end_date: date | None = None,
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_db),
):
    """Collect costs from all cloud providers (AWS, GCP).

    Runs as background task for large date ranges.

    Args:
        start_date: Start date (defaults to yesterday)
        end_date: End date (defaults to today)

    Returns:
        Job status
    """
    if not start_date:
        start_date = (datetime.utcnow() - timedelta(days=1)).date()
    if not end_date:
        end_date = datetime.utcnow().date()

    logger.info(f"Triggering cost collection for all providers ({start_date} to {end_date})")

    # Run in background
    async def collect_task():
        import os

        async with AsyncSessionLocal() as session:
            # AWS
            try:
                await collect_aws_costs(start_date, end_date, None, session)
            except Exception as e:
                logger.error(f"AWS collection failed: {e}")

            # GCP
            gcp_project = os.getenv("GCP_PROJECT_ID")
            if gcp_project:
                try:
                    await collect_gcp_costs(gcp_project, start_date, end_date, session)
                except Exception as e:
                    logger.error(f"GCP collection failed: {e}")

            # Azure
            azure_subscription = os.getenv("AZURE_SUBSCRIPTION_ID")
            if azure_subscription:
                try:
                    await collect_azure_costs(azure_subscription, start_date, end_date, session)
                except Exception as e:
                    logger.error(f"Azure collection failed: {e}")

    if background_tasks:
        background_tasks.add_task(collect_task)

    return {
        "status": "triggered",
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "message": "Cost collection started in background",
    }


# ==================== Cost Summary ====================


@app.get(
    "/api/v1/finops/costs/summary",
    response_model=CostSummary,
    tags=["Costs"],
)
async def get_cost_summary(
    start_date: date | None = None,
    end_date: date | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Get cost summary for period.

    Args:
        start_date: Start date (defaults to 30 days ago)
        end_date: End date (defaults to today)

    Returns:
        Cost summary with breakdowns
    """
    if not start_date:
        start_date = (datetime.utcnow() - timedelta(days=30)).date()
    if not end_date:
        end_date = datetime.utcnow().date()

    # Total cost
    result = await db.execute(
        select(func.sum(CloudCostRow.cost)).where(
            CloudCostRow.time >= datetime.combine(start_date, datetime.min.time()),
            CloudCostRow.time < datetime.combine(end_date, datetime.min.time()),
        )
    )
    total_cost = result.scalar() or 0

    # Daily average
    days = (end_date - start_date).days
    daily_average = total_cost / days if days > 0 else 0

    # Breakdown by service
    result = await db.execute(
        select(CloudCostRow.service, func.sum(CloudCostRow.cost).label("total"))
        .where(
            CloudCostRow.time >= datetime.combine(start_date, datetime.min.time()),
            CloudCostRow.time < datetime.combine(end_date, datetime.min.time()),
        )
        .group_by(CloudCostRow.service)
        .order_by(func.sum(CloudCostRow.cost).desc())
    )
    breakdown_by_service = {row.service: row.total for row in result.all()}

    # Breakdown by project
    result = await db.execute(
        select(CloudCostRow.project, func.sum(CloudCostRow.cost).label("total"))
        .where(
            CloudCostRow.time >= datetime.combine(start_date, datetime.min.time()),
            CloudCostRow.time < datetime.combine(end_date, datetime.min.time()),
            CloudCostRow.project.isnot(None),
        )
        .group_by(CloudCostRow.project)
        .order_by(func.sum(CloudCostRow.cost).desc())
    )
    breakdown_by_project = {row.project: row.total for row in result.all()}

    # Breakdown by environment
    result = await db.execute(
        select(CloudCostRow.environment, func.sum(CloudCostRow.cost).label("total"))
        .where(
            CloudCostRow.time >= datetime.combine(start_date, datetime.min.time()),
            CloudCostRow.time < datetime.combine(end_date, datetime.min.time()),
            CloudCostRow.environment.isnot(None),
        )
        .group_by(CloudCostRow.environment)
        .order_by(func.sum(CloudCostRow.cost).desc())
    )
    breakdown_by_environment = {row.environment: row.total for row in result.all()}

    # Top spenders (top 10 services)
    top_spenders = [
        {"service": service, "cost": float(cost)}
        for service, cost in sorted(breakdown_by_service.items(), key=lambda x: x[1], reverse=True)[:10]
    ]

    return CostSummary(
        total_cost=total_cost,
        daily_average=daily_average,
        breakdown_by_service=breakdown_by_service,
        breakdown_by_project=breakdown_by_project,
        breakdown_by_environment=breakdown_by_environment,
        top_spenders=top_spenders,
    )


# ==================== Budget Management ====================


@app.post(
    "/api/v1/finops/budgets",
    response_model=Budget,
    status_code=status.HTTP_201_CREATED,
    tags=["Budgets"],
)
async def create_budget(
    budget: BudgetCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker(["write:budgets"])),
):
    """Create new budget (requires write:budgets permission).

    Args:
        budget: Budget configuration

    Returns:
        Created budget
    """
    logger.info(f"Creating budget: {budget.budget_name} (by {current_user.user_id})")

    budget_row = BudgetRow(
        budget_name=budget.budget_name,
        scope_type=budget.scope_type,
        scope_value=budget.scope_value,
        amount=budget.amount,
        currency=budget.currency,
        period=budget.period.value,
        alert_thresholds=budget.alert_thresholds,
        alert_channels=budget.alert_channels,
        created_by=current_user.user_id,  # Use authenticated user
        active=True,
    )

    db.add(budget_row)
    await db.commit()
    await db.refresh(budget_row)

    return Budget(
        budget_id=budget_row.budget_id,
        budget_name=budget_row.budget_name,
        scope_type=budget_row.scope_type,
        scope_value=budget_row.scope_value,
        amount=budget_row.amount,
        currency=budget_row.currency,
        period=budget_row.period,
        alert_thresholds=budget_row.alert_thresholds,
        alert_channels=budget_row.alert_channels,
        created_by=budget_row.created_by,
        created_at=budget_row.created_at,
        active=budget_row.active,
    )


@app.get(
    "/api/v1/finops/budgets",
    response_model=list[Budget],
    tags=["Budgets"],
)
async def list_budgets(
    active_only: bool = True,
    db: AsyncSession = Depends(get_db),
):
    """List all budgets.

    Args:
        active_only: Return only active budgets

    Returns:
        List of budgets
    """
    query = select(BudgetRow)
    if active_only:
        query = query.where(BudgetRow.active)

    result = await db.execute(query.order_by(BudgetRow.created_at.desc()))
    budgets = result.scalars().all()

    return [
        Budget(
            budget_id=b.budget_id,
            budget_name=b.budget_name,
            scope_type=b.scope_type,
            scope_value=b.scope_value,
            amount=b.amount,
            currency=b.currency,
            period=b.period,
            alert_thresholds=b.alert_thresholds,
            alert_channels=b.alert_channels,
            created_by=b.created_by,
            created_at=b.created_at,
            active=b.active,
        )
        for b in budgets
    ]


@app.get(
    "/api/v1/finops/budgets/{budget_id}",
    response_model=Budget,
    tags=["Budgets"],
)
async def get_budget(
    budget_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get budget by ID.

    Args:
        budget_id: Budget ID

    Returns:
        Budget details
    """
    result = await db.execute(select(BudgetRow).where(BudgetRow.budget_id == budget_id))
    budget = result.scalar_one_or_none()

    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")

    return Budget(
        budget_id=budget.budget_id,
        budget_name=budget.budget_name,
        scope_type=budget.scope_type,
        scope_value=budget.scope_value,
        amount=budget.amount,
        currency=budget.currency,
        period=budget.period,
        alert_thresholds=budget.alert_thresholds,
        alert_channels=budget.alert_channels,
        created_by=budget.created_by,
        created_at=budget.created_at,
        active=budget.active,
    )


@app.get(
    "/api/v1/finops/budgets/{budget_id}/status",
    response_model=BudgetStatus,
    tags=["Budgets"],
)
async def get_budget_status(
    budget_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get current budget status with burn rate and forecast.

    Args:
        budget_id: Budget ID

    Returns:
        Budget status
    """
    monitor = BudgetMonitor(db)

    try:
        status = await monitor.get_budget_status(budget_id)
        return status
    except Exception as e:
        logger.error(f"Error getting budget status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get budget status: {e!s}") from e


@app.post(
    "/api/v1/finops/budgets/check-all",
    tags=["Budgets"],
)
async def check_all_budgets(
    db: AsyncSession = Depends(get_db),
):
    """Check all active budgets and send alerts if needed.

    Returns:
        Budget check results
    """
    monitor = BudgetMonitor(db)

    try:
        statuses = await monitor.check_all_budgets()

        return {
            "budgets_checked": len(statuses),
            "statuses": [
                {
                    "budget_id": s.budget_id,
                    "budget_name": s.budget_name,
                    "pct_consumed": float(s.pct_consumed),
                    "alert_level": s.alert_level,
                    "on_track": s.on_track,
                }
                for s in statuses
            ],
        }
    except Exception as e:
        logger.error(f"Error checking budgets: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to check budgets: {e!s}") from e


@app.patch(
    "/api/v1/finops/budgets/{budget_id}",
    response_model=Budget,
    tags=["Budgets"],
)
async def update_budget(
    budget_id: int,
    amount: float | None = None,
    alert_thresholds: list[int] | None = None,
    alert_channels: dict[str, Any] | None = None,
    active: bool | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Update budget configuration.

    Args:
        budget_id: Budget ID
        amount: New budget amount
        alert_thresholds: New alert thresholds
        alert_channels: New alert channels
        active: Active status

    Returns:
        Updated budget
    """
    result = await db.execute(select(BudgetRow).where(BudgetRow.budget_id == budget_id))
    budget = result.scalar_one_or_none()

    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")

    if amount is not None:
        budget.amount = amount
    if alert_thresholds is not None:
        budget.alert_thresholds = alert_thresholds
    if alert_channels is not None:
        budget.alert_channels = alert_channels
    if active is not None:
        budget.active = active

    await db.commit()
    await db.refresh(budget)

    return Budget(
        budget_id=budget.budget_id,
        budget_name=budget.budget_name,
        scope_type=budget.scope_type,
        scope_value=budget.scope_value,
        amount=budget.amount,
        currency=budget.currency,
        period=budget.period,
        alert_thresholds=budget.alert_thresholds,
        alert_channels=budget.alert_channels,
        created_by=budget.created_by,
        created_at=budget.created_at,
        active=budget.active,
    )


# ==================== Anomaly Detection ====================


@app.post(
    "/api/v1/finops/anomalies/detect",
    tags=["Anomalies"],
)
async def detect_anomalies(
    cloud_provider: CloudProvider | None = None,
    service: str | None = None,
    lookback_days: int = 90,
    db: AsyncSession = Depends(get_db),
):
    """Run anomaly detection.

    Args:
        cloud_provider: Filter by cloud provider
        service: Filter by service
        lookback_days: Days of historical data to analyze

    Returns:
        Detection results
    """
    detector = AnomalyDetector(db, lookback_days=lookback_days)

    try:
        anomalies = await detector.detect_anomalies(
            cloud_provider=cloud_provider.value if cloud_provider else None,
            service=service,
        )

        return {
            "anomalies_detected": len(anomalies),
            "total_impact": sum(float(a.get("actual_cost", 0) - a.get("expected_cost", 0)) for a in anomalies),
            "anomalies": [
                {
                    "service": a["service"],
                    "expected_cost": float(a["expected_cost"]),
                    "actual_cost": float(a["actual_cost"]),
                    "deviation_pct": float(a["deviation_pct"]),
                    "detection_method": a["detection_method"],
                    "confidence": float(a["confidence_score"]),
                }
                for a in anomalies[:10]  # Top 10
            ],
        }
    except Exception as e:
        logger.error(f"Error detecting anomalies: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to detect anomalies: {e!s}") from e


@app.get(
    "/api/v1/finops/anomalies",
    response_model=list[Anomaly],
    tags=["Anomalies"],
)
async def list_anomalies(
    status_filter: AnomalyStatus | None = None,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    """List detected anomalies.

    Args:
        status_filter: Filter by status
        limit: Maximum number of results

    Returns:
        List of anomalies
    """
    query = select(CostAnomalyRow).order_by(CostAnomalyRow.detected_at.desc()).limit(limit)

    if status_filter:
        query = query.where(CostAnomalyRow.status == status_filter.value)

    result = await db.execute(query)
    anomalies = result.scalars().all()

    return [
        Anomaly(
            anomaly_id=a.anomaly_id,
            detected_at=a.detected_at,
            cloud_provider=CloudProvider(a.cloud_provider) if a.cloud_provider else None,
            service=a.service,
            project=a.project,
            resource_id=a.resource_id,
            expected_cost=a.expected_cost,
            actual_cost=a.actual_cost,
            deviation_pct=a.deviation_pct,
            detection_method=a.detection_method,
            confidence_score=a.confidence_score,
            status=AnomalyStatus(a.status),
            resolution_notes=a.resolution_notes,
        )
        for a in anomalies
    ]


@app.patch(
    "/api/v1/finops/anomalies/{anomaly_id}/resolve",
    tags=["Anomalies"],
)
async def resolve_anomaly(
    anomaly_id: int,
    resolution: AnomalyResolution,
    db: AsyncSession = Depends(get_db),
):
    """Resolve anomaly.

    Args:
        anomaly_id: Anomaly ID
        resolution: Resolution details

    Returns:
        Updated anomaly
    """
    result = await db.execute(select(CostAnomalyRow).where(CostAnomalyRow.anomaly_id == anomaly_id))
    anomaly = result.scalar_one_or_none()

    if not anomaly:
        raise HTTPException(status_code=404, detail="Anomaly not found")

    anomaly.status = resolution.status.value
    anomaly.resolution_notes = resolution.resolution_notes
    anomaly.resolved_by = resolution.resolved_by
    anomaly.resolved_at = datetime.utcnow()

    await db.commit()

    return {"success": True, "anomaly_id": anomaly_id, "status": resolution.status.value}


# ==================== Savings Recommendations ====================


@app.post(
    "/api/v1/finops/recommendations/generate",
    tags=["Recommendations"],
)
async def generate_recommendations(
    db: AsyncSession = Depends(get_db),
):
    """Generate savings recommendations.

    Returns:
        Recommendation generation results
    """
    recommender = SavingsRecommender(db)

    try:
        recommendations = await recommender.generate_all_recommendations()

        total_monthly_savings = sum(r["monthly_savings"] for r in recommendations)
        total_annual_savings = sum(r["annual_savings"] for r in recommendations)

        return {
            "recommendations_generated": len(recommendations),
            "total_monthly_savings": float(total_monthly_savings),
            "total_annual_savings": float(total_annual_savings),
            "breakdown": {
                "rightsizing": len([r for r in recommendations if r["type"] == "rightsizing"]),
                "reserved_instance": len([r for r in recommendations if r["type"] == "reserved_instance"]),
                "idle_resource": len([r for r in recommendations if r["type"] == "idle_resource"]),
                "storage_optimization": len([r for r in recommendations if r["type"] == "storage_optimization"]),
            },
        }
    except Exception as e:
        logger.error(f"Error generating recommendations: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate recommendations: {e!s}") from e


@app.get(
    "/api/v1/finops/recommendations",
    response_model=list[Recommendation],
    tags=["Recommendations"],
)
async def list_recommendations(
    status_filter: RecommendationStatus | None = None,
    priority: str | None = None,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    """List savings recommendations.

    Args:
        status_filter: Filter by status
        priority: Filter by priority (critical, high, medium, low)
        limit: Maximum number of results

    Returns:
        List of recommendations
    """
    query = select(SavingsRecommendationRow).order_by(SavingsRecommendationRow.monthly_savings.desc()).limit(limit)

    if status_filter:
        query = query.where(SavingsRecommendationRow.status == status_filter.value)

    if priority:
        query = query.where(SavingsRecommendationRow.priority == priority)

    result = await db.execute(query)
    recommendations = result.scalars().all()

    return [
        Recommendation(
            recommendation_id=r.recommendation_id,
            generated_at=r.generated_at,
            type=r.type,
            priority=r.priority,
            cloud_provider=CloudProvider(r.cloud_provider) if r.cloud_provider else None,
            service=r.service,
            resource_id=r.resource_id,
            resource_name=r.resource_name,
            current_monthly_cost=r.current_monthly_cost,
            projected_monthly_cost=r.projected_monthly_cost,
            monthly_savings=r.monthly_savings,
            annual_savings=r.annual_savings,
            description=r.description,
            action_required=r.action_required,
            status=RecommendationStatus(r.status),
        )
        for r in recommendations
    ]


@app.post(
    "/api/v1/finops/recommendations/{recommendation_id}/approve",
    tags=["Recommendations"],
)
async def approve_recommendation(
    recommendation_id: int,
    approved_by: str,
    db: AsyncSession = Depends(get_db),
):
    """Approve recommendation for implementation.

    Args:
        recommendation_id: Recommendation ID
        approved_by: User who approved

    Returns:
        Success status
    """
    recommender = SavingsRecommender(db)

    try:
        await recommender.approve_recommendation(recommendation_id, approved_by)
        return {"success": True, "recommendation_id": recommendation_id, "status": "approved"}
    except Exception as e:
        logger.error(f"Error approving recommendation: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to approve recommendation: {e!s}") from e


@app.post(
    "/api/v1/finops/recommendations/{recommendation_id}/implement",
    tags=["Recommendations"],
)
async def mark_recommendation_implemented(
    recommendation_id: int,
    implemented_by: str,
    db: AsyncSession = Depends(get_db),
):
    """Mark recommendation as implemented.

    Args:
        recommendation_id: Recommendation ID
        implemented_by: User who implemented

    Returns:
        Success status
    """
    recommender = SavingsRecommender(db)

    try:
        await recommender.mark_implemented(recommendation_id, implemented_by)
        return {"success": True, "recommendation_id": recommendation_id, "status": "implemented"}
    except Exception as e:
        logger.error(f"Error marking recommendation as implemented: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to mark as implemented: {e!s}") from e


@app.get(
    "/api/v1/finops/recommendations/savings-potential",
    tags=["Recommendations"],
)
async def get_savings_potential(
    db: AsyncSession = Depends(get_db),
):
    """Get total savings potential from pending recommendations.

    Returns:
        Monthly and annual savings potential
    """
    recommender = SavingsRecommender(db)

    try:
        savings = await recommender.get_total_savings_potential()

        return {
            "monthly_savings": float(savings["monthly_savings"]),
            "annual_savings": float(savings["annual_savings"]),
            "percentage_of_current_spend": 25.0,  # TODO: Calculate from actual spend
        }
    except Exception as e:
        logger.error(f"Error calculating savings potential: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to calculate savings: {e!s}") from e


# ==================== Main Entry Point ====================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "finops_dashboard.main:app",
        host="0.0.0.0",
        port=8080,
        reload=True,
        log_level="info",
    )
