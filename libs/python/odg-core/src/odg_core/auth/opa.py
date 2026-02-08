"""OPA policy evaluation client (ADR-072)."""

from __future__ import annotations

import logging

import httpx

from odg_core.settings import OPASettings

logger = logging.getLogger(__name__)


class OPAClient:
    """Evaluates authorization policies against OPA."""

    def __init__(self, settings: OPASettings | None = None) -> None:
        self._settings = settings or OPASettings()
        self._enabled = self._settings.enabled

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def is_configured(self) -> bool:
        """Alias for enabled, used by auth dependencies."""
        return self._enabled

    async def check_permission(
        self,
        *,
        user_id: str,
        roles: list[str],
        action: str,
        resource: str,
    ) -> bool:
        """Check permission (alias for check_access)."""
        return await self.check_access(
            user_id=user_id,
            roles=roles,
            resource=resource,
            action=action,
        )

    async def check_access(
        self,
        *,
        user_id: str,
        roles: list[str],
        resource: str,
        action: str,
    ) -> bool:
        """Check if a user is authorized to perform an action on a resource.

        Returns True if authorized, False otherwise.
        When OPA is disabled, all requests are allowed (dev mode).
        """
        if not self._enabled:
            return True

        input_data = {
            "input": {
                "user": user_id,
                "roles": roles,
                "resource": resource,
                "action": action,
            }
        }

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self._settings.url}/v1/data/authz/allow",
                    json=input_data,
                    timeout=5.0,
                )
                resp.raise_for_status()
                result = resp.json()
                return bool(result.get("result", False))
        except Exception:
            logger.warning("OPA check failed, defaulting to deny", exc_info=True)
            return False
