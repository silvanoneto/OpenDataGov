"""FastAPI dependency injection helpers for auth (ADR-072).

Usage in route handlers:
    @router.get("/protected")
    async def protected(user: UserContext = Depends(get_current_user)):
        ...

    @router.post("/admin-only")
    async def admin_only(user: UserContext = Depends(require_role(RACIRole.ACCOUNTABLE))):
        ...
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from fastapi import Depends, HTTPException, Request

from odg_core.auth.middleware import get_anonymous_user, get_keycloak, get_opa
from odg_core.auth.models import UserContext

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

    from odg_core.enums import RACIRole

logger = logging.getLogger(__name__)


def get_current_user(request: Request) -> UserContext:
    """Extract and validate the current user from the request.

    Returns anonymous user if auth is not configured (dev mode).
    """
    keycloak = get_keycloak()

    if not keycloak.is_configured:
        return get_anonymous_user()

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return get_anonymous_user()

    token = auth_header.removeprefix("Bearer ")
    payload = keycloak.verify_token(token)

    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return UserContext(
        user_id=payload.sub,
        username=payload.preferred_username,
        email=payload.email,
        roles=payload.roles,
        is_authenticated=True,
    )


def require_role(role: RACIRole) -> Callable[..., Coroutine[Any, Any, UserContext]]:
    """Create a dependency that requires a specific RACI role."""

    async def _check_role(
        request: Request,
        user: UserContext = Depends(get_current_user),  # noqa: B008
    ) -> UserContext:
        if not user.is_authenticated:
            raise HTTPException(status_code=401, detail="Authentication required")

        opa = get_opa()
        if opa.is_configured:
            allowed = await opa.check_permission(
                user_id=user.user_id,
                roles=user.roles,
                action=role.value,
                resource=request.url.path,
            )
            if not allowed:
                raise HTTPException(status_code=403, detail=f"Role {role.value} required")
        elif role.value not in user.roles:
            raise HTTPException(status_code=403, detail=f"Role {role.value} required")

        return user

    return _check_role
