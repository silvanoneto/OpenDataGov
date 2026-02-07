"""Unit tests for MockDataExpert."""

from __future__ import annotations

import pytest
from data_expert.expert import MockDataExpert
from odg_core.enums import ExpertCapability
from odg_core.expert import ExpertRequest


@pytest.fixture
def expert() -> MockDataExpert:
    return MockDataExpert()


# ------------------------------------------------------------------ #
# process()
# ------------------------------------------------------------------ #


@pytest.mark.asyncio
async def test_process_sql_generation(expert: MockDataExpert) -> None:
    request = ExpertRequest(
        query="show all active users",
        context={"table": "users"},
        parameters={"capability": ExpertCapability.SQL_GENERATION},
    )

    response = await expert.process(request)

    assert "SELECT" in response.recommendation
    assert "users" in response.recommendation
    assert 0.7 <= response.confidence <= 0.95
    assert response.requires_approval is True
    assert response.metadata["capability"] == ExpertCapability.SQL_GENERATION


@pytest.mark.asyncio
async def test_process_data_analysis(expert: MockDataExpert) -> None:
    request = ExpertRequest(
        query="analyse sales dataset",
        context={},
        parameters={"capability": ExpertCapability.DATA_ANALYSIS},
    )

    response = await expert.process(request)

    assert "Analysis summary" in response.recommendation
    assert 0.7 <= response.confidence <= 0.95
    assert response.requires_approval is True
    assert response.metadata["capability"] == ExpertCapability.DATA_ANALYSIS


# ------------------------------------------------------------------ #
# get_capabilities()
# ------------------------------------------------------------------ #


def test_capabilities_returns_four_items(expert: MockDataExpert) -> None:
    capabilities = expert.get_capabilities()

    assert len(capabilities) == 4
    assert ExpertCapability.SQL_GENERATION in capabilities
    assert ExpertCapability.DATA_ANALYSIS in capabilities
    assert ExpertCapability.DATA_PROFILING in capabilities
    assert ExpertCapability.SCHEMA_INFERENCE in capabilities


# ------------------------------------------------------------------ #
# health_check()
# ------------------------------------------------------------------ #


@pytest.mark.asyncio
async def test_health_check_returns_true(expert: MockDataExpert) -> None:
    result = await expert.health_check()

    assert result is True


# ------------------------------------------------------------------ #
# requires_approval
# ------------------------------------------------------------------ #


@pytest.mark.asyncio
async def test_requires_approval_is_always_true(expert: MockDataExpert) -> None:
    """Every capability must set requires_approval=True (ADR-011)."""
    capabilities = [
        ExpertCapability.SQL_GENERATION,
        ExpertCapability.DATA_ANALYSIS,
        ExpertCapability.DATA_PROFILING,
        ExpertCapability.SCHEMA_INFERENCE,
    ]

    for cap in capabilities:
        request = ExpertRequest(
            query="test query",
            context={},
            parameters={"capability": cap},
        )
        response = await expert.process(request)
        assert response.requires_approval is True, f"requires_approval must be True for {cap}"
