"""Tests for HashiCorp Vault client and MinIO SSE integration."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from odg_core.settings import VaultSettings
from odg_core.vault.client import VaultClient
from odg_core.vault.minio_sse import (
    DEFAULT_TRANSIT_KEY,
    ensure_transit_key,
    get_sse_headers,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _configured_settings() -> VaultSettings:
    """Return a VaultSettings instance that is enabled with a token."""
    return VaultSettings(enabled=True, token="s.test-token", addr="http://vault:8200")


def _disabled_settings() -> VaultSettings:
    """Return a VaultSettings instance that is disabled."""
    return VaultSettings(enabled=False, token="", addr="http://vault:8200")


def _enabled_no_token_settings() -> VaultSettings:
    """Return enabled settings without a token."""
    return VaultSettings(enabled=True, token="", addr="http://vault:8200")


# ---------------------------------------------------------------------------
# VaultClient — property: is_configured
# ---------------------------------------------------------------------------


class TestVaultClientIsConfigured:
    def test_configured_when_enabled_and_token_present(self) -> None:
        client = VaultClient(settings=_configured_settings())
        assert client.is_configured is True

    def test_not_configured_when_disabled(self) -> None:
        client = VaultClient(settings=_disabled_settings())
        assert client.is_configured is False

    def test_not_configured_when_token_empty(self) -> None:
        client = VaultClient(settings=_enabled_no_token_settings())
        assert client.is_configured is False

    def test_default_settings_not_configured(self) -> None:
        """Default VaultSettings has enabled=False and token=''."""
        client = VaultClient()
        assert client.is_configured is False


# ---------------------------------------------------------------------------
# VaultClient — _ensure_client
# ---------------------------------------------------------------------------


class TestVaultClientEnsureClient:
    def test_raises_when_not_configured(self) -> None:
        client = VaultClient(settings=_disabled_settings())
        with pytest.raises(RuntimeError, match="Vault not configured"):
            client._ensure_client()

    def test_raises_when_hvac_not_installed(self) -> None:
        client = VaultClient(settings=_configured_settings())
        with patch.dict("sys.modules", {"hvac": None}), pytest.raises(RuntimeError, match="hvac package not installed"):
            client._ensure_client()

    def test_raises_when_authentication_fails(self) -> None:
        client = VaultClient(settings=_configured_settings())
        mock_hvac = MagicMock()
        mock_hvac_client = MagicMock()
        mock_hvac_client.is_authenticated.return_value = False
        mock_hvac.Client.return_value = mock_hvac_client

        with (
            patch.dict("sys.modules", {"hvac": mock_hvac}),
            pytest.raises(RuntimeError, match="Vault authentication failed"),
        ):
            client._ensure_client()

    def test_successful_client_creation(self) -> None:
        client = VaultClient(settings=_configured_settings())
        mock_hvac = MagicMock()
        mock_hvac_client = MagicMock()
        mock_hvac_client.is_authenticated.return_value = True
        mock_hvac.Client.return_value = mock_hvac_client

        with patch.dict("sys.modules", {"hvac": mock_hvac}):
            result = client._ensure_client()

        assert result is mock_hvac_client
        mock_hvac.Client.assert_called_once_with(
            url="http://vault:8200",
            token="s.test-token",
        )

    def test_returns_cached_client_on_second_call(self) -> None:
        client = VaultClient(settings=_configured_settings())
        mock_hvac = MagicMock()
        mock_hvac_client = MagicMock()
        mock_hvac_client.is_authenticated.return_value = True
        mock_hvac.Client.return_value = mock_hvac_client

        with patch.dict("sys.modules", {"hvac": mock_hvac}):
            first = client._ensure_client()
            second = client._ensure_client()

        assert first is second
        # hvac.Client should only be called once (caching)
        mock_hvac.Client.assert_called_once()


# ---------------------------------------------------------------------------
# VaultClient — read_secret
# ---------------------------------------------------------------------------


class TestVaultClientReadSecret:
    def test_read_secret_default_mount(self) -> None:
        client = VaultClient(settings=_configured_settings())
        mock_inner = MagicMock()
        mock_inner.secrets.kv.v2.read_secret_version.return_value = {
            "data": {"data": {"password": "s3cret", "username": "admin"}},
        }
        client._client = mock_inner

        result = client.read_secret("myapp/creds")

        assert result == {"password": "s3cret", "username": "admin"}
        mock_inner.secrets.kv.v2.read_secret_version.assert_called_once_with(path="myapp/creds", mount_point="secret")

    def test_read_secret_custom_mount(self) -> None:
        client = VaultClient(settings=_configured_settings())
        mock_inner = MagicMock()
        mock_inner.secrets.kv.v2.read_secret_version.return_value = {
            "data": {"data": {"key": "value"}},
        }
        client._client = mock_inner

        result = client.read_secret("path", mount_point="custom")

        assert result == {"key": "value"}
        mock_inner.secrets.kv.v2.read_secret_version.assert_called_once_with(path="path", mount_point="custom")


# ---------------------------------------------------------------------------
# VaultClient — write_secret
# ---------------------------------------------------------------------------


class TestVaultClientWriteSecret:
    def test_write_secret_default_mount(self) -> None:
        client = VaultClient(settings=_configured_settings())
        mock_inner = MagicMock()
        client._client = mock_inner

        client.write_secret("myapp/creds", {"password": "new"})

        mock_inner.secrets.kv.v2.create_or_update_secret.assert_called_once_with(
            path="myapp/creds", secret={"password": "new"}, mount_point="secret"
        )

    def test_write_secret_custom_mount(self) -> None:
        client = VaultClient(settings=_configured_settings())
        mock_inner = MagicMock()
        client._client = mock_inner

        client.write_secret("p", {"k": "v"}, mount_point="custom")

        mock_inner.secrets.kv.v2.create_or_update_secret.assert_called_once_with(
            path="p", secret={"k": "v"}, mount_point="custom"
        )


# ---------------------------------------------------------------------------
# VaultClient — transit_encrypt / transit_decrypt
# ---------------------------------------------------------------------------


class TestVaultClientTransit:
    def test_transit_encrypt(self) -> None:
        client = VaultClient(settings=_configured_settings())
        mock_inner = MagicMock()
        mock_inner.secrets.transit.encrypt_data.return_value = {
            "data": {"ciphertext": "vault:v1:abc123"},
        }
        client._client = mock_inner

        result = client.transit_encrypt("my-key", "cGxhaW50ZXh0")

        assert result == "vault:v1:abc123"
        mock_inner.secrets.transit.encrypt_data.assert_called_once_with(name="my-key", plaintext="cGxhaW50ZXh0")

    def test_transit_decrypt(self) -> None:
        client = VaultClient(settings=_configured_settings())
        mock_inner = MagicMock()
        mock_inner.secrets.transit.decrypt_data.return_value = {
            "data": {"plaintext": "cGxhaW50ZXh0"},
        }
        client._client = mock_inner

        result = client.transit_decrypt("my-key", "vault:v1:abc123")

        assert result == "cGxhaW50ZXh0"
        mock_inner.secrets.transit.decrypt_data.assert_called_once_with(name="my-key", ciphertext="vault:v1:abc123")


# ---------------------------------------------------------------------------
# minio_sse — ensure_transit_key
# ---------------------------------------------------------------------------


class TestEnsureTransitKey:
    def test_key_already_exists(self) -> None:
        vault = VaultClient(settings=_configured_settings())
        mock_inner = MagicMock()
        # read_key succeeds -> key exists
        mock_inner.secrets.transit.read_key.return_value = {"data": {}}
        vault._client = mock_inner

        result = ensure_transit_key(vault)

        assert result is True
        mock_inner.secrets.transit.read_key.assert_called_once_with(name=DEFAULT_TRANSIT_KEY)
        mock_inner.secrets.transit.create_key.assert_not_called()

    def test_key_created_when_not_exists(self) -> None:
        vault = VaultClient(settings=_configured_settings())
        mock_inner = MagicMock()
        # read_key raises -> key does not exist -> create_key called
        mock_inner.secrets.transit.read_key.side_effect = Exception("not found")
        vault._client = mock_inner

        result = ensure_transit_key(vault)

        assert result is True
        mock_inner.secrets.transit.create_key.assert_called_once_with(name=DEFAULT_TRANSIT_KEY, key_type="aes256-gcm96")

    def test_custom_key_name(self) -> None:
        vault = VaultClient(settings=_configured_settings())
        mock_inner = MagicMock()
        mock_inner.secrets.transit.read_key.return_value = {"data": {}}
        vault._client = mock_inner

        result = ensure_transit_key(vault, key_name="custom-key")

        assert result is True
        mock_inner.secrets.transit.read_key.assert_called_once_with(name="custom-key")

    def test_returns_false_when_vault_not_configured(self) -> None:
        vault = VaultClient(settings=_disabled_settings())

        result = ensure_transit_key(vault)

        assert result is False

    def test_returns_false_when_create_key_fails(self) -> None:
        vault = VaultClient(settings=_configured_settings())
        mock_inner = MagicMock()
        mock_inner.secrets.transit.read_key.side_effect = Exception("not found")
        mock_inner.secrets.transit.create_key.side_effect = Exception("permission denied")
        vault._client = mock_inner

        result = ensure_transit_key(vault)

        assert result is False


# ---------------------------------------------------------------------------
# minio_sse — get_sse_headers
# ---------------------------------------------------------------------------


class TestGetSSEHeaders:
    def test_default_key_name(self) -> None:
        headers = get_sse_headers()

        assert headers == {
            "x-amz-server-side-encryption": "aws:kms",
            "x-amz-server-side-encryption-aws-kms-key-id": DEFAULT_TRANSIT_KEY,
        }

    def test_custom_key_name(self) -> None:
        headers = get_sse_headers(key_name="my-custom-key")

        assert headers == {
            "x-amz-server-side-encryption": "aws:kms",
            "x-amz-server-side-encryption-aws-kms-key-id": "my-custom-key",
        }

    def test_returns_dict_with_two_keys(self) -> None:
        headers = get_sse_headers()
        assert len(headers) == 2
        assert "x-amz-server-side-encryption" in headers
        assert "x-amz-server-side-encryption-aws-kms-key-id" in headers
