"""Auth token and user context models (ADR-072)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TokenPayload(BaseModel):
    """Decoded JWT token payload."""

    sub: str = Field(min_length=1)
    email: str = Field(default="")
    realm_access: dict[str, list[str]] = Field(default_factory=dict)
    resource_access: dict[str, dict[str, list[str]]] = Field(default_factory=dict)
    preferred_username: str = Field(default="")

    @property
    def roles(self) -> list[str]:
        """Extract realm-level roles from the token."""
        return self.realm_access.get("roles", [])


class UserContext(BaseModel):
    """Authenticated user context for request processing."""

    user_id: str
    username: str = ""
    email: str = ""
    roles: list[str] = Field(default_factory=list)
    is_authenticated: bool = True
