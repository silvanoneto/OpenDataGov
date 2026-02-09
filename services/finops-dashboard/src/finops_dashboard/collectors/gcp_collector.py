"""GCP Cost Collector - Fetches cost data from GCP Billing API.

Collects daily cost and usage data from BigQuery billing export.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from finops_dashboard.models import CloudCost, CloudProvider, derive_cost_allocation
from google.cloud import bigquery
from google.cloud.exceptions import GoogleCloudError

logger = logging.getLogger(__name__)


class GCPCostCollector:
    """Collects cost data from GCP BigQuery billing export."""

    def __init__(
        self,
        project_id: str,
        billing_dataset: str = "billing_export",
        billing_table_prefix: str = "gcp_billing_export_v1",
        credentials_path: str | None = None,
    ):
        """Initialize GCP BigQuery client.

        Args:
            project_id: GCP project ID
            billing_dataset: BigQuery dataset containing billing export
            billing_table_prefix: Table prefix for billing export
            credentials_path: Path to service account JSON (defaults to application default)
        """
        self.project_id = project_id
        self.billing_dataset = billing_dataset
        self.billing_table_prefix = billing_table_prefix

        # Initialize BigQuery client
        if credentials_path:
            from google.oauth2 import service_account

            credentials = service_account.Credentials.from_service_account_file(credentials_path)
            self.bq_client = bigquery.Client(project=project_id, credentials=credentials)
        else:
            self.bq_client = bigquery.Client(project=project_id)

    async def fetch_costs(self, start_date: date, end_date: date) -> list[CloudCost]:
        """Fetch costs from GCP BigQuery billing export.

        Args:
            start_date: Start date (inclusive)
            end_date: End date (exclusive)

        Returns:
            List of CloudCost objects
        """
        logger.info(f"Fetching GCP costs from {start_date} to {end_date}")

        # Build BigQuery query
        query = f"""
        SELECT
          DATE(usage_start_time) AS usage_date,
          service.description AS service_name,
          location.region AS region,
          project.id AS project_id,
          SUM(cost) AS total_cost,
          currency,
          TO_JSON_STRING(labels) AS labels_json
        FROM
          `{self.project_id}.{self.billing_dataset}.{self.billing_table_prefix}_*`
        WHERE
          DATE(_PARTITIONTIME) BETWEEN '{start_date}' AND '{end_date}'
          AND cost > 0
        GROUP BY
          usage_date,
          service_name,
          region,
          project_id,
          currency,
          labels_json
        ORDER BY
          usage_date DESC,
          total_cost DESC
        """

        try:
            query_job = self.bq_client.query(query)
            results = query_job.result()

            costs = []

            for row in results:
                import json

                timestamp = datetime.combine(row["usage_date"], datetime.min.time())

                # Parse labels (tags)
                labels_str = row.get("labels_json", "{}")
                try:
                    labels = json.loads(labels_str) if labels_str else {}
                except json.JSONDecodeError:
                    labels = {}

                # Derive cost allocation
                project, team, environment = derive_cost_allocation(labels)

                cost = CloudCost(
                    time=timestamp,
                    cloud_provider=CloudProvider.GCP,
                    account_id=row["project_id"],
                    service=row["service_name"],
                    region=row.get("region"),
                    cost=Decimal(str(row["total_cost"])),
                    currency=row.get("currency", "USD"),
                    tags=labels,
                    project=project,
                    team=team,
                    environment=environment,
                )

                costs.append(cost)

            logger.info(f"Fetched {len(costs)} cost records from GCP")
            return costs

        except GoogleCloudError as e:
            logger.error(f"Error fetching GCP costs: {e}")
            raise

    async def fetch_detailed_costs_with_labels(
        self,
        start_date: date,
        end_date: date,
        label_key: str = "project",
    ) -> list[CloudCost]:
        """Fetch costs grouped by specific label.

        Args:
            start_date: Start date
            end_date: End date
            label_key: Label key to filter by

        Returns:
            List of CloudCost objects
        """
        logger.info(f"Fetching GCP costs with label grouping: {label_key} ({start_date} to {end_date})")

        query = f"""
        SELECT
          DATE(usage_start_time) AS usage_date,
          service.description AS service_name,
          location.region AS region,
          project.id AS project_id,
          labels.value AS label_value,
          SUM(cost) AS total_cost,
          currency
        FROM
          `{self.project_id}.{self.billing_dataset}.{self.billing_table_prefix}_*`,
          UNNEST(labels) AS labels
        WHERE
          DATE(_PARTITIONTIME) BETWEEN '{start_date}' AND '{end_date}'
          AND labels.key = '{label_key}'
          AND cost > 0
        GROUP BY
          usage_date,
          service_name,
          region,
          project_id,
          label_value,
          currency
        ORDER BY
          usage_date DESC,
          total_cost DESC
        """

        try:
            query_job = self.bq_client.query(query)
            results = query_job.result()

            costs = []

            for row in results:
                timestamp = datetime.combine(row["usage_date"], datetime.min.time())

                tags = {label_key: row["label_value"]}
                project, team, environment = derive_cost_allocation(tags)

                cost = CloudCost(
                    time=timestamp,
                    cloud_provider=CloudProvider.GCP,
                    account_id=row["project_id"],
                    service=row["service_name"],
                    region=row.get("region"),
                    cost=Decimal(str(row["total_cost"])),
                    currency=row.get("currency", "USD"),
                    tags=tags,
                    project=project,
                    team=team,
                    environment=environment,
                )

                costs.append(cost)

            logger.info(f"Fetched {len(costs)} labeled cost records from GCP")
            return costs

        except GoogleCloudError as e:
            logger.error(f"Error fetching GCP labeled costs: {e}")
            raise

    async def detect_idle_resources(self) -> list[dict[str, Any]]:
        """Detect idle GCP resources (GCE instances, disks, etc.).

        Returns:
            List of idle resources with savings potential
        """
        idle_resources = []

        # Query for stopped Compute Engine instances
        query = f"""
        SELECT
          sku.description AS resource_type,
          labels.value AS instance_name,
          project.id AS project_id,
          SUM(cost) AS monthly_cost
        FROM
          `{self.project_id}.{self.billing_dataset}.{self.billing_table_prefix}_*`,
          UNNEST(labels) AS labels
        WHERE
          DATE(_PARTITIONTIME) >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
          AND service.description = 'Compute Engine'
          AND sku.description LIKE '%Instance%'
          AND labels.key = 'instance_name'
          AND cost > 0
        GROUP BY
          resource_type,
          instance_name,
          project_id
        HAVING
          monthly_cost < 10  -- Likely idle/stopped
        ORDER BY
          monthly_cost DESC
        """

        try:
            query_job = self.bq_client.query(query)
            results = query_job.result()

            for row in results:
                idle_resources.append(
                    {
                        "resource_type": "GCE Instance",
                        "resource_id": row["instance_name"],
                        "resource_name": row["instance_name"],
                        "project_id": row["project_id"],
                        "status": "potentially_idle",
                        "monthly_cost": float(row["monthly_cost"]),
                        "recommendation": "Review utilization and consider stopping or deletion",
                    }
                )

            logger.info(f"Detected {len(idle_resources)} potentially idle GCP resources")
            return idle_resources

        except GoogleCloudError as e:
            logger.error(f"Error detecting idle GCP resources: {e}")
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
        query = f"""
        SELECT
          service.description AS service_name,
          SUM(cost) AS total_cost,
          currency
        FROM
          `{self.project_id}.{self.billing_dataset}.{self.billing_table_prefix}_*`
        WHERE
          DATE(_PARTITIONTIME) BETWEEN '{start_date}' AND '{end_date}'
          AND cost > 0
        GROUP BY
          service_name,
          currency
        ORDER BY
          total_cost DESC
        LIMIT {limit}
        """

        try:
            query_job = self.bq_client.query(query)
            results = query_job.result()

            top_spenders = []

            for row in results:
                top_spenders.append(
                    {
                        "service": row["service_name"],
                        "cost": float(row["total_cost"]),
                        "currency": row.get("currency", "USD"),
                    }
                )

            return top_spenders

        except GoogleCloudError as e:
            logger.error(f"Error fetching top spenders: {e}")
            return []

    async def close(self):
        """Close BigQuery client."""
        self.bq_client.close()
