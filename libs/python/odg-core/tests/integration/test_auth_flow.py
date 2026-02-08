"""Integration test: auth models, Keycloak verifier, and OPA client."""

from __future__ import annotations


class TestAuthModels:
    """Verify auth models and dependencies (works without Keycloak)."""

    def test_user_context_anonymous(self) -> None:
        """Anonymous user context should have correct defaults."""
        from odg_core.auth.models import UserContext

        user = UserContext(
            user_id="anonymous",
            username="anonymous",
            is_authenticated=False,
        )

        assert user.user_id == "anonymous"
        assert user.is_authenticated is False
        assert user.roles == []

    def test_keycloak_verifier_disabled_by_default(self) -> None:
        """KeycloakVerifier should be disabled when no URL is configured."""
        from odg_core.auth.keycloak import KeycloakVerifier

        verifier = KeycloakVerifier()
        assert verifier.is_configured is False

    def test_opa_client_disabled_by_default(self) -> None:
        """OPAClient should be disabled when not configured."""
        from odg_core.auth.opa import OPAClient

        client = OPAClient()
        assert client.is_configured is False

    async def test_opa_allows_all_when_disabled(self) -> None:
        """Disabled OPA should allow all requests (dev mode)."""
        from odg_core.auth.opa import OPAClient

        client = OPAClient()
        result = await client.check_access(
            user_id="test-user",
            roles=["viewer"],
            resource="/api/v1/decisions",
            action="read",
        )
        assert result is True


class TestKeycloakIntegration:
    """Verify Keycloak verifier graceful degradation."""

    def test_verify_token_returns_none_when_disabled(self) -> None:
        """verify_token should return None when Keycloak is not configured."""
        from odg_core.auth.keycloak import KeycloakVerifier

        verifier = KeycloakVerifier()
        result = verifier.verify_token("some-token")
        assert result is None

    def test_verifier_enabled_with_settings(self) -> None:
        """KeycloakVerifier should report is_configured=True when URL is set."""
        from odg_core.auth.keycloak import KeycloakVerifier
        from odg_core.settings import KeycloakSettings

        settings = KeycloakSettings(
            enabled=True,
            server_url="http://localhost:8180",
            realm="opendatagov",
            client_id="odg-api",
        )
        verifier = KeycloakVerifier(settings=settings)
        assert verifier.is_configured is True

    def test_verify_token_placeholder_with_enabled_settings(self) -> None:
        """verify_token with enabled settings returns None (placeholder)."""
        from odg_core.auth.keycloak import KeycloakVerifier
        from odg_core.settings import KeycloakSettings

        settings = KeycloakSettings(
            enabled=True,
            server_url="http://localhost:8180",
            realm="opendatagov",
            client_id="odg-api",
        )
        verifier = KeycloakVerifier(settings=settings)
        # Placeholder implementation returns None without making network calls
        result = verifier.verify_token("dummy-token")
        assert result is None
