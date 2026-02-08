"""FastAPI auth middleware: JWT validation + OPA authorization (ADR-072).

Graceful degradation: without Keycloak URL configured, auth is skipped,
preserving simple dev-mode operation.
"""

from __future__ import annotations

import logging

from odg_core.auth.keycloak import KeycloakVerifier
from odg_core.auth.models import UserContext
from odg_core.auth.opa import OPAClient

logger = logging.getLogger(__name__)

# Singleton instances (initialized on first use)
_keycloak: KeycloakVerifier | None = None
_opa: OPAClient | None = None


def get_keycloak() -> KeycloakVerifier:
    """Get or create the Keycloak verifier singleton."""
    global _keycloak
    if _keycloak is None:
        _keycloak = KeycloakVerifier()
    return _keycloak


def get_opa() -> OPAClient:
    """Get or create the OPA client singleton."""
    global _opa
    if _opa is None:
        _opa = OPAClient()
    return _opa


def get_anonymous_user() -> UserContext:
    """Return an anonymous user context for unauthenticated requests."""
    return UserContext(
        user_id="anonymous",
        username="anonymous",
        is_authenticated=False,
    )
