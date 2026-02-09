"""Auth token and user context models (ADR-072)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator


class TokenPayload(BaseModel):
    """Decoded JWT token payload."""

    sub: str = Field(min_length=1)
    email: str = Field(default="")
    preferred_username: str = Field(default="")
    realm_access: dict[str, list[str]] = Field(default_factory=dict)
    resource_access: dict[str, dict[str, list[str]]] = Field(default_factory=dict)
    roles: list[str] = Field(default_factory=list)
    exp: int | None = None
    iat: int | None = None

    @model_validator(mode="before")
    @classmethod
    def _sync_roles(cls, data: Any) -> Any:
        """Sync roles between realm_access and the roles field."""
        if isinstance(data, dict):
            # If roles provided, use them. Otherwise extract from realm_access
            if "roles" not in data or not data["roles"]:
                ra = data.get("realm_access", {})
                if isinstance(ra, dict):
                    data["roles"] = ra.get("roles", [])
            # Also populate realm_access if missing but roles provided (for back-compat)
            if "realm_access" not in data and data.get("roles"):
                data["realm_access"] = {"roles": data["roles"]}
        return data


class UserContext(BaseModel):
    """Authenticated user context for request processing."""

    user_id: str
    username: str = ""
    email: str = ""
    roles: list[str] = Field(default_factory=list)
    is_authenticated: bool = True
