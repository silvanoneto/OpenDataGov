"""Tests for the base expert abstract class and request/response models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from odg_core.expert import BaseExpert, ExpertRequest, ExpertResponse


class TestExpertRequest:
    def test_valid_request(self) -> None:
        """ExpertRequest should accept valid query, context, and parameters."""
        req = ExpertRequest(
            query="What is the schema for revenue?",
            context={"domain": "finance"},
            parameters={"max_rows": 100},
        )

        assert req.query == "What is the schema for revenue?"
        assert req.context == {"domain": "finance"}
        assert req.parameters == {"max_rows": 100}

    def test_defaults(self) -> None:
        """ExpertRequest should use empty dicts as defaults for context/parameters."""
        req = ExpertRequest(query="test query")

        assert req.context == {}
        assert req.parameters == {}

    def test_empty_query_rejected(self) -> None:
        """ExpertRequest should reject an empty query string."""
        with pytest.raises(ValidationError):
            ExpertRequest(query="")

    def test_query_min_length(self) -> None:
        """ExpertRequest query must have at least 1 character."""
        req = ExpertRequest(query="x")
        assert req.query == "x"


class TestExpertResponse:
    def test_valid_response(self) -> None:
        """ExpertResponse should accept valid fields."""
        resp = ExpertResponse(
            recommendation="Use partitioned table",
            confidence=0.85,
            reasoning="Based on query patterns",
            metadata={"model": "gpt-4"},
            requires_approval=True,
        )

        assert resp.recommendation == "Use partitioned table"
        assert resp.confidence == 0.85
        assert resp.reasoning == "Based on query patterns"
        assert resp.metadata == {"model": "gpt-4"}
        assert resp.requires_approval is True

    def test_defaults(self) -> None:
        """ExpertResponse should use sensible defaults."""
        resp = ExpertResponse(
            recommendation="Do something",
            confidence=0.5,
        )

        assert resp.reasoning == ""
        assert resp.metadata == {}
        assert resp.requires_approval is True

    def test_confidence_lower_bound(self) -> None:
        """Confidence of 0.0 should be accepted."""
        resp = ExpertResponse(recommendation="low confidence", confidence=0.0)
        assert resp.confidence == 0.0

    def test_confidence_upper_bound(self) -> None:
        """Confidence of 1.0 should be accepted."""
        resp = ExpertResponse(recommendation="high confidence", confidence=1.0)
        assert resp.confidence == 1.0

    def test_confidence_below_zero_rejected(self) -> None:
        """Confidence below 0.0 should be rejected."""
        with pytest.raises(ValidationError):
            ExpertResponse(recommendation="bad", confidence=-0.1)

    def test_confidence_above_one_rejected(self) -> None:
        """Confidence above 1.0 should be rejected."""
        with pytest.raises(ValidationError):
            ExpertResponse(recommendation="bad", confidence=1.1)

    def test_requires_approval_false(self) -> None:
        """requires_approval=False should be accepted."""
        resp = ExpertResponse(
            recommendation="safe action",
            confidence=0.99,
            requires_approval=False,
        )
        assert resp.requires_approval is False


class ConcreteExpert(BaseExpert):
    """Concrete implementation of BaseExpert for testing."""

    def __init__(self, healthy: bool = True) -> None:
        self._healthy = healthy
        self.initialized = False
        self.shut_down = False

    async def process(self, request: ExpertRequest) -> ExpertResponse:
        """Return a static recommendation."""
        return ExpertResponse(
            recommendation=f"Processed: {request.query}",
            confidence=0.9,
            reasoning="test reasoning",
        )

    def get_capabilities(self) -> list[str]:
        """Return test capabilities."""
        return ["sql_generation", "data_analysis"]

    async def health_check(self) -> bool:
        """Return configured health status."""
        return self._healthy

    async def initialize(self) -> None:
        """Track initialization."""
        self.initialized = True

    async def shutdown(self) -> None:
        """Track shutdown."""
        self.shut_down = True


class TestBaseExpert:
    @pytest.mark.asyncio
    async def test_process(self) -> None:
        """Concrete expert should process requests correctly."""
        expert = ConcreteExpert()
        req = ExpertRequest(query="test query")
        resp = await expert.process(req)

        assert isinstance(resp, ExpertResponse)
        assert resp.recommendation == "Processed: test query"
        assert resp.confidence == 0.9

    def test_get_capabilities(self) -> None:
        """Concrete expert should return its capabilities."""
        expert = ConcreteExpert()
        caps = expert.get_capabilities()

        assert caps == ["sql_generation", "data_analysis"]

    @pytest.mark.asyncio
    async def test_health_check_healthy(self) -> None:
        """Healthy expert should return True."""
        expert = ConcreteExpert(healthy=True)
        assert await expert.health_check() is True

    @pytest.mark.asyncio
    async def test_health_check_unhealthy(self) -> None:
        """Unhealthy expert should return False."""
        expert = ConcreteExpert(healthy=False)
        assert await expert.health_check() is False

    @pytest.mark.asyncio
    async def test_initialize(self) -> None:
        """initialize() should be callable and run custom logic."""
        expert = ConcreteExpert()
        assert expert.initialized is False

        await expert.initialize()
        assert expert.initialized is True

    @pytest.mark.asyncio
    async def test_shutdown(self) -> None:
        """shutdown() should be callable and run custom logic."""
        expert = ConcreteExpert()
        assert expert.shut_down is False

        await expert.shutdown()
        assert expert.shut_down is True

    @pytest.mark.asyncio
    async def test_default_initialize_is_noop(self) -> None:
        """BaseExpert.initialize default does nothing (no error)."""

        class MinimalExpert(BaseExpert):
            async def process(self, request: ExpertRequest) -> ExpertResponse:
                return ExpertResponse(recommendation="x", confidence=0.5)

            def get_capabilities(self) -> list[str]:
                return []

            async def health_check(self) -> bool:
                return True

        expert = MinimalExpert()
        # Default initialize and shutdown should not raise
        await expert.initialize()
        await expert.shutdown()

    def test_cannot_instantiate_abstract(self) -> None:
        """BaseExpert cannot be instantiated directly."""
        with pytest.raises(TypeError):
            BaseExpert()  # type: ignore[abstract]
