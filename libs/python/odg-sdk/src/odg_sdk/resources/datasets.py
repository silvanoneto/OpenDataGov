"""Dataset resource API."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

if TYPE_CHECKING:
    from odg_sdk.client import OpenDataGovClient


class Dataset(BaseModel):
    """Dataset model."""

    id: str
    name: str
    description: str | None = None
    classification: str | None = None
    layer: str | None = None
    quality_score: float | None = None
    owner: str | None = None
    tags: list[str] = []
    last_updated: str | None = None


class DatasetResource:
    """Dataset resource manager.

    Provides methods to interact with datasets via GraphQL.
    """

    def __init__(self, client: OpenDataGovClient):
        self.client = client

    async def get(self, dataset_id: str, include_lineage: bool = False) -> dict[str, Any]:
        """Get dataset by ID.

        Args:
            dataset_id: Dataset identifier
            include_lineage: Include upstream/downstream lineage

        Returns:
            Dataset with optional lineage

        Example:
            >>> dataset = await client.datasets.get("gold.customers", include_lineage=True)
        """
        if include_lineage:
            query = """
                query GetDataset($id: ID!) {
                    dataset(id: $id) {
                        id
                        name
                        description
                        classification
                        layer
                        qualityScore
                        owner
                        tags
                        lastUpdated
                        upstreamLineage {
                            id
                            name
                            layer
                        }
                        downstreamLineage {
                            id
                            name
                            layer
                        }
                    }
                }
            """
        else:
            query = """
                query GetDataset($id: ID!) {
                    dataset(id: $id) {
                        id
                        name
                        description
                        classification
                        layer
                        qualityScore
                        owner
                        tags
                        lastUpdated
                    }
                }
            """

        result = await self.client.graphql(query, {"id": dataset_id})
        return result["dataset"]

    async def list(
        self,
        *,
        domain_id: str | None = None,
        layer: str | None = None,
        classification: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """List datasets with optional filters.

        Args:
            domain_id: Filter by domain
            layer: Filter by layer (bronze, silver, gold, platinum)
            classification: Filter by classification
            limit: Maximum number of results

        Returns:
            List of datasets

        Example:
            >>> datasets = await client.datasets.list(layer="gold", limit=10)
        """
        query = """
            query ListDatasets($domainId: String, $layer: String, $limit: Int) {
                datasets(domainId: $domainId, layer: $layer, limit: $limit) {
                    id
                    name
                    description
                    classification
                    layer
                    qualityScore
                    owner
                    tags
                    lastUpdated
                }
            }
        """

        variables: dict[str, Any] = {"limit": limit}
        if domain_id:
            variables["domainId"] = domain_id
        if layer:
            variables["layer"] = layer

        result = await self.client.graphql(query, variables)
        return result["datasets"]

    async def get_lineage(self, dataset_id: str, depth: int = 3) -> dict[str, Any]:
        """Get lineage graph for a dataset.

        Args:
            dataset_id: Dataset identifier
            depth: How many levels to traverse

        Returns:
            Lineage graph with nodes and edges

        Example:
            >>> lineage = await client.datasets.get_lineage("gold.sales", depth=5)
        """
        query = """
            query GetLineage($datasetId: ID!, $depth: Int) {
                lineage(datasetId: $datasetId, depth: $depth) {
                    nodes {
                        id
                        name
                        type
                        layer
                        classification
                    }
                    edges {
                        from
                        to
                        label
                        transformationType
                    }
                }
            }
        """

        result = await self.client.graphql(query, {"datasetId": dataset_id, "depth": depth})
        return result["lineage"]

    async def search(
        self,
        query: str = "",
        *,
        domain: str | None = None,
        layer: str | None = None,
        classification: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Search datasets via REST API.

        Args:
            query: Search query string
            domain: Filter by domain
            layer: Filter by layer
            classification: Filter by classification
            limit: Maximum number of results

        Returns:
            List of matching datasets

        Example:
            >>> results = await client.datasets.search("customer", domain="crm")
        """
        params: dict[str, Any] = {"query": query, "limit": limit}
        if domain:
            params["domain"] = domain
        if layer:
            params["layer"] = layer
        if classification:
            params["classification"] = classification

        data = await self.client.request(
            "GET",
            "/api/v1/self-service/datasets/search",
            params=params,
        )
        return data
