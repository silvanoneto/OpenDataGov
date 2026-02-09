"""Tests for GraphQL schema."""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from odg_core.graphql.schema import schema


@pytest.fixture
def mock_context() -> dict[str, Any]:
    """Create mock context for GraphQL execution."""
    mock_session = AsyncMock(spec=AsyncSession)

    # Configure mock to return empty results
    from unittest.mock import MagicMock

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_result.scalars.return_value.all.return_value = []
    mock_session.execute.return_value = mock_result

    return {"db_session": mock_session}


@pytest.mark.asyncio
async def test_schema_query_type_exists() -> None:
    """Test that schema has Query type."""
    # Verify schema is initialized properly
    assert schema is not None


@pytest.mark.asyncio
async def test_decision_query_exists(mock_context: dict[str, Any]) -> None:
    """Test that decision query field exists."""
    query = """
        query GetDecision($id: UUID!) {
            decision(id: $id) {
                id
                title
                status
            }
        }
    """
    # Execute query with mock context
    result = await schema.execute(query, variable_values={"id": str(uuid.uuid4())}, context_value=mock_context)
    # Should return None (no data) but no errors
    assert result.errors is None or len(result.errors) == 0


@pytest.mark.asyncio
async def test_decisions_query_exists(mock_context: dict[str, Any]) -> None:
    """Test that decisions query field exists."""
    query = """
        query ListDecisions {
            decisions(limit: 10) {
                id
                title
                status
            }
        }
    """
    result = await schema.execute(query, context_value=mock_context)
    assert result.errors is None or len(result.errors) == 0
    assert result.data is not None
    assert "decisions" in result.data
    assert isinstance(result.data["decisions"], list)


@pytest.mark.asyncio
async def test_dataset_query_exists(mock_context: dict[str, Any]) -> None:
    """Test that dataset query field exists."""
    query = """
        query GetDataset($id: UUID!) {
            dataset(id: $id) {
                id
                name
                layer
            }
        }
    """
    result = await schema.execute(query, variable_values={"id": str(uuid.uuid4())}, context_value=mock_context)
    assert result.errors is None or len(result.errors) == 0


@pytest.mark.asyncio
async def test_datasets_query_exists(mock_context: dict[str, Any]) -> None:
    """Test that datasets query field exists."""
    query = """
        query ListDatasets {
            datasets(limit: 10) {
                id
                name
                layer
            }
        }
    """
    result = await schema.execute(query, context_value=mock_context)
    assert result.errors is None or len(result.errors) == 0
    assert result.data is not None
    assert "datasets" in result.data


@pytest.mark.asyncio
async def test_lineage_query_exists(mock_context: dict[str, Any]) -> None:
    """Test that lineage query field exists."""
    query = """
        query GetLineage($datasetId: UUID!) {
            lineage(datasetId: $datasetId, depth: 3) {
                nodes {
                    id
                    name
                }
                edges {
                    fromDataset
                    toDataset
                }
            }
        }
    """
    result = await schema.execute(query, variable_values={"datasetId": str(uuid.uuid4())}, context_value=mock_context)
    assert result.errors is None or len(result.errors) == 0


@pytest.mark.asyncio
async def test_quality_report_query_exists(mock_context: dict[str, Any]) -> None:
    """Test that qualityReport query field exists."""
    query = """
        query GetQualityReport($datasetId: String!) {
            qualityReport(datasetId: $datasetId) {
                id
                datasetId
                overallScore
                passed
            }
        }
    """
    result = await schema.execute(query, variable_values={"datasetId": "test-dataset"}, context_value=mock_context)
    assert result.errors is None or len(result.errors) == 0
