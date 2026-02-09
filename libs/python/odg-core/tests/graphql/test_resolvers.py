"""Integration tests for GraphQL resolvers."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from odg_core.enums import DAMADimension, DecisionStatus, DecisionType
from odg_core.graphql.resolvers import dataset as dataset_resolvers
from odg_core.graphql.resolvers import decision as decision_resolvers
from odg_core.graphql.resolvers import quality as quality_resolvers


@pytest.fixture
def mock_session() -> AsyncMock:
    """Create mock async session."""
    return AsyncMock(spec=AsyncSession)


@pytest.mark.asyncio
async def test_get_decision_returns_decision(mock_session: AsyncMock) -> None:
    """Test get_decision resolver with valid ID."""
    from odg_core.db.tables import GovernanceDecisionRow

    # Create mock decision row
    decision_id = uuid.uuid4()
    mock_row = GovernanceDecisionRow(
        id=decision_id,
        decision_type=DecisionType.DATA_PROMOTION.value,
        title="Test Decision",
        description="Test description",
        status=DecisionStatus.PENDING.value,
        domain_id="finance",
        created_by="user-1",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        source_layer="bronze",
        target_layer="silver",
        metadata_json={},
    )

    # Mock query result
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_row
    mock_session.execute.return_value = mock_result

    # Call resolver
    result = await decision_resolvers.get_decision(mock_session, decision_id)

    # Verify result
    assert result is not None
    assert result.id == decision_id
    assert result.title == "Test Decision"
    assert result.decision_type == DecisionType.DATA_PROMOTION.value
    assert result.status == DecisionStatus.PENDING.value
    assert result.domain_id == "finance"


@pytest.mark.asyncio
async def test_get_decision_returns_none_when_not_found(mock_session: AsyncMock) -> None:
    """Test get_decision resolver returns None for non-existent ID."""
    # Mock empty result
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    # Call resolver
    result = await decision_resolvers.get_decision(mock_session, uuid.uuid4())

    # Verify None returned
    assert result is None


@pytest.mark.asyncio
async def test_list_decisions_returns_all_decisions(mock_session: AsyncMock) -> None:
    """Test list_decisions resolver returns all decisions."""
    from odg_core.db.tables import GovernanceDecisionRow

    # Create mock decision rows
    mock_rows = [
        GovernanceDecisionRow(
            id=uuid.uuid4(),
            decision_type=DecisionType.DATA_PROMOTION.value,
            title=f"Decision {i}",
            description="Test",
            status=DecisionStatus.PENDING.value,
            domain_id="finance",
            created_by="user-1",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            metadata_json={},
        )
        for i in range(3)
    ]

    # Mock query result
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = mock_rows
    mock_session.execute.return_value = mock_result

    # Call resolver
    results = await decision_resolvers.list_decisions(mock_session)

    # Verify results
    assert len(results) == 3
    assert all(r.decision_type == DecisionType.DATA_PROMOTION.value for r in results)


@pytest.mark.asyncio
async def test_list_decisions_filters_by_domain(mock_session: AsyncMock) -> None:
    """Test list_decisions resolver filters by domain."""
    from odg_core.db.tables import GovernanceDecisionRow

    # Create mock decision row for finance domain
    mock_row = GovernanceDecisionRow(
        id=uuid.uuid4(),
        decision_type=DecisionType.DATA_PROMOTION.value,
        title="Finance Decision",
        description="Test",
        status=DecisionStatus.PENDING.value,
        domain_id="finance",
        created_by="user-1",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        metadata_json={},
    )

    # Mock query result
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mock_row]
    mock_session.execute.return_value = mock_result

    # Call resolver with domain filter
    results = await decision_resolvers.list_decisions(mock_session, domain="finance")

    # Verify results
    assert len(results) == 1
    assert results[0].domain_id == "finance"


@pytest.mark.asyncio
async def test_list_decisions_filters_by_status(mock_session: AsyncMock) -> None:
    """Test list_decisions resolver filters by status."""
    from odg_core.db.tables import GovernanceDecisionRow

    # Create mock approved decision
    mock_row = GovernanceDecisionRow(
        id=uuid.uuid4(),
        decision_type=DecisionType.DATA_PROMOTION.value,
        title="Approved Decision",
        description="Test",
        status=DecisionStatus.APPROVED.value,
        domain_id="finance",
        created_by="user-1",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        metadata_json={},
    )

    # Mock query result
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mock_row]
    mock_session.execute.return_value = mock_result

    # Call resolver with status filter
    results = await decision_resolvers.list_decisions(mock_session, status="approved")

    # Verify results
    assert len(results) == 1
    assert results[0].status == DecisionStatus.APPROVED.value


@pytest.mark.asyncio
async def test_get_quality_report_returns_latest_report(mock_session: AsyncMock) -> None:
    """Test get_quality_report resolver returns latest report."""
    from odg_core.db.tables import QualityReportRow

    # Create mock quality report
    report_id = uuid.uuid4()
    dimension_scores = {
        DAMADimension.COMPLETENESS.value: {
            "score": 0.95,
            "passed": True,
            "message": "Completeness check passed",
        },
        DAMADimension.ACCURACY.value: {
            "score": 0.90,
            "passed": True,
            "message": None,
        },
        DAMADimension.VALIDITY.value: {
            "score": 0.88,
            "passed": True,
            "message": None,
        },
        DAMADimension.CONSISTENCY.value: {
            "score": 0.92,
            "passed": True,
            "message": None,
        },
        DAMADimension.TIMELINESS.value: {
            "score": 0.85,
            "passed": True,
            "message": None,
        },
        DAMADimension.UNIQUENESS.value: {
            "score": 1.0,
            "passed": True,
            "message": None,
        },
    }

    mock_row = QualityReportRow(
        id=report_id,
        dataset_id="gold.sales",
        domain_id="finance",
        layer="gold",
        suite_name="test_suite",
        dq_score=0.92,
        dimension_scores=dimension_scores,
        expectations_passed=100,
        expectations_failed=0,
        expectations_total=100,
        created_at=datetime.now(UTC),
    )

    # Mock query result
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_row
    mock_session.execute.return_value = mock_result

    # Call resolver
    result = await quality_resolvers.get_quality_report(mock_session, "gold.sales")

    # Verify result
    assert result is not None
    assert result.id == report_id
    assert result.dataset_id == "gold.sales"
    assert abs(result.overall_score - 0.92) < 0.01
    assert result.passed is True
    assert len(result.dimensions) == 6

    # Verify dimensions
    completeness_dim = next(d for d in result.dimensions if d.dimension == DAMADimension.COMPLETENESS.value)
    assert abs(completeness_dim.score - 0.95) < 0.01
    assert completeness_dim.passed is True


@pytest.mark.asyncio
async def test_get_quality_report_returns_none_when_not_found(mock_session: AsyncMock) -> None:
    """Test get_quality_report resolver returns None when no report exists."""
    # Mock empty result
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    # Call resolver
    result = await quality_resolvers.get_quality_report(mock_session, "nonexistent.dataset")

    # Verify None returned
    assert result is None


@pytest.mark.asyncio
async def test_get_dataset_placeholder(mock_session: AsyncMock) -> None:
    """Test get_dataset resolver (placeholder implementation)."""
    result = await dataset_resolvers.get_dataset(mock_session, uuid.uuid4())
    # Placeholder returns None
    assert result is None


@pytest.mark.asyncio
async def test_list_datasets_placeholder(mock_session: AsyncMock) -> None:
    """Test list_datasets resolver (placeholder implementation)."""
    results = await dataset_resolvers.list_datasets(mock_session)
    # Placeholder returns empty list
    assert results == []


@pytest.mark.asyncio
async def test_get_lineage_graph_placeholder(mock_session: AsyncMock) -> None:
    """Test get_lineage_graph resolver (placeholder implementation)."""
    result = await dataset_resolvers.get_lineage_graph(mock_session, uuid.uuid4())
    # Placeholder returns None
    assert result is None
