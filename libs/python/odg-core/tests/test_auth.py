"""Tests for auth module: models, keycloak, opa, middleware, dependencies."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from odg_core.auth.dependencies import get_current_user, require_role
from odg_core.auth.keycloak import KeycloakVerifier
from odg_core.auth.middleware import get_anonymous_user, get_keycloak, get_opa
from odg_core.auth.models import TokenPayload, UserContext
from odg_core.auth.opa import OPAClient
from odg_core.enums import RACIRole
from odg_core.settings import KeycloakSettings, OPASettings


# ---------------------------------------------------------------------------
# TokenPayload
# ---------------------------------------------------------------------------
class TestTokenPayload:
    def test_minimal_payload(self) -> None:
        payload = TokenPayload(sub="user-123")
        assert payload.sub == "user-123"
        assert payload.email == ""
        assert payload.preferred_username == ""
        assert payload.realm_access == {}
        assert payload.resource_access == {}
        assert payload.roles == []

    def test_roles_extracted_from_realm_access(self) -> None:
        payload = TokenPayload(
            sub="u1",
            realm_access={"roles": ["admin", "viewer"]},
        )
        assert payload.roles == ["admin", "viewer"]

    def test_roles_empty_when_no_roles_key(self) -> None:
        payload = TokenPayload(sub="u1", realm_access={"other": ["x"]})
        assert payload.roles == []

    def test_full_payload(self) -> None:
        payload = TokenPayload(
            sub="user-abc",
            email="a@b.com",
            preferred_username="alice",
            realm_access={"roles": ["accountable"]},
            resource_access={"client": {"roles": ["editor"]}},
        )
        assert payload.email == "a@b.com"
        assert payload.preferred_username == "alice"
        assert payload.roles == ["accountable"]
        assert payload.resource_access["client"]["roles"] == ["editor"]

    def test_sub_must_be_non_empty(self) -> None:
        with pytest.raises(ValidationError):
            TokenPayload(sub="")


# ---------------------------------------------------------------------------
# UserContext
# ---------------------------------------------------------------------------
class TestUserContext:
    def test_defaults(self) -> None:
        ctx = UserContext(user_id="u1")
        assert ctx.user_id == "u1"
        assert ctx.username == ""
        assert ctx.email == ""
        assert ctx.roles == []
        assert ctx.is_authenticated is True

    def test_full_context(self) -> None:
        ctx = UserContext(
            user_id="u2",
            username="bob",
            email="bob@x.com",
            roles=["admin"],
            is_authenticated=False,
        )
        assert ctx.username == "bob"
        assert ctx.email == "bob@x.com"
        assert ctx.roles == ["admin"]
        assert ctx.is_authenticated is False


# ---------------------------------------------------------------------------
# KeycloakVerifier
# ---------------------------------------------------------------------------
class TestKeycloakVerifier:
    def test_defaults_disabled(self) -> None:
        verifier = KeycloakVerifier()
        assert verifier.enabled is False
        assert verifier.is_configured is False

    def test_enabled_via_settings(self) -> None:
        settings = KeycloakSettings(enabled=True)
        verifier = KeycloakVerifier(settings=settings)
        assert verifier.enabled is True
        assert verifier.is_configured is True

    def test_verify_token_disabled_returns_none(self) -> None:
        verifier = KeycloakVerifier()
        result = verifier.verify_token("some-token")
        assert result is None

    def test_verify_token_enabled_returns_none_placeholder(self) -> None:
        """Current implementation is a placeholder that logs and returns None."""
        settings = KeycloakSettings(enabled=True)
        verifier = KeycloakVerifier(settings=settings)
        result = verifier.verify_token("jwt.token.here")
        assert result is None

    def test_verify_token_exception_returns_none(self) -> None:
        """If an exception occurs inside verify_token, it returns None."""
        settings = KeycloakSettings(enabled=True)
        verifier = KeycloakVerifier(settings=settings)
        # Patch logger.debug to raise so we enter the except branch
        with patch("odg_core.auth.keycloak.logger") as mock_logger:
            mock_logger.debug.side_effect = RuntimeError("boom")
            result = verifier.verify_token("bad")
        assert result is None
        mock_logger.warning.assert_called_once()

    def test_custom_settings_preserved(self) -> None:
        settings = KeycloakSettings(
            server_url="http://kc:8080",
            realm="test",
            client_id="my-app",
            enabled=True,
        )
        verifier = KeycloakVerifier(settings=settings)
        assert verifier._settings.server_url == "http://kc:8080"
        assert verifier._settings.realm == "test"
        assert verifier._settings.client_id == "my-app"


# ---------------------------------------------------------------------------
# OPAClient
# ---------------------------------------------------------------------------
class TestOPAClient:
    def test_defaults_disabled(self) -> None:
        client = OPAClient()
        assert client.enabled is False
        assert client.is_configured is False

    def test_enabled_via_settings(self) -> None:
        settings = OPASettings(enabled=True)
        client = OPAClient(settings=settings)
        assert client.enabled is True
        assert client.is_configured is True

    @pytest.mark.asyncio
    async def test_check_access_disabled_allows_all(self) -> None:
        client = OPAClient()
        result = await client.check_access(
            user_id="u1",
            roles=["admin"],
            resource="/data",
            action="read",
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_check_permission_delegates_to_check_access(self) -> None:
        client = OPAClient()
        result = await client.check_permission(
            user_id="u1",
            roles=["viewer"],
            action="write",
            resource="/stuff",
        )
        assert result is True  # disabled -> allow all

    @pytest.mark.asyncio
    async def test_check_access_enabled_allowed(self) -> None:
        settings = OPASettings(enabled=True, url="http://opa:8181")
        client = OPAClient(settings=settings)

        mock_response = MagicMock()
        mock_response.json.return_value = {"result": True}
        mock_response.raise_for_status = MagicMock()

        mock_http_client = AsyncMock()
        mock_http_client.post = AsyncMock(return_value=mock_response)
        mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_http_client.__aexit__ = AsyncMock(return_value=False)

        with patch("odg_core.auth.opa.httpx.AsyncClient", return_value=mock_http_client):
            result = await client.check_access(
                user_id="u1",
                roles=["admin"],
                resource="/data",
                action="read",
            )

        assert result is True
        mock_http_client.post.assert_awaited_once()
        call_args = mock_http_client.post.call_args
        assert call_args[0][0] == "http://opa:8181/v1/data/authz/allow"
        posted_json = call_args[1]["json"]
        assert posted_json["input"]["user"] == "u1"
        assert posted_json["input"]["roles"] == ["admin"]
        assert posted_json["input"]["resource"] == "/data"
        assert posted_json["input"]["action"] == "read"

    @pytest.mark.asyncio
    async def test_check_access_enabled_denied(self) -> None:
        settings = OPASettings(enabled=True)
        client = OPAClient(settings=settings)

        mock_response = MagicMock()
        mock_response.json.return_value = {"result": False}
        mock_response.raise_for_status = MagicMock()

        mock_http_client = AsyncMock()
        mock_http_client.post = AsyncMock(return_value=mock_response)
        mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_http_client.__aexit__ = AsyncMock(return_value=False)

        with patch("odg_core.auth.opa.httpx.AsyncClient", return_value=mock_http_client):
            result = await client.check_access(
                user_id="u1",
                roles=[],
                resource="/admin",
                action="delete",
            )

        assert result is False

    @pytest.mark.asyncio
    async def test_check_access_enabled_no_result_key(self) -> None:
        """When OPA response lacks 'result', default to False."""
        settings = OPASettings(enabled=True)
        client = OPAClient(settings=settings)

        mock_response = MagicMock()
        mock_response.json.return_value = {}
        mock_response.raise_for_status = MagicMock()

        mock_http_client = AsyncMock()
        mock_http_client.post = AsyncMock(return_value=mock_response)
        mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_http_client.__aexit__ = AsyncMock(return_value=False)

        with patch("odg_core.auth.opa.httpx.AsyncClient", return_value=mock_http_client):
            result = await client.check_access(
                user_id="u1",
                roles=[],
                resource="/x",
                action="y",
            )

        assert result is False

    @pytest.mark.asyncio
    async def test_check_access_http_error_defaults_deny(self) -> None:
        settings = OPASettings(enabled=True)
        client = OPAClient(settings=settings)

        mock_http_client = AsyncMock()
        mock_http_client.post = AsyncMock(side_effect=httpx.ConnectError("connection refused"))
        mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_http_client.__aexit__ = AsyncMock(return_value=False)

        with patch("odg_core.auth.opa.httpx.AsyncClient", return_value=mock_http_client):
            result = await client.check_access(
                user_id="u1",
                roles=["admin"],
                resource="/data",
                action="read",
            )

        assert result is False

    @pytest.mark.asyncio
    async def test_check_access_raise_for_status_error(self) -> None:
        """When raise_for_status raises, we default to deny."""
        settings = OPASettings(enabled=True)
        client = OPAClient(settings=settings)

        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500", request=MagicMock(), response=MagicMock()
        )

        mock_http_client = AsyncMock()
        mock_http_client.post = AsyncMock(return_value=mock_response)
        mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_http_client.__aexit__ = AsyncMock(return_value=False)

        with patch("odg_core.auth.opa.httpx.AsyncClient", return_value=mock_http_client):
            result = await client.check_access(
                user_id="u1",
                roles=[],
                resource="/x",
                action="y",
            )

        assert result is False

    @pytest.mark.asyncio
    async def test_check_permission_enabled_delegates(self) -> None:
        """check_permission should delegate to check_access with same args."""
        settings = OPASettings(enabled=True)
        client = OPAClient(settings=settings)

        with patch.object(client, "check_access", new_callable=AsyncMock, return_value=True) as mock_check:
            result = await client.check_permission(
                user_id="u1",
                roles=["viewer"],
                action="read",
                resource="/path",
            )

        assert result is True
        mock_check.assert_awaited_once_with(
            user_id="u1",
            roles=["viewer"],
            resource="/path",
            action="read",
        )


# ---------------------------------------------------------------------------
# Middleware singletons
# ---------------------------------------------------------------------------
class TestMiddleware:
    def setup_method(self) -> None:
        """Reset module-level singletons before each test."""
        import odg_core.auth.middleware as mw

        mw._keycloak = None
        mw._opa = None

    def test_get_keycloak_returns_singleton(self) -> None:
        kc1 = get_keycloak()
        kc2 = get_keycloak()
        assert kc1 is kc2
        assert isinstance(kc1, KeycloakVerifier)

    def test_get_opa_returns_singleton(self) -> None:
        opa1 = get_opa()
        opa2 = get_opa()
        assert opa1 is opa2
        assert isinstance(opa1, OPAClient)

    def test_get_anonymous_user(self) -> None:
        user = get_anonymous_user()
        assert user.user_id == "anonymous"
        assert user.username == "anonymous"
        assert user.is_authenticated is False
        assert user.email == ""
        assert user.roles == []

    def test_get_anonymous_user_returns_new_instances(self) -> None:
        user1 = get_anonymous_user()
        user2 = get_anonymous_user()
        assert user1 == user2  # equal values
        assert user1 is not user2  # different objects

    def test_get_keycloak_creates_new_after_reset(self) -> None:
        import odg_core.auth.middleware as mw

        kc1 = get_keycloak()
        mw._keycloak = None
        kc2 = get_keycloak()
        assert kc1 is not kc2

    def test_get_opa_creates_new_after_reset(self) -> None:
        import odg_core.auth.middleware as mw

        opa1 = get_opa()
        mw._opa = None
        opa2 = get_opa()
        assert opa1 is not opa2


# ---------------------------------------------------------------------------
# Dependencies: get_current_user
# ---------------------------------------------------------------------------
class TestGetCurrentUser:
    def setup_method(self) -> None:
        import odg_core.auth.middleware as mw

        mw._keycloak = None
        mw._opa = None

    def test_returns_anonymous_when_keycloak_not_configured(self) -> None:
        """When Keycloak is disabled, return anonymous user regardless of headers."""
        request = MagicMock()
        request.headers = {"Authorization": "Bearer some.jwt.token"}

        user = get_current_user(request)
        assert user.user_id == "anonymous"
        assert user.is_authenticated is False

    def test_returns_anonymous_when_no_bearer_header(self) -> None:
        """Even if Keycloak is configured, missing Bearer header -> anonymous."""
        import odg_core.auth.middleware as mw

        mock_kc = MagicMock(spec=KeycloakVerifier)
        mock_kc.is_configured = True
        mw._keycloak = mock_kc

        request = MagicMock()
        request.headers = {}  # no Authorization header

        with patch("odg_core.auth.dependencies.get_keycloak", return_value=mock_kc):
            user = get_current_user(request)

        assert user.user_id == "anonymous"
        assert user.is_authenticated is False

    def test_returns_anonymous_when_header_not_bearer(self) -> None:
        import odg_core.auth.middleware as mw

        mock_kc = MagicMock(spec=KeycloakVerifier)
        mock_kc.is_configured = True
        mw._keycloak = mock_kc

        request = MagicMock()
        request.headers = {"Authorization": "Basic dXNlcjpwYXNz"}

        with patch("odg_core.auth.dependencies.get_keycloak", return_value=mock_kc):
            user = get_current_user(request)

        assert user.user_id == "anonymous"

    def test_raises_401_when_token_invalid(self) -> None:
        mock_kc = MagicMock(spec=KeycloakVerifier)
        mock_kc.is_configured = True
        mock_kc.verify_token = MagicMock(return_value=None)

        request = MagicMock()
        request.headers = {"Authorization": "Bearer invalid.token"}

        with (
            pytest.raises(HTTPException) as exc_info,
            patch("odg_core.auth.dependencies.get_keycloak", return_value=mock_kc),
        ):
            get_current_user(request)

        assert exc_info.value.status_code == 401
        assert "Invalid or expired token" in str(exc_info.value.detail)

    def test_returns_user_context_on_valid_token(self) -> None:
        payload = TokenPayload(
            sub="user-42",
            preferred_username="alice",
            email="alice@example.com",
            realm_access={"roles": ["admin", "viewer"]},
        )

        mock_kc = MagicMock(spec=KeycloakVerifier)
        mock_kc.is_configured = True
        mock_kc.verify_token = MagicMock(return_value=payload)

        request = MagicMock()
        request.headers = {"Authorization": "Bearer valid.jwt.token"}

        with patch("odg_core.auth.dependencies.get_keycloak", return_value=mock_kc):
            user = get_current_user(request)

        assert user.user_id == "user-42"
        assert user.username == "alice"
        assert user.email == "alice@example.com"
        assert user.roles == ["admin", "viewer"]
        assert user.is_authenticated is True
        mock_kc.verify_token.assert_called_once_with("valid.jwt.token")

    def test_bearer_prefix_stripped(self) -> None:
        """Ensure only the 'Bearer ' prefix is removed from the token."""
        payload = TokenPayload(sub="u1")

        mock_kc = MagicMock(spec=KeycloakVerifier)
        mock_kc.is_configured = True
        mock_kc.verify_token = MagicMock(return_value=payload)

        request = MagicMock()
        request.headers = {"Authorization": "Bearer abc.def.ghi"}

        with patch("odg_core.auth.dependencies.get_keycloak", return_value=mock_kc):
            get_current_user(request)

        mock_kc.verify_token.assert_called_once_with("abc.def.ghi")


# ---------------------------------------------------------------------------
# Dependencies: require_role
# ---------------------------------------------------------------------------
class TestRequireRole:
    def setup_method(self) -> None:
        import odg_core.auth.middleware as mw

        mw._keycloak = None
        mw._opa = None

    @pytest.mark.asyncio
    async def test_raises_401_for_unauthenticated_user(self) -> None:
        dep = require_role(RACIRole.ACCOUNTABLE)
        anon_user = UserContext(user_id="anonymous", is_authenticated=False)

        request = MagicMock()
        request.url = MagicMock()
        request.url.path = "/admin"

        with (
            patch("odg_core.auth.dependencies.get_current_user", new_callable=MagicMock, return_value=anon_user),
            pytest.raises(HTTPException) as exc_info,
        ):
            await dep(request=request, user=anon_user)

        assert exc_info.value.status_code == 401
        assert "Authentication required" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_opa_configured_and_allowed(self) -> None:
        dep = require_role(RACIRole.RESPONSIBLE)
        user = UserContext(
            user_id="u1",
            username="bob",
            roles=["responsible"],
            is_authenticated=True,
        )

        mock_opa = AsyncMock(spec=OPAClient)
        mock_opa.is_configured = True
        mock_opa.check_permission = AsyncMock(return_value=True)

        request = MagicMock()
        request.url = MagicMock()
        request.url.path = "/data/promote"

        with patch("odg_core.auth.dependencies.get_opa", return_value=mock_opa):
            result = await dep(request=request, user=user)

        assert result is user
        mock_opa.check_permission.assert_awaited_once_with(
            user_id="u1",
            roles=["responsible"],
            action="responsible",
            resource="/data/promote",
        )

    @pytest.mark.asyncio
    async def test_opa_configured_and_denied(self) -> None:
        dep = require_role(RACIRole.ACCOUNTABLE)
        user = UserContext(
            user_id="u1",
            roles=["viewer"],
            is_authenticated=True,
        )

        mock_opa = AsyncMock(spec=OPAClient)
        mock_opa.is_configured = True
        mock_opa.check_permission = AsyncMock(return_value=False)

        request = MagicMock()
        request.url = MagicMock()
        request.url.path = "/admin"

        with (
            patch("odg_core.auth.dependencies.get_opa", return_value=mock_opa),
            pytest.raises(HTTPException) as exc_info,
        ):
            await dep(request=request, user=user)

        assert exc_info.value.status_code == 403
        assert "accountable" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_opa_not_configured_role_present(self) -> None:
        """Without OPA, fall back to simple role-in-list check."""
        dep = require_role(RACIRole.RESPONSIBLE)
        user = UserContext(
            user_id="u1",
            roles=["responsible", "consulted"],
            is_authenticated=True,
        )

        mock_opa = MagicMock(spec=OPAClient)
        mock_opa.is_configured = False

        request = MagicMock()
        request.url = MagicMock()
        request.url.path = "/tasks"

        with patch("odg_core.auth.dependencies.get_opa", return_value=mock_opa):
            result = await dep(request=request, user=user)

        assert result is user

    @pytest.mark.asyncio
    async def test_opa_not_configured_role_missing(self) -> None:
        dep = require_role(RACIRole.ACCOUNTABLE)
        user = UserContext(
            user_id="u1",
            roles=["consulted"],
            is_authenticated=True,
        )

        mock_opa = MagicMock(spec=OPAClient)
        mock_opa.is_configured = False

        request = MagicMock()
        request.url = MagicMock()
        request.url.path = "/admin"

        with (
            patch("odg_core.auth.dependencies.get_opa", return_value=mock_opa),
            pytest.raises(HTTPException) as exc_info,
        ):
            await dep(request=request, user=user)

        assert exc_info.value.status_code == 403
        assert "accountable" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_require_role_returns_callable(self) -> None:
        dep = require_role(RACIRole.INFORMED)
        assert callable(dep)

    @pytest.mark.asyncio
    async def test_opa_not_configured_empty_roles(self) -> None:
        """User with empty roles list should be denied."""
        dep = require_role(RACIRole.RESPONSIBLE)
        user = UserContext(
            user_id="u1",
            roles=[],
            is_authenticated=True,
        )

        mock_opa = MagicMock(spec=OPAClient)
        mock_opa.is_configured = False

        request = MagicMock()
        request.url = MagicMock()
        request.url.path = "/resource"

        with (
            patch("odg_core.auth.dependencies.get_opa", return_value=mock_opa),
            pytest.raises(HTTPException) as exc_info,
        ):
            await dep(request=request, user=user)

        assert exc_info.value.status_code == 403


# ---------------------------------------------------------------------------
# Settings defaults (KeycloakSettings / OPASettings)
# ---------------------------------------------------------------------------
class TestAuthSettings:
    def test_keycloak_defaults(self) -> None:
        settings = KeycloakSettings()
        assert settings.server_url == "http://localhost:8180"
        assert settings.realm == "opendatagov"
        assert settings.client_id == "odg-api"
        assert settings.enabled is False

    def test_opa_defaults(self) -> None:
        settings = OPASettings()
        assert settings.url == "http://localhost:8181"
        assert settings.enabled is False


# ---------------------------------------------------------------------------
# Integration-style: end-to-end dependency chain
# ---------------------------------------------------------------------------
class TestAuthEndToEnd:
    def setup_method(self) -> None:
        import odg_core.auth.middleware as mw

        mw._keycloak = None
        mw._opa = None

    @pytest.mark.asyncio
    async def test_full_flow_valid_user_with_opa(self) -> None:
        """Simulate: valid token -> Keycloak verifies -> OPA allows."""
        payload = TokenPayload(
            sub="user-99",
            preferred_username="charlie",
            email="charlie@org.com",
            realm_access={"roles": ["accountable"]},
        )

        mock_kc = MagicMock(spec=KeycloakVerifier)
        mock_kc.is_configured = True
        mock_kc.verify_token = MagicMock(return_value=payload)

        mock_opa = AsyncMock(spec=OPAClient)
        mock_opa.is_configured = True
        mock_opa.check_permission = AsyncMock(return_value=True)

        request = MagicMock()
        request.headers = {"Authorization": "Bearer real.jwt.token"}
        request.url = MagicMock()
        request.url.path = "/governance/approve"

        with (
            patch("odg_core.auth.dependencies.get_keycloak", return_value=mock_kc),
            patch("odg_core.auth.dependencies.get_opa", return_value=mock_opa),
        ):
            user = get_current_user(request)
            dep = require_role(RACIRole.ACCOUNTABLE)
            result = await dep(request=request, user=user)

        assert result.user_id == "user-99"
        assert result.is_authenticated is True

    @pytest.mark.asyncio
    async def test_full_flow_valid_user_opa_denies(self) -> None:
        """Simulate: valid token -> Keycloak verifies -> OPA denies."""
        payload = TokenPayload(
            sub="user-100",
            preferred_username="dave",
            realm_access={"roles": ["consulted"]},
        )

        mock_kc = MagicMock(spec=KeycloakVerifier)
        mock_kc.is_configured = True
        mock_kc.verify_token = MagicMock(return_value=payload)

        mock_opa = AsyncMock(spec=OPAClient)
        mock_opa.is_configured = True
        mock_opa.check_permission = AsyncMock(return_value=False)

        request = MagicMock()
        request.headers = {"Authorization": "Bearer real.jwt.token"}
        request.url = MagicMock()
        request.url.path = "/admin/delete"

        with (
            patch("odg_core.auth.dependencies.get_keycloak", return_value=mock_kc),
            patch("odg_core.auth.dependencies.get_opa", return_value=mock_opa),
        ):
            user = get_current_user(request)
            dep = require_role(RACIRole.ACCOUNTABLE)
            with pytest.raises(HTTPException) as exc_info:
                await dep(request=request, user=user)

        assert exc_info.value.status_code == 403

    def test_dev_mode_no_auth_configured(self) -> None:
        """When nothing is configured, everything is anonymous but allowed."""
        request = MagicMock()
        request.headers = {}

        user = get_current_user(request)
        assert user.user_id == "anonymous"
        assert user.is_authenticated is False
