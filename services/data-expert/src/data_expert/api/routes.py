"""Expert HTTP endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Request
from odg_core.expert import ExpertRequest

from data_expert.api.schemas import (
    CapabilitiesResponse,
    ProcessRequest,
    ProcessResponse,
)

router = APIRouter(prefix="/api/v1", tags=["expert"])


@router.post("/process")
async def process_request(body: ProcessRequest, request: Request) -> ProcessResponse:
    """Process a query through the data expert."""
    expert = request.app.state.expert

    expert_request = ExpertRequest(
        query=body.query,
        context=body.context,
        parameters={**body.parameters, "capability": body.capability},
    )

    result = await expert.process(expert_request)

    return ProcessResponse(
        recommendation=result.recommendation,
        confidence=result.confidence,
        reasoning=result.reasoning,
        metadata=result.metadata,
        requires_approval=result.requires_approval,
    )


@router.get("/capabilities")
async def list_capabilities(request: Request) -> CapabilitiesResponse:
    """Return the capabilities offered by the data expert."""
    expert = request.app.state.expert
    return CapabilitiesResponse(
        capabilities=expert.get_capabilities(),
        name="MockDataExpert",
        description="Mock AI data expert for OpenDataGov (development/testing).",
    )
