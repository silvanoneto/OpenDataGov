"""Base expert abstract class for AI experts (ADR-034)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field


class ExpertRequest(BaseModel):
    """Request payload for an AI expert."""

    query: str = Field(min_length=1)
    context: dict[str, Any] = Field(default_factory=dict)
    parameters: dict[str, Any] = Field(default_factory=dict)


class ExpertResponse(BaseModel):
    """Response payload from an AI expert.

    Follows "AI recommends, human decides" paradigm (ADR-011).
    """

    recommendation: str
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str = Field(default="")
    metadata: dict[str, Any] = Field(default_factory=dict)
    requires_approval: bool = Field(default=True)


class BaseExpert(ABC):
    """Abstract base class for all AI experts in OpenDataGov.

    Every expert must implement process(), get_capabilities(),
    and health_check(). Lifecycle is managed by initialize()/shutdown().
    """

    @abstractmethod
    async def process(self, request: ExpertRequest) -> ExpertResponse:
        """Process a request and return a recommendation."""
        ...

    @abstractmethod
    def get_capabilities(self) -> list[str]:
        """Return the list of capabilities this expert provides."""
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the expert is healthy and ready to serve requests."""
        ...

    async def initialize(self) -> None:  # noqa: B027
        """Initialize the expert (load models, connect to backends, etc.)."""

    async def shutdown(self) -> None:  # noqa: B027
        """Gracefully shut down the expert."""
