"""Keycloak OIDC token verification via JWKS (ADR-072).

Validates JWT tokens issued by Keycloak using the JWKS endpoint.
Graceful degradation: if Keycloak is not configured, auth is skipped.
"""

from __future__ import annotations

import logging

import jwt
from jwt import PyJWKClient

from odg_core.auth.models import TokenPayload
from odg_core.settings import KeycloakSettings

logger = logging.getLogger(__name__)


class KeycloakVerifier:
    """Verifies JWT tokens against Keycloak JWKS."""

    def __init__(self, settings: KeycloakSettings | None = None) -> None:
        self._settings = settings or KeycloakSettings()
        self._enabled = self._settings.enabled
        self._jwks_client: PyJWKClient | None = None

        if self._enabled:
            jwks_url = f"{self._settings.server_url}/realms/{self._settings.realm}/protocol/openid-connect/certs"
            self._jwks_client = PyJWKClient(jwks_url, cache_keys=True)
            logger.info("Initialized Keycloak verifier with JWKS from %s", jwks_url)

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
        """
        if not self._enabled or self._jwks_client is None:
            return None

        try:
            # Get signing key from JWKS
            signing_key = self._jwks_client.get_signing_key_from_jwt(token)

            # Decode and verify JWT
            decoded = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                audience=self._settings.client_id,
                options={
                    "verify_signature": True,
                    "verify_aud": True,
                    "verify_exp": True,
                },
            )

            # Extract roles from Keycloak token structure
            roles = []
            if "realm_access" in decoded:
                roles.extend(decoded["realm_access"].get("roles", []))
            if "resource_access" in decoded:
                client_roles = decoded["resource_access"].get(self._settings.client_id, {})
                roles.extend(client_roles.get("roles", []))

            return TokenPayload(
                sub=decoded["sub"],
                preferred_username=decoded.get("preferred_username", ""),
                email=decoded.get("email", ""),
                roles=roles,
                exp=decoded["exp"],
                iat=decoded["iat"],
            )

        except jwt.ExpiredSignatureError:
            logger.warning("Token expired")
            return None
        except jwt.InvalidTokenError:
            logger.warning("Invalid token", exc_info=True)
            return None
        except Exception:
            logger.error("Token verification failed", exc_info=True)
            return None
