"""Tests for DatasetResource."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from odg_sdk import OpenDataGovClient

if TYPE_CHECKING:
    from pytest_httpx import HTTPXMock


@pytest.mark.asyncio
async def test_get_dataset(httpx_mock: HTTPXMock):
    """Test getting a dataset."""
    httpx_mock.add_response(
        json={
            "data": {
                "dataset": {
                    "id": "gold.customers",
                    "name": "customers",
                    "description": "Customer data",
                    "classification": "sensitive",
                    "layer": "gold",
                    "qualityScore": 0.95,
                    "owner": "data-team",
                    "tags": ["pii", "crm"],
                    "lastUpdated": "2024-02-08T10:00:00Z",
                }
            }
        }
    )

    async with OpenDataGovClient("http://localhost:8000") as client:
        dataset = await client.datasets.get("gold.customers")

        assert dataset["id"] == "gold.customers"
        assert dataset["layer"] == "gold"
        assert dataset["qualityScore"] == 0.95


@pytest.mark.asyncio
async def test_get_dataset_with_lineage(httpx_mock: HTTPXMock):
    """Test getting a dataset with lineage."""
    httpx_mock.add_response(
        json={
            "data": {
                "dataset": {
                    "id": "gold.sales",
                    "name": "sales",
                    "layer": "gold",
                    "upstreamLineage": [{"id": "silver.sales", "name": "sales", "layer": "silver"}],
                    "downstreamLineage": [{"id": "platinum.analytics", "name": "analytics", "layer": "platinum"}],
                }
            }
        }
    )

    async with OpenDataGovClient("http://localhost:8000") as client:
        dataset = await client.datasets.get("gold.sales", include_lineage=True)

        assert len(dataset["upstreamLineage"]) == 1
        assert len(dataset["downstreamLineage"]) == 1


@pytest.mark.asyncio
async def test_list_datasets(httpx_mock: HTTPXMock):
    """Test listing datasets."""
    httpx_mock.add_response(
        json={
            "data": {
                "datasets": [
                    {"id": "gold.customers", "name": "customers", "layer": "gold"},
                    {"id": "gold.sales", "name": "sales", "layer": "gold"},
                ]
            }
        }
    )

    async with OpenDataGovClient("http://localhost:8000") as client:
        datasets = await client.datasets.list(layer="gold", limit=50)

        assert len(datasets) == 2
        assert datasets[0]["id"] == "gold.customers"


@pytest.mark.asyncio
async def test_get_lineage(httpx_mock: HTTPXMock):
    """Test getting lineage graph."""
    httpx_mock.add_response(
        json={
            "data": {
                "lineage": {
                    "nodes": [
                        {"id": "gold.sales", "name": "sales", "layer": "gold"},
                        {"id": "silver.sales", "name": "sales", "layer": "silver"},
                    ],
                    "edges": [{"from": "silver.sales", "to": "gold.sales", "label": "promote"}],
                }
            }
        }
    )

    async with OpenDataGovClient("http://localhost:8000") as client:
        lineage = await client.datasets.get_lineage("gold.sales", depth=3)

        assert len(lineage["nodes"]) == 2
        assert len(lineage["edges"]) == 1


@pytest.mark.asyncio
async def test_search_datasets(httpx_mock: HTTPXMock):
    """Test searching datasets."""
    httpx_mock.add_response(
        json=[
            {
                "dataset_id": "gold.customers",
                "name": "customers",
                "description": "Customer master data",
                "layer": "gold",
            }
        ]
    )

    async with OpenDataGovClient("http://localhost:8000") as client:
        results = await client.datasets.search(query="customer", domain="crm", layer="gold", limit=20)

        assert len(results) == 1
        assert results[0]["dataset_id"] == "gold.customers"
