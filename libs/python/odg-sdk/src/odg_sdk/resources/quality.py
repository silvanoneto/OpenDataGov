"""Quality resource API."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

if TYPE_CHECKING:
    from odg_sdk.client import OpenDataGovClient


class QualityReport(BaseModel):
    """Quality report model."""

    dataset_id: str
    overall_score: float
    validated_at: str
    validated_by: str | None = None
    dimensions: list[dict[str, Any]] = []
    expectation_results: list[dict[str, Any]] = []


class QualityResource:
    """Quality resource manager.

    Provides methods to interact with data quality validation.
    """

    def __init__(self, client: OpenDataGovClient):
        self.client = client

    async def validate(
        self,
        dataset_id: str,
        layer: str,
        expectation_suite_names: list[str] | None = None,
    ) -> dict[str, Any]:
        """Validate dataset quality.

        Args:
            dataset_id: Dataset identifier
            layer: Data layer (bronze, silver, gold, platinum)
            expectation_suite_names: Optional list of expectation suites to run

        Returns:
            Validation report

        Example:
            >>> report = await client.quality.validate(
            ...     dataset_id="gold.sales",
            ...     layer="gold",
            ...     expectation_suite_names=["gold_suite"]
            ... )
        """
        data = await self.client.request(
            "POST",
            "/api/v1/validate",
            json={
                "dataset_id": dataset_id,
                "layer": layer,
                "expectation_suite_names": expectation_suite_names or [],
            },
        )
        return data

    async def get_report(self, dataset_id: str) -> dict[str, Any]:
        """Get quality report for a dataset via GraphQL.

        Args:
            dataset_id: Dataset identifier

        Returns:
            Quality report

        Example:
            >>> report = await client.quality.get_report("gold.customers")
        """
        query = """
            query GetQualityReport($datasetId: ID!) {
                qualityReport(datasetId: $datasetId) {
                    datasetId
                    overallScore
                    dimensions {
                        name
                        score
                        status
                        details
                    }
                    validatedAt
                    validatedBy
                    expectationResults {
                        expectationType
                        success
                        observedValue
                        details
                    }
                }
            }
        """

        result = await self.client.graphql(query, {"datasetId": dataset_id})
        return result["qualityReport"]
