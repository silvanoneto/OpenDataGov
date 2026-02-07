"""Data promotion endpoints: /api/v1/promote."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from odg_core.enums import MedallionLayer
from pydantic import BaseModel, Field

from lakehouse_agent.promotion import PromotionError, PromotionService

router = APIRouter(prefix="/api/v1", tags=["promotion"])


class PromoteRequest(BaseModel):
    """Request body for data promotion."""

    domain_id: str = Field(min_length=1, max_length=100)
    source_layer: MedallionLayer
    target_layer: MedallionLayer
    dataset_id: str = Field(min_length=1, max_length=500)
    dq_score: float = Field(ge=0.0, le=1.0)


@router.post("/promote", responses={400: {"description": "Invalid promotion request"}})
async def promote_data(
    body: PromoteRequest,
    request: Request,
) -> dict[str, Any]:
    """Promote a dataset from one medallion layer to the next."""
    service: PromotionService = request.app.state.promotion_service

    try:
        result = await service.promote(
            domain_id=body.domain_id,
            source_layer=body.source_layer,
            target_layer=body.target_layer,
            dataset_id=body.dataset_id,
            dq_score=body.dq_score,
        )
    except PromotionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return result
