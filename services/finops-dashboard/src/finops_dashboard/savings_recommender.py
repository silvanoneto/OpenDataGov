"""Savings Recommender - Generates cost optimization recommendations.

Analyzes resource utilization and costs to recommend:
- Rightsizing (downsize underutilized instances)
- Reserved Instances (for steady-state workloads)
- Spot Instances (for fault-tolerant workloads)
- Idle Resource Cleanup (stopped instances, unattached volumes)
- Storage Optimization (S3 → Glacier, log retention)
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from finops_dashboard.collectors.aws_collector import AWSCostCollector
from finops_dashboard.collectors.gcp_collector import GCPCostCollector
from finops_dashboard.models import (
    CloudCostRow,
    RecommendationStatus,
    RecommendationType,
    SavingsRecommendationRow,
)
from sqlalchemy import func, select

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class SavingsRecommender:
    """Generates cost savings recommendations."""

    def __init__(self, db: AsyncSession):
        """Initialize savings recommender.

        Args:
            db: Database session
        """
        self.db = db

        # Thresholds
        self.cpu_threshold = 20.0  # CPU < 20% = underutilized
        self.memory_threshold = 30.0  # Memory < 30% = underutilized
        self.ri_utilization_threshold = 80.0  # 80%+ utilization = RI candidate
        self.idle_cost_threshold = 10.0  # < $10/month = likely idle

    async def generate_all_recommendations(
        self,
    ) -> list[dict[str, Any]]:
        """Generate all types of cost savings recommendations.

        Returns:
            List of recommendations
        """
        logger.info("Generating cost savings recommendations")

        all_recommendations = []

        # 1. Rightsizing recommendations
        rightsizing = await self.generate_rightsizing_recommendations()
        all_recommendations.extend(rightsizing)

        # 2. Reserved Instance recommendations
        ri_recommendations = await self.generate_ri_recommendations()
        all_recommendations.extend(ri_recommendations)

        # 3. Idle resource cleanup
        idle_recommendations = await self.generate_idle_resource_recommendations()
        all_recommendations.extend(idle_recommendations)

        # 4. Storage optimization
        storage_recommendations = await self.generate_storage_recommendations()
        all_recommendations.extend(storage_recommendations)

        # Save to database
        for rec in all_recommendations:
            await self._save_recommendation(rec)

        logger.info(
            f"Generated {len(all_recommendations)} savings recommendations "
            f"(potential: ${sum(r['monthly_savings'] for r in all_recommendations):,.2f}/month)"
        )

        return all_recommendations

    async def generate_rightsizing_recommendations(
        self,
    ) -> list[dict[str, Any]]:
        """Generate rightsizing recommendations for underutilized instances.

        Returns:
            List of rightsizing recommendations
        """
        logger.info("Analyzing resource utilization for rightsizing opportunities")

        recommendations = []

        # AWS EC2 rightsizing
        aws_collector = AWSCostCollector()

        try:
            # Get all EC2 instances from cost data (last 30 days)
            result = await self.db.execute(
                select(
                    CloudCostRow.resource_id,
                    CloudCostRow.resource_name,
                    CloudCostRow.region,
                    func.sum(CloudCostRow.cost).label("monthly_cost"),
                )
                .where(
                    CloudCostRow.cloud_provider == "aws",
                    CloudCostRow.service == "Amazon Elastic Compute Cloud - Compute",
                    CloudCostRow.time >= datetime.utcnow() - timedelta(days=30),
                    CloudCostRow.resource_id.isnot(None),
                )
                .group_by(
                    CloudCostRow.resource_id,
                    CloudCostRow.resource_name,
                    CloudCostRow.region,
                )
            )

            instances = result.all()

            for resource_id, resource_name, _region, monthly_cost in instances:
                if not resource_id or not resource_id.startswith("i-"):
                    continue  # Not an instance ID

                # Get CloudWatch metrics
                cpu_stats = await aws_collector.get_resource_utilization(resource_id, "CPUUtilization", days=14)

                # Check if underutilized
                if (
                    cpu_stats["average"] < self.cpu_threshold
                    and cpu_stats["p95"] < self.cpu_threshold * 1.5
                    and cpu_stats["datapoints"] > 100  # Enough data
                ):
                    # Estimate savings (assume 50% downsize = 50% savings)
                    current_cost = Decimal(monthly_cost)
                    projected_cost = current_cost * Decimal("0.5")
                    savings = current_cost - projected_cost

                    recommendation = {
                        "type": RecommendationType.RIGHTSIZING,
                        "priority": "high" if savings > 100 else "medium",
                        "cloud_provider": "aws",
                        "service": "EC2",
                        "resource_id": resource_id,
                        "resource_name": resource_name or "Unnamed",
                        "current_monthly_cost": current_cost,
                        "projected_monthly_cost": projected_cost,
                        "monthly_savings": savings,
                        "annual_savings": savings * 12,
                        "description": (
                            f"Instance {resource_id} is underutilized"
                            f" (avg CPU: {cpu_stats['average']:.1f}%,"
                            f" P95: {cpu_stats['p95']:.1f}%)"
                        ),
                        "action_required": "Downsize instance to smaller type (e.g., from m5.2xlarge to m5.xlarge)",
                    }

                    recommendations.append(recommendation)

        except Exception as e:
            logger.error(f"Error generating rightsizing recommendations: {e}")
        finally:
            await aws_collector.close()

        return recommendations

    async def generate_ri_recommendations(
        self,
    ) -> list[dict[str, Any]]:
        """Generate Reserved Instance purchase recommendations.

        Recommends RIs for steady-state workloads with high utilization.

        Returns:
            List of RI recommendations
        """
        logger.info("Analyzing workloads for Reserved Instance opportunities")

        recommendations = []

        # Find instances with consistent usage (running 80%+ of time)
        result = await self.db.execute(
            select(
                CloudCostRow.service,
                CloudCostRow.region,
                func.count(func.distinct(func.date(CloudCostRow.time))).label("days_used"),
                func.sum(CloudCostRow.cost).label("total_cost"),
            )
            .where(
                CloudCostRow.cloud_provider == "aws",
                CloudCostRow.service.like("%Compute%"),
                CloudCostRow.time >= datetime.utcnow() - timedelta(days=90),
            )
            .group_by(CloudCostRow.service, CloudCostRow.region)
            .having(
                func.count(func.distinct(func.date(CloudCostRow.time))) >= 90 * 0.8  # 80%+ utilization
            )
        )

        workloads = result.all()

        for service, region, days_used, total_cost in workloads:
            utilization_pct = (days_used / 90) * 100

            if utilization_pct >= self.ri_utilization_threshold:
                # Calculate savings (RIs typically save 30-72%)
                monthly_cost = Decimal(total_cost) / 3  # 90 days → monthly
                ri_savings_pct = Decimal("0.40")  # 40% savings (conservative estimate)
                savings = monthly_cost * ri_savings_pct

                recommendation = {
                    "type": RecommendationType.RESERVED_INSTANCE,
                    "priority": "high" if savings > 500 else "medium",
                    "cloud_provider": "aws",
                    "service": service,
                    "resource_id": f"{service}-{region}",
                    "resource_name": f"{service} in {region}",
                    "current_monthly_cost": monthly_cost,
                    "projected_monthly_cost": monthly_cost - savings,
                    "monthly_savings": savings,
                    "annual_savings": savings * 12,
                    "description": (
                        f"{service} in {region} has {utilization_pct:.0f}% utilization (steady-state workload)"
                    ),
                    "action_required": f"Purchase 1-year or 3-year Reserved Instances for {service} in {region}",
                }

                recommendations.append(recommendation)

        return recommendations

    async def generate_idle_resource_recommendations(
        self,
    ) -> list[dict[str, Any]]:
        """Generate recommendations for idle resource cleanup.

        Returns:
            List of idle resource recommendations
        """
        logger.info("Detecting idle resources for cleanup")

        recommendations = []

        # AWS idle resources
        aws_collector = AWSCostCollector()

        try:
            idle_aws = await aws_collector.detect_idle_resources()

            for resource in idle_aws:
                monthly_cost = Decimal(resource["monthly_cost"])

                recommendation = {
                    "type": RecommendationType.IDLE_RESOURCE,
                    "priority": "critical" if monthly_cost > 100 else "high",
                    "cloud_provider": "aws",
                    "service": resource["resource_type"],
                    "resource_id": resource["resource_id"],
                    "resource_name": resource["resource_name"],
                    "current_monthly_cost": monthly_cost,
                    "projected_monthly_cost": Decimal(0),
                    "monthly_savings": monthly_cost,
                    "annual_savings": monthly_cost * 12,
                    "description": f"{resource['resource_type']} {resource['resource_id']} is {resource['status']}",
                    "action_required": resource["recommendation"],
                }

                recommendations.append(recommendation)

        except Exception as e:
            logger.error(f"Error detecting idle AWS resources: {e}")
        finally:
            await aws_collector.close()

        # GCP idle resources
        gcp_collector = GCPCostCollector(project_id="your-project-id")  # TODO: Config

        try:
            idle_gcp = await gcp_collector.detect_idle_resources()

            for resource in idle_gcp:
                monthly_cost = Decimal(resource["monthly_cost"])

                recommendation = {
                    "type": RecommendationType.IDLE_RESOURCE,
                    "priority": "high",
                    "cloud_provider": "gcp",
                    "service": resource["resource_type"],
                    "resource_id": resource["resource_id"],
                    "resource_name": resource["resource_name"],
                    "current_monthly_cost": monthly_cost,
                    "projected_monthly_cost": Decimal(0),
                    "monthly_savings": monthly_cost,
                    "annual_savings": monthly_cost * 12,
                    "description": f"{resource['resource_type']} {resource['resource_id']} is {resource['status']}",
                    "action_required": resource["recommendation"],
                }

                recommendations.append(recommendation)

        except Exception as e:
            logger.error(f"Error detecting idle GCP resources: {e}")
        finally:
            await gcp_collector.close()

        return recommendations

    async def generate_storage_recommendations(
        self,
    ) -> list[dict[str, Any]]:
        """Generate storage optimization recommendations.

        Recommends moving infrequently accessed data to cheaper storage tiers.

        Returns:
            List of storage recommendations
        """
        logger.info("Analyzing storage for optimization opportunities")

        recommendations = []

        # Find S3 buckets with high costs
        result = await self.db.execute(
            select(
                CloudCostRow.resource_id,
                CloudCostRow.resource_name,
                func.sum(CloudCostRow.cost).label("monthly_cost"),
            )
            .where(
                CloudCostRow.cloud_provider == "aws",
                CloudCostRow.service == "Amazon Simple Storage Service",
                CloudCostRow.time >= datetime.utcnow() - timedelta(days=30),
                CloudCostRow.resource_id.isnot(None),
            )
            .group_by(CloudCostRow.resource_id, CloudCostRow.resource_name)
            .having(func.sum(CloudCostRow.cost) > 50)  # > $50/month
        )

        buckets = result.all()

        for resource_id, resource_name, monthly_cost in buckets:
            # Estimate savings (assume 70% of data can go to Glacier = 70% savings)
            current_cost = Decimal(monthly_cost)
            glacier_savings_pct = Decimal("0.70")
            savings = current_cost * glacier_savings_pct

            recommendation = {
                "type": RecommendationType.STORAGE_OPTIMIZATION,
                "priority": "medium",
                "cloud_provider": "aws",
                "service": "S3",
                "resource_id": resource_id,
                "resource_name": resource_name or "S3 Bucket",
                "current_monthly_cost": current_cost,
                "projected_monthly_cost": current_cost - savings,
                "monthly_savings": savings,
                "annual_savings": savings * 12,
                "description": f"S3 bucket {resource_id} has high storage costs (${current_cost:.2f}/month)",
                "action_required": (
                    "Configure lifecycle policy to move objects to Glacier after 90 days, or delete old logs/backups"
                ),
            }

            recommendations.append(recommendation)

        return recommendations

    async def _save_recommendation(self, rec: dict[str, Any]):
        """Save recommendation to database.

        Args:
            rec: Recommendation data
        """
        # Check if similar recommendation already exists (last 7 days)
        result = await self.db.execute(
            select(SavingsRecommendationRow).where(
                SavingsRecommendationRow.type == rec["type"],
                SavingsRecommendationRow.resource_id == rec.get("resource_id"),
                SavingsRecommendationRow.generated_at >= datetime.utcnow() - timedelta(days=7),
                SavingsRecommendationRow.status == RecommendationStatus.PENDING,
            )
        )

        existing = result.scalar_one_or_none()

        if existing:
            logger.debug(f"Recommendation already exists for {rec.get('resource_id')}")
            return

        # Create new recommendation
        rec_row = SavingsRecommendationRow(
            generated_at=datetime.utcnow(),
            type=rec["type"],
            priority=rec.get("priority", "medium"),
            cloud_provider=rec.get("cloud_provider"),
            service=rec.get("service"),
            resource_id=rec.get("resource_id"),
            resource_name=rec.get("resource_name"),
            current_monthly_cost=rec.get("current_monthly_cost"),
            projected_monthly_cost=rec.get("projected_monthly_cost"),
            monthly_savings=rec["monthly_savings"],
            annual_savings=rec["annual_savings"],
            description=rec.get("description"),
            action_required=rec.get("action_required"),
            status=RecommendationStatus.PENDING,
        )

        self.db.add(rec_row)
        await self.db.commit()

    async def approve_recommendation(self, recommendation_id: int, approved_by: str):
        """Approve recommendation for implementation.

        Args:
            recommendation_id: Recommendation ID
            approved_by: User who approved
        """
        result = await self.db.execute(
            select(SavingsRecommendationRow).where(SavingsRecommendationRow.recommendation_id == recommendation_id)
        )

        rec = result.scalar_one()

        rec.status = RecommendationStatus.APPROVED
        rec.implemented_by = approved_by

        await self.db.commit()

        logger.info(f"Recommendation {recommendation_id} approved by {approved_by}")

    async def mark_implemented(self, recommendation_id: int, implemented_by: str):
        """Mark recommendation as implemented.

        Args:
            recommendation_id: Recommendation ID
            implemented_by: User who implemented
        """
        result = await self.db.execute(
            select(SavingsRecommendationRow).where(SavingsRecommendationRow.recommendation_id == recommendation_id)
        )

        rec = result.scalar_one()

        rec.status = RecommendationStatus.IMPLEMENTED
        rec.implemented_at = datetime.utcnow()
        rec.implemented_by = implemented_by

        await self.db.commit()

        logger.info(f"Recommendation {recommendation_id} marked as implemented by {implemented_by}")

    async def get_total_savings_potential(self) -> dict[str, Decimal]:
        """Calculate total potential savings from all pending recommendations.

        Returns:
            Dictionary with monthly and annual savings
        """
        result = await self.db.execute(
            select(
                func.sum(SavingsRecommendationRow.monthly_savings).label("monthly_total"),
                func.sum(SavingsRecommendationRow.annual_savings).label("annual_total"),
            ).where(SavingsRecommendationRow.status == RecommendationStatus.PENDING)
        )

        row = result.one()

        return {
            "monthly_savings": row.monthly_total or Decimal(0),
            "annual_savings": row.annual_total or Decimal(0),
        }
