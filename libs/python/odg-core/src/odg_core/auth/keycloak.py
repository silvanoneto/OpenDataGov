"""Keycloak OIDC token verification via JWKS (ADR-072).

Validates JWT tokens issued by Keycloak using the JWKS endpoint.
Graceful degradation: if Keycloak is not configured, auth is skipped.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from odg_core.settings import KeycloakSettings

if TYPE_CHECKING:
    from odg_core.auth.models import TokenPayload

logger = logging.getLogger(__name__)


class KeycloakVerifier:
    """Verifies JWT tokens against Keycloak JWKS."""

    def __init__(self, settings: KeycloakSettings | None = None) -> None:
        self._settings = settings or KeycloakSettings()
        self._enabled = self._settings.enabled

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def is_configured(self) -> bool:
        """Alias for enabled, used by auth dependencies."""
        return self._enabled

    def verify_token(self, token: str) -> TokenPayload | None:
        """Verify a JWT token and return the decoded payload.

        Returns None if verification fails or Keycloak is disabled.
        In production, this should use PyJWT with JWKS caching.
        """
        if not self._enabled:
            return None

        try:
            # Placeholder: real implementation uses PyJWT[crypto]
            # with JWKS fetched from {server_url}/realms/{realm}/protocol/openid-connect/certs
            logger.debug("Token verification would happen here (Keycloak at %s)", self._settings.server_url)
            return None
        except Exception:
            logger.warning("Token verification failed", exc_info=True)
            return None
