"""AWS Cost Collector - Fetches cost data from AWS Cost Explorer API.

Collects daily cost and usage data with service and tag breakdowns.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from finops_dashboard.models import CloudCost, CloudProvider, derive_cost_allocation

logger = logging.getLogger(__name__)


class AWSCostCollector:
    """Collects cost data from AWS Cost Explorer."""

    def __init__(
        self,
        aws_access_key_id: str | None = None,
        aws_secret_access_key: str | None = None,
        region_name: str = "us-east-1",
    ):
        """Initialize AWS Cost Explorer client.

        Args:
            aws_access_key_id: AWS access key (defaults to env/IAM role)
            aws_secret_access_key: AWS secret key
            region_name: AWS region for Cost Explorer API
        """
        session_kwargs = {"region_name": region_name}

        if aws_access_key_id and aws_secret_access_key:
            session_kwargs["aws_access_key_id"] = aws_access_key_id
            session_kwargs["aws_secret_access_key"] = aws_secret_access_key

        self.session = boto3.Session(**session_kwargs)
        self.ce_client = self.session.client("ce")
        self.cloudwatch_client = self.session.client("cloudwatch")

        # Get account ID
        sts_client = self.session.client("sts")
        self.account_id = sts_client.get_caller_identity()["Account"]

    async def fetch_costs(
        self,
        start_date: date,
        end_date: date,
        granularity: str = "DAILY",
    ) -> list[CloudCost]:
        """Fetch costs from AWS Cost Explorer.

        Args:
            start_date: Start date (inclusive)
            end_date: End date (exclusive)
            granularity: DAILY, MONTHLY, or HOURLY

        Returns:
            List of CloudCost objects
        """
        logger.info(f"Fetching AWS costs from {start_date} to {end_date} (granularity: {granularity})")

        try:
            # Fetch cost data with service and tag grouping
            response = self.ce_client.get_cost_and_usage(
                TimePeriod={
                    "Start": start_date.strftime("%Y-%m-%d"),
                    "End": end_date.strftime("%Y-%m-%d"),
                },
                Granularity=granularity,
                Metrics=["UnblendedCost"],
                GroupBy=[
                    {"Type": "DIMENSION", "Key": "SERVICE"},
                    {"Type": "DIMENSION", "Key": "REGION"},
                ],
            )

            costs = []

            for result in response["ResultsByTime"]:
                time_period = result["TimePeriod"]
                timestamp = datetime.strptime(time_period["Start"], "%Y-%m-%d")

                for group in result["Groups"]:
                    # Parse grouping keys
                    keys = group["Keys"]
                    service = keys[0] if len(keys) > 0 else "Unknown"
                    region = keys[1] if len(keys) > 1 else "global"

                    # Get cost
                    amount = Decimal(group["Metrics"]["UnblendedCost"]["Amount"])

                    if amount == 0:
                        continue  # Skip zero-cost entries

                    # Fetch tags for this service (if available)
                    tags = await self._fetch_tags_for_service(service, region)
                    project, team, environment = derive_cost_allocation(tags)

                    cost = CloudCost(
                        time=timestamp,
                        cloud_provider=CloudProvider.AWS,
                        account_id=self.account_id,
                        service=service,
                        region=region if region != "global" else None,
                        cost=amount,
                        currency="USD",
                        tags=tags,
                        project=project,
                        team=team,
                        environment=environment,
                    )

                    costs.append(cost)

            logger.info(f"Fetched {len(costs)} cost records from AWS")
            return costs

        except (ClientError, BotoCoreError) as e:
            logger.error(f"Error fetching AWS costs: {e}")
            raise

    async def _fetch_tags_for_service(self, service: str, region: str) -> dict[str, Any]:
        """Fetch tags for a specific service.

        Note: This is a simplified implementation. In production, you would
        query resource tagging API or maintain a tag index.

        Args:
            service: AWS service name
            region: AWS region

        Returns:
            Tags dictionary
        """
        # Simplified: Return empty tags
        # In production, use:
        # - resourcegroupstaggingapi.get_resources()
        # - Tag index from infrastructure as code (Terraform state, CloudFormation)
        return {}

    async def fetch_detailed_costs_with_tags(
        self,
        start_date: date,
        end_date: date,
        tag_key: str = "project",
    ) -> list[CloudCost]:
        """Fetch costs with specific tag grouping.

        This provides better cost allocation by grouping costs by tags.

        Args:
            start_date: Start date
            end_date: End date
            tag_key: Tag key to group by (e.g., "project", "team", "environment")

        Returns:
            List of CloudCost objects with tag-based allocation
        """
        logger.info(f"Fetching AWS costs with tag grouping: {tag_key} ({start_date} to {end_date})")

        try:
            response = self.ce_client.get_cost_and_usage(
                TimePeriod={
                    "Start": start_date.strftime("%Y-%m-%d"),
                    "End": end_date.strftime("%Y-%m-%d"),
                },
                Granularity="DAILY",
                Metrics=["UnblendedCost"],
                GroupBy=[
                    {"Type": "DIMENSION", "Key": "SERVICE"},
                    {"Type": "TAG", "Key": tag_key},
                ],
            )

            costs = []

            for result in response["ResultsByTime"]:
                timestamp = datetime.strptime(result["TimePeriod"]["Start"], "%Y-%m-%d")

                for group in result["Groups"]:
                    keys = group["Keys"]
                    service = keys[0] if len(keys) > 0 else "Unknown"
                    tag_value = keys[1] if len(keys) > 1 else "untagged"

                    amount = Decimal(group["Metrics"]["UnblendedCost"]["Amount"])

                    if amount == 0:
                        continue

                    # Build tags dict
                    tags = {tag_key: tag_value}
                    project, team, environment = derive_cost_allocation(tags)

                    cost = CloudCost(
                        time=timestamp,
                        cloud_provider=CloudProvider.AWS,
                        account_id=self.account_id,
                        service=service,
                        cost=amount,
                        tags=tags,
                        project=project,
                        team=team,
                        environment=environment,
                    )

                    costs.append(cost)

            logger.info(f"Fetched {len(costs)} tagged cost records from AWS")
            return costs

        except (ClientError, BotoCoreError) as e:
            logger.error(f"Error fetching AWS tagged costs: {e}")
            raise

    async def get_resource_utilization(self, instance_id: str, metric_name: str, days: int = 14) -> dict[str, Any]:
        """Get CloudWatch metrics for a resource (for rightsizing recommendations).

        Args:
            instance_id: Resource ID (e.g., EC2 instance ID)
            metric_name: Metric name (e.g., CPUUtilization, MemoryUtilization)
            days: Number of days to query

        Returns:
            Utilization statistics
        """
        try:
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(days=days)

            response = self.cloudwatch_client.get_metric_statistics(
                Namespace="AWS/EC2",
                MetricName=metric_name,
                Dimensions=[{"Name": "InstanceId", "Value": instance_id}],
                StartTime=start_time,
                EndTime=end_time,
                Period=3600,  # 1 hour
                Statistics=["Average", "Maximum"],
            )

            datapoints = response["Datapoints"]

            if not datapoints:
                return {
                    "average": 0.0,
                    "maximum": 0.0,
                    "p95": 0.0,
                    "datapoints": 0,
                }

            averages = [dp["Average"] for dp in datapoints]
            maximums = [dp["Maximum"] for dp in datapoints]

            return {
                "average": sum(averages) / len(averages),
                "maximum": max(maximums),
                "p95": sorted(averages)[int(len(averages) * 0.95)] if len(averages) > 0 else 0.0,
                "datapoints": len(datapoints),
            }

        except (ClientError, BotoCoreError) as e:
            logger.error(f"Error fetching CloudWatch metrics: {e}")
            return {"average": 0.0, "maximum": 0.0, "p95": 0.0, "datapoints": 0}

    async def detect_idle_resources(self) -> list[dict[str, Any]]:
        """Detect idle EC2 instances, EBS volumes, and other resources.

        Returns:
            List of idle resources with savings potential
        """
        idle_resources = []

        # Detect stopped EC2 instances
        ec2_client = self.session.client("ec2")

        try:
            response = ec2_client.describe_instances(Filters=[{"Name": "instance-state-name", "Values": ["stopped"]}])

            for reservation in response["Reservations"]:
                for instance in reservation["Instances"]:
                    instance_id = instance["InstanceId"]
                    instance_type = instance["InstanceType"]

                    # Estimate cost (simplified pricing)
                    hourly_cost = self._estimate_ec2_cost(instance_type)
                    monthly_cost = hourly_cost * 730  # 730 hours/month

                    idle_resources.append(
                        {
                            "resource_type": "EC2 Instance",
                            "resource_id": instance_id,
                            "resource_name": instance.get("Tags", [{}])[0].get("Value", "Unnamed")
                            if instance.get("Tags")
                            else "Unnamed",
                            "status": "stopped",
                            "monthly_cost": monthly_cost,
                            "recommendation": "Terminate if no longer needed or use Auto Scaling",
                        }
                    )

        except (ClientError, BotoCoreError) as e:
            logger.error(f"Error detecting idle EC2 instances: {e}")

        # Detect unattached EBS volumes
        try:
            response = ec2_client.describe_volumes(Filters=[{"Name": "status", "Values": ["available"]}])

            for volume in response["Volumes"]:
                volume_id = volume["VolumeId"]
                size_gb = volume["Size"]
                volume_type = volume["VolumeType"]

                # Estimate cost (simplified: $0.10/GB/month for gp3)
                monthly_cost = size_gb * 0.10

                idle_resources.append(
                    {
                        "resource_type": "EBS Volume",
                        "resource_id": volume_id,
                        "resource_name": f"{size_gb}GB {volume_type}",
                        "status": "unattached",
                        "monthly_cost": monthly_cost,
                        "recommendation": "Delete if no longer needed or create snapshot",
                    }
                )

        except (ClientError, BotoCoreError) as e:
            logger.error(f"Error detecting unattached EBS volumes: {e}")

        logger.info(f"Detected {len(idle_resources)} idle resources")
        return idle_resources

    def _estimate_ec2_cost(self, instance_type: str) -> float:
        """Estimate hourly cost for EC2 instance type.

        Note: This is a simplified pricing model. In production, use AWS Pricing API.

        Args:
            instance_type: EC2 instance type (e.g., "m5.large")

        Returns:
            Estimated hourly cost in USD
        """
        # Simplified pricing (actual prices vary by region and pricing model)
        pricing = {
            "t3.micro": 0.0104,
            "t3.small": 0.0208,
            "t3.medium": 0.0416,
            "t3.large": 0.0832,
            "m5.large": 0.096,
            "m5.xlarge": 0.192,
            "m5.2xlarge": 0.384,
            "m5.4xlarge": 0.768,
            "r5.large": 0.126,
            "r5.xlarge": 0.252,
            "r5.2xlarge": 0.504,
            "c5.large": 0.085,
            "c5.xlarge": 0.17,
            "c5.2xlarge": 0.34,
        }

        return pricing.get(instance_type, 0.10)  # Default $0.10/hour

    async def close(self):
        """Close AWS clients (cleanup)."""
        # boto3 clients don't need explicit closing
        pass
