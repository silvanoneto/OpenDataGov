"""RACI role endpoints: /api/v1/roles."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from odg_core.auth.dependencies import get_current_user, require_role
from odg_core.auth.models import UserContext
from odg_core.enums import RACIRole

from governance_engine.api.deps import RoleServiceDep
from governance_engine.api.schemas import AssignRoleRequest, RoleAssignmentResponse

router = APIRouter(prefix="/api/v1/roles", tags=["roles"])


@router.post("", status_code=201, responses={400: {"description": "Invalid role assignment"}})
async def assign_role(
    body: AssignRoleRequest,
    service: RoleServiceDep,
    user: UserContext = Depends(require_role(RACIRole.ACCOUNTABLE)),
) -> RoleAssignmentResponse:
    try:
        assignment = await service.assign_role(
            user_id=body.user_id,
            domain_id=body.domain_id,
            role=body.role,
            assigned_by=body.assigned_by,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return RoleAssignmentResponse.model_validate(assignment, from_attributes=True)


@router.delete("/{assignment_id}", status_code=204, responses={404: {"description": "Assignment not found"}})
async def revoke_role(
    assignment_id: uuid.UUID,
    revoked_by: str,
    service: RoleServiceDep,
    user: UserContext = Depends(require_role(RACIRole.ACCOUNTABLE)),
) -> None:
    try:
        await service.revoke_role(assignment_id, revoked_by)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("/domain/{domain_id}")
async def get_domain_roles(
    domain_id: str,
    service: RoleServiceDep,
    user: UserContext = Depends(get_current_user),
) -> list[RoleAssignmentResponse]:
    assignments = await service.get_assignments_for_domain(domain_id)
    return [RoleAssignmentResponse.model_validate(a, from_attributes=True) for a in assignments]


@router.get("/user/{user_id}")
async def get_user_roles(
    user_id: str,
    service: RoleServiceDep,
    user: UserContext = Depends(get_current_user),
) -> list[RoleAssignmentResponse]:
    assignments = await service.get_assignments_for_user(user_id)
    return [RoleAssignmentResponse.model_validate(a, from_attributes=True) for a in assignments]
