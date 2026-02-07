"""Decision endpoints: /api/v1/decisions."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException
from odg_core.enums import DecisionStatus

from governance_engine.api.deps import ApprovalServiceDep, DecisionServiceDep, VetoServiceDep
from governance_engine.api.schemas import (
    ApprovalResponse,
    CastVoteRequest,
    CreateDecisionRequest,
    DecisionResponse,
    ExerciseVetoRequest,
    OverrideVetoRequest,
    SubmitDecisionRequest,
    VetoResponse,
)

router = APIRouter(prefix="/api/v1/decisions", tags=["decisions"])


@router.post("", status_code=201)
async def create_decision(
    body: CreateDecisionRequest,
    service: DecisionServiceDep,
) -> DecisionResponse:
    decision = await service.create_decision(
        decision_type=body.decision_type,
        title=body.title,
        description=body.description,
        domain_id=body.domain_id,
        created_by=body.created_by,
        promotion=body.promotion,
        metadata=body.metadata,
    )
    return DecisionResponse.model_validate(decision, from_attributes=True)


@router.get("")
async def list_decisions(
    service: DecisionServiceDep,
    domain_id: str | None = None,
    status: DecisionStatus | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[DecisionResponse]:
    decisions = await service.list_decisions(domain_id=domain_id, status=status, limit=limit, offset=offset)
    return [DecisionResponse.model_validate(d, from_attributes=True) for d in decisions]


@router.get("/{decision_id}", responses={404: {"description": "Decision not found"}})
async def get_decision(decision_id: uuid.UUID, service: DecisionServiceDep) -> DecisionResponse:
    decision = await service.get_decision(decision_id)
    if decision is None:
        raise HTTPException(status_code=404, detail="Decision not found")
    return DecisionResponse.model_validate(decision, from_attributes=True)


@router.post("/{decision_id}/submit", responses={400: {"description": "Invalid state transition"}})
async def submit_decision(
    decision_id: uuid.UUID,
    body: SubmitDecisionRequest,
    service: DecisionServiceDep,
) -> DecisionResponse:
    try:
        decision = await service.submit_for_approval(decision_id, body.actor_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return DecisionResponse.model_validate(decision, from_attributes=True)


@router.post("/{decision_id}/approve", status_code=201, responses={400: {"description": "Invalid vote"}})
async def approve_decision(
    decision_id: uuid.UUID,
    body: CastVoteRequest,
    service: ApprovalServiceDep,
) -> ApprovalResponse:
    try:
        record = await service.cast_vote(
            decision_id=decision_id,
            voter_id=body.voter_id,
            vote=body.vote,
            comment=body.comment,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return ApprovalResponse.model_validate(record, from_attributes=True)


@router.get("/{decision_id}/approvals")
async def list_approvals(
    decision_id: uuid.UUID,
    service: ApprovalServiceDep,
) -> list[ApprovalResponse]:
    records = await service.list_votes(decision_id)
    return [ApprovalResponse.model_validate(r, from_attributes=True) for r in records]


@router.post("/{decision_id}/veto", status_code=201, responses={400: {"description": "Invalid veto"}})
async def exercise_veto(
    decision_id: uuid.UUID,
    body: ExerciseVetoRequest,
    service: VetoServiceDep,
) -> VetoResponse:
    try:
        veto = await service.exercise_veto(
            decision_id=decision_id,
            vetoed_by=body.vetoed_by,
            reason=body.reason,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return VetoResponse.model_validate(veto, from_attributes=True)


@router.post("/{decision_id}/vetoes/{veto_id}/override", responses={400: {"description": "Invalid override"}})
async def override_veto(
    decision_id: uuid.UUID,
    veto_id: uuid.UUID,
    body: OverrideVetoRequest,
    service: VetoServiceDep,
) -> VetoResponse:
    try:
        veto = await service.override_veto(
            veto_id=veto_id,
            overridden_by=body.overridden_by,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return VetoResponse.model_validate(veto, from_attributes=True)


@router.get("/{decision_id}/vetoes")
async def list_vetoes(
    decision_id: uuid.UUID,
    service: VetoServiceDep,
) -> list[VetoResponse]:
    vetoes = await service.list_vetoes(decision_id)
    return [VetoResponse.model_validate(v, from_attributes=True) for v in vetoes]
