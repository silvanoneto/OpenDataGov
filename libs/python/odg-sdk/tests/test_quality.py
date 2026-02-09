"""Tests for QualityResource."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from odg_sdk import OpenDataGovClient

if TYPE_CHECKING:
    from pytest_httpx import HTTPXMock


@pytest.mark.asyncio
async def test_validate_dataset(httpx_mock: HTTPXMock):
    """Test validating a dataset."""
    httpx_mock.add_response(
        json={
            "dataset_id": "gold.sales",
            "success": True,
            "overall_score": 0.98,
            "dimensions": [
                {"dimension_name": "completeness", "score": 0.99, "status": "passed"},
                {"dimension_name": "accuracy", "score": 0.97, "status": "passed"},
            ],
            "validated_at": "2024-02-08T10:00:00Z",
        }
    )

    async with OpenDataGovClient("http://localhost:8000") as client:
        report = await client.quality.validate(
            dataset_id="gold.sales", layer="gold", expectation_suite_names=["gold_suite"]
        )

        assert report["success"] is True
        assert report["overall_score"] == 0.98
        assert len(report["dimensions"]) == 2


@pytest.mark.asyncio
async def test_get_quality_report(httpx_mock: HTTPXMock):
    """Test getting quality report via GraphQL."""
    httpx_mock.add_response(
        json={
            "data": {
                "qualityReport": {
                    "datasetId": "gold.customers",
                    "overallScore": 0.95,
                    "dimensions": [
                        {"name": "completeness", "score": 0.96, "status": "passed"},
                        {"name": "accuracy", "score": 0.94, "status": "passed"},
                    ],
                    "validatedAt": "2024-02-08T10:00:00Z",
                    "validatedBy": "quality-service",
                    "expectationResults": [
                        {
                            "expectationType": "expect_column_values_to_not_be_null",
                            "success": True,
                            "observedValue": None,
                            "details": {},
                        }
                    ],
                }
            }
        }
    )

    async with OpenDataGovClient("http://localhost:8000") as client:
        report = await client.quality.get_report("gold.customers")

        assert report["datasetId"] == "gold.customers"
        assert report["overallScore"] == 0.95
        assert len(report["dimensions"]) == 2
        assert len(report["expectationResults"]) == 1
