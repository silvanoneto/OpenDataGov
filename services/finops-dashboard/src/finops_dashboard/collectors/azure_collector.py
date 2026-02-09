"""Azure Cost Collector - Fetches cost data from Azure Cost Management API.

Collects daily cost and usage data with resource group and tag breakdowns.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from azure.core.exceptions import AzureError
from azure.identity import ClientSecretCredential, DefaultAzureCredential
from azure.mgmt.costmanagement import CostManagementClient
from azure.mgmt.costmanagement.models import (
    GranularityType,
    QueryAggregation,
    QueryDataset,
    QueryDefinition,
    QueryGrouping,
    QueryTimePeriod,
    TimeframeType,
)
from finops_dashboard.models import CloudCost, CloudProvider, derive_cost_allocation

logger = logging.getLogger(__name__)


class AzureCostCollector:
    """Collects cost data from Azure Cost Management API."""

    def __init__(
        self,
        subscription_id: str,
        tenant_id: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
    ):
        """Initialize Azure Cost Management client.

        Args:
            subscription_id: Azure subscription ID
            tenant_id: Azure AD tenant ID (optional, for service principal)
            client_id: Service principal client ID (optional)
            client_secret: Service principal secret (optional)
        """
        self.subscription_id = subscription_id
        self.scope = f"/subscriptions/{subscription_id}"

        # Initialize credential
        if tenant_id and client_id and client_secret:
            self.credential = ClientSecretCredential(
                tenant_id=tenant_id,
                client_id=client_id,
                client_secret=client_secret,
            )
        else:
            # Use DefaultAzureCredential (managed identity, Azure CLI, etc.)
            self.credential = DefaultAzureCredential()

        # Initialize Cost Management client
        self.client = CostManagementClient(
            credential=self.credential,
            base_url="https://management.azure.com",
        )

    async def fetch_costs(self, start_date: date, end_date: date) -> list[CloudCost]:
        """Fetch costs from Azure Cost Management API.

        Args:
            start_date: Start date (inclusive)
            end_date: End date (exclusive)

        Returns:
            List of CloudCost objects
        """
        logger.info(f"Fetching Azure costs from {start_date} to {end_date}")

        try:
            # Build query definition
            query = QueryDefinition(
                type="Usage",
                timeframe=TimeframeType.CUSTOM,
                time_period=QueryTimePeriod(
                    from_property=start_date.isoformat(),
                    to=end_date.isoformat(),
                ),
                dataset=QueryDataset(
                    granularity=GranularityType.DAILY,
                    aggregation={"totalCost": QueryAggregation(name="Cost", function="Sum")},
                    grouping=[
                        QueryGrouping(type="Dimension", name="ServiceName"),
                        QueryGrouping(type="Dimension", name="ResourceLocation"),
                        QueryGrouping(type="Dimension", name="ResourceGroupName"),
                    ],
                ),
            )

            # Execute query
            result = self.client.query.usage(scope=self.scope, parameters=query)

            costs = []

            # Parse results
            if not result.rows:
                logger.warning("No cost data returned from Azure")
                return costs

            # Column indexes
            columns = {col.name: idx for idx, col in enumerate(result.columns)}

            for row in result.rows:
                # Extract data
                cost_value = row[columns["Cost"]]
                service_name = row[columns["ServiceName"]]
                location = row[columns["ResourceLocation"]]
                resource_group = row[columns["ResourceGroupName"]]
                usage_date = row[columns.get("UsageDate", 0)]  # If available

                # Parse date
                if isinstance(usage_date, str):
                    timestamp = datetime.fromisoformat(usage_date.replace("Z", "+00:00"))
                else:
                    timestamp = datetime.combine(start_date, datetime.min.time())

                # Fetch tags for resource group (simplified)
                tags = await self._fetch_tags_for_resource_group(resource_group)

                # Derive cost allocation
                project, team, environment = derive_cost_allocation(tags)

                cost = CloudCost(
                    time=timestamp,
                    cloud_provider=CloudProvider.AZURE,
                    account_id=self.subscription_id,
                    service=service_name,
                    region=location if location != "Unassigned" else None,
                    cost=Decimal(str(cost_value)),
                    currency="USD",
                    tags=tags,
                    project=project,
                    team=team,
                    environment=environment,
                )

                costs.append(cost)

            logger.info(f"Fetched {len(costs)} cost records from Azure")
            return costs

        except AzureError as e:
            logger.error(f"Error fetching Azure costs: {e}")
            raise

    async def fetch_detailed_costs_with_tags(
        self,
        start_date: date,
        end_date: date,
        tag_key: str = "project",
    ) -> list[CloudCost]:
        """Fetch costs with specific tag grouping.

        Args:
            start_date: Start date
            end_date: End date
            tag_key: Tag key to group by (e.g., "project", "team", "environment")

        Returns:
            List of CloudCost objects with tag-based allocation
        """
        logger.info(f"Fetching Azure costs with tag grouping: {tag_key} ({start_date} to {end_date})")

        try:
            # Build query with tag grouping
            query = QueryDefinition(
                type="Usage",
                timeframe=TimeframeType.CUSTOM,
                time_period=QueryTimePeriod(
                    from_property=start_date.isoformat(),
                    to=end_date.isoformat(),
                ),
                dataset=QueryDataset(
                    granularity=GranularityType.DAILY,
                    aggregation={"totalCost": QueryAggregation(name="Cost", function="Sum")},
                    grouping=[
                        QueryGrouping(type="Dimension", name="ServiceName"),
                        QueryGrouping(type="Tag", name=tag_key),
                    ],
                ),
            )

            result = self.client.query.usage(scope=self.scope, parameters=query)

            costs = []
            columns = {col.name: idx for idx, col in enumerate(result.columns)}

            for row in result.rows:
                cost_value = row[columns["Cost"]]
                service_name = row[columns["ServiceName"]]
                tag_value = row[columns.get(tag_key, "")]
                usage_date = row[columns.get("UsageDate", 0)]

                if isinstance(usage_date, str):
                    timestamp = datetime.fromisoformat(usage_date.replace("Z", "+00:00"))
                else:
                    timestamp = datetime.combine(start_date, datetime.min.time())

                tags = {tag_key: tag_value} if tag_value else {}
                project, team, environment = derive_cost_allocation(tags)

                cost = CloudCost(
                    time=timestamp,
                    cloud_provider=CloudProvider.AZURE,
                    account_id=self.subscription_id,
                    service=service_name,
                    cost=Decimal(str(cost_value)),
                    tags=tags,
                    project=project,
                    team=team,
                    environment=environment,
                )

                costs.append(cost)

            logger.info(f"Fetched {len(costs)} tagged cost records from Azure")
            return costs

        except AzureError as e:
            logger.error(f"Error fetching Azure tagged costs: {e}")
            raise

    async def _fetch_tags_for_resource_group(self, resource_group: str) -> dict[str, Any]:
        """Fetch tags for a specific resource group.

        Note: This is a simplified implementation. In production, you would
        query Azure Resource Graph or Resource Manager API.

        Args:
            resource_group: Resource group name

        Returns:
            Tags dictionary
        """
        # Simplified: Return empty tags
        # In production, use:
        # - Azure Resource Graph API
        # - azure.mgmt.resource.ResourceManagementClient
        return {}

    async def detect_idle_resources(self) -> list[dict[str, Any]]:
        """Detect idle Azure resources (stopped VMs, unattached disks).

        Returns:
            List of idle resources with savings potential
        """
        idle_resources = []

        try:
            # Query for low-cost resources (potential idle candidates)
            query = QueryDefinition(
                type="Usage",
                timeframe=TimeframeType.MONTHLY_TO_DATE,
                dataset=QueryDataset(
                    granularity=GranularityType.NONE,
                    aggregation={"totalCost": QueryAggregation(name="Cost", function="Sum")},
                    grouping=[
                        QueryGrouping(type="Dimension", name="ResourceId"),
                        QueryGrouping(type="Dimension", name="ServiceName"),
                    ],
                    filter={
                        "And": [
                            {
                                "Dimensions": {
                                    "Name": "ServiceName",
                                    "Operator": "In",
                                    "Values": [
                                        "Virtual Machines",
                                        "Storage",
                                        "Azure App Service",
                                    ],
                                }
                            }
                        ]
                    },
                ),
            )

            result = self.client.query.usage(scope=self.scope, parameters=query)

            if not result.rows:
                return idle_resources

            columns = {col.name: idx for idx, col in enumerate(result.columns)}

            for row in result.rows:
                cost = row[columns["Cost"]]
                resource_id = row[columns.get("ResourceId", "")]
                service_name = row[columns["ServiceName"]]

                # Flag resources with very low cost (< $10/month)
                if cost < 10 and resource_id:
                    resource_name = resource_id.split("/")[-1] if "/" in resource_id else resource_id

                    idle_resources.append(
                        {
                            "resource_type": service_name,
                            "resource_id": resource_id,
                            "resource_name": resource_name,
                            "status": "potentially_idle",
                            "monthly_cost": float(cost),
                            "recommendation": "Review utilization and consider stopping or deletion",
                        }
                    )

            logger.info(f"Detected {len(idle_resources)} potentially idle Azure resources")
            return idle_resources

        except AzureError as e:
            logger.error(f"Error detecting idle Azure resources: {e}")
            return []

    async def get_top_spenders(self, start_date: date, end_date: date, limit: int = 10) -> list[dict[str, Any]]:
        """Get top spending services.

        Args:
            start_date: Start date
            end_date: End date
            limit: Number of top spenders to return

        Returns:
            List of top spending services
        """
        try:
            query = QueryDefinition(
                type="Usage",
                timeframe=TimeframeType.CUSTOM,
                time_period=QueryTimePeriod(
                    from_property=start_date.isoformat(),
                    to=end_date.isoformat(),
                ),
                dataset=QueryDataset(
                    granularity=GranularityType.NONE,
                    aggregation={"totalCost": QueryAggregation(name="Cost", function="Sum")},
                    grouping=[
                        QueryGrouping(type="Dimension", name="ServiceName"),
                    ],
                ),
            )

            result = self.client.query.usage(scope=self.scope, parameters=query)

            top_spenders = []
            columns = {col.name: idx for idx, col in enumerate(result.columns)}

            for row in result.rows:
                service_name = row[columns["ServiceName"]]
                total_cost = row[columns["Cost"]]

                top_spenders.append(
                    {
                        "service": service_name,
                        "cost": float(total_cost),
                        "currency": "USD",
                    }
                )

            # Sort by cost and limit
            top_spenders.sort(key=lambda x: x["cost"], reverse=True)
            return top_spenders[:limit]

        except AzureError as e:
            logger.error(f"Error fetching top spenders: {e}")
            return []

    async def get_resource_utilization(self, resource_id: str, metric_name: str, days: int = 14) -> dict[str, Any]:
        """Get Azure Monitor metrics for a resource (for rightsizing recommendations).

        Args:
            resource_id: Resource ID (e.g., VM resource ID)
            metric_name: Metric name (e.g., "Percentage CPU", "Available Memory Bytes")
            days: Number of days to query

        Returns:
            Utilization statistics
        """
        try:
            from datetime import timedelta

            from azure.mgmt.monitor import MonitorManagementClient

            monitor_client = MonitorManagementClient(
                credential=self.credential,
                subscription_id=self.subscription_id,
            )

            end_time = datetime.utcnow()
            start_time = end_time - timedelta(days=days)

            # Query metrics
            metrics_data = monitor_client.metrics.list(
                resource_uri=resource_id,
                timespan=f"{start_time.isoformat()}/{end_time.isoformat()}",
                interval="PT1H",
                metricnames=metric_name,
                aggregation="Average,Maximum",
            )

            # Parse metrics
            averages = []
            maximums = []

            for metric in metrics_data.value:
                for timeseries in metric.timeseries:
                    for data_point in timeseries.data:
                        if data_point.average is not None:
                            averages.append(data_point.average)
                        if data_point.maximum is not None:
                            maximums.append(data_point.maximum)

            if not averages:
                return {
                    "average": 0.0,
                    "maximum": 0.0,
                    "p95": 0.0,
                    "datapoints": 0,
                }

            return {
                "average": sum(averages) / len(averages),
                "maximum": max(maximums) if maximums else 0.0,
                "p95": sorted(averages)[int(len(averages) * 0.95)] if len(averages) > 0 else 0.0,
                "datapoints": len(averages),
            }

        except Exception as e:
            logger.error(f"Error fetching Azure Monitor metrics: {e}")
            return {"average": 0.0, "maximum": 0.0, "p95": 0.0, "datapoints": 0}

    async def close(self):
        """Close Azure clients."""
        # Azure SDK handles connection pooling automatically
        pass
