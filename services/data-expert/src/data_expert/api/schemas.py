"""API request/response schemas for the Data Expert service."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ProcessRequest(BaseModel):
    """Incoming request to process a query through the expert."""

    query: str = Field(min_length=1)
    context: dict[str, Any] = Field(default_factory=dict)
    parameters: dict[str, Any] = Field(default_factory=dict)
    capability: str = Field(
        default="",
        description="The expert capability to invoke (e.g. sql_generation).",
    )


class ProcessResponse(BaseModel):
    """Response returned after the expert processes a request."""

    recommendation: str
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str = Field(default="")
    metadata: dict[str, Any] = Field(default_factory=dict)
    requires_approval: bool = Field(default=True)


class CapabilitiesResponse(BaseModel):
    """Lists the capabilities offered by this expert."""

    capabilities: list[str]
    name: str
    description: str
