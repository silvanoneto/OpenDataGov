"""Audit endpoints: /api/v1/audit."""

from __future__ import annotations

from fastapi import APIRouter
from odg_core.enums import AuditEventType

from governance_engine.api.deps import AuditServiceDep
from governance_engine.api.schemas import AuditEventResponse, AuditVerifyResponse

router = APIRouter(prefix="/api/v1/audit", tags=["audit"])


@router.get("")
async def list_events(
    service: AuditServiceDep,
    event_type: AuditEventType | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[AuditEventResponse]:
    events = await service.get_events(event_type=event_type, limit=limit, offset=offset)
    return [AuditEventResponse.model_validate(e, from_attributes=True) for e in events]


@router.get("/entity/{entity_id}")
async def get_events_for_entity(
    entity_id: str,
    service: AuditServiceDep,
    limit: int = 50,
) -> list[AuditEventResponse]:
    events = await service.get_events_for_entity(entity_id, limit=limit)
    return [AuditEventResponse.model_validate(e, from_attributes=True) for e in events]


@router.get("/verify")
async def verify_audit_integrity(service: AuditServiceDep) -> AuditVerifyResponse:
    is_valid = await service.verify_integrity()
    return AuditVerifyResponse(is_valid=is_valid)
