"""HashiCorp Vault client for secrets and transit encryption (ADR-073).

Graceful degradation: when Vault is not configured, operations raise
clear errors. Use ``is_configured`` to check before calling.
"""

from __future__ import annotations

import logging
from typing import Any

from odg_core.settings import VaultSettings

logger = logging.getLogger(__name__)


class VaultClient:
    """Client for HashiCorp Vault secrets and transit engine."""

    def __init__(self, settings: VaultSettings | None = None) -> None:
        self._settings = settings or VaultSettings()
        self._client: Any = None

    @property
    def is_configured(self) -> bool:
        return self._settings.enabled and bool(self._settings.token)

    def _ensure_client(self) -> Any:
        """Lazily initialize hvac client."""
        if self._client is not None:
            return self._client

        if not self.is_configured:
            msg = "Vault not configured (set VAULT_ENABLED=true and VAULT_TOKEN)"
            raise RuntimeError(msg)

        try:
            import hvac
        except ImportError:
            msg = "hvac package not installed (pip install hvac)"
            raise RuntimeError(msg) from None

        self._client = hvac.Client(
            url=self._settings.addr,
            token=self._settings.token,
        )
        if not self._client.is_authenticated():
            msg = "Vault authentication failed"
            raise RuntimeError(msg)
        logger.info("Connected to Vault at %s", self._settings.addr)

        return self._client

    def read_secret(self, path: str, mount_point: str = "secret") -> dict[str, Any]:
        """Read a secret from Vault KV v2."""
        client = self._ensure_client()
        response = client.secrets.kv.v2.read_secret_version(path=path, mount_point=mount_point)
        result: dict[str, Any] = response["data"]["data"]
        return result

    def write_secret(self, path: str, data: dict[str, Any], mount_point: str = "secret") -> None:
        """Write a secret to Vault KV v2."""
        client = self._ensure_client()
        client.secrets.kv.v2.create_or_update_secret(path=path, secret=data, mount_point=mount_point)

    def transit_encrypt(self, key_name: str, plaintext_b64: str) -> str:
        """Encrypt data using Vault Transit engine."""
        client = self._ensure_client()
        result = client.secrets.transit.encrypt_data(name=key_name, plaintext=plaintext_b64)
        ciphertext: str = result["data"]["ciphertext"]
        return ciphertext

    def transit_decrypt(self, key_name: str, ciphertext: str) -> str:
        """Decrypt data using Vault Transit engine."""
        client = self._ensure_client()
        result = client.secrets.transit.decrypt_data(name=key_name, ciphertext=ciphertext)
        plaintext: str = result["data"]["plaintext"]
        return plaintext

    def get_database_credentials(self, role: str = "odg-app") -> dict[str, Any]:
        """Get dynamic database credentials from Vault.

        Returns:
            Dict with keys: username, password, lease_id, lease_duration
        """
        client = self._ensure_client()
        response = client.secrets.database.generate_credentials(name=role)

        return {
            "username": response["data"]["username"],
            "password": response["data"]["password"],
            "lease_id": response["lease_id"],
            "lease_duration": response["lease_duration"],
        }

    def renew_database_lease(self, lease_id: str, increment: int | None = None) -> dict[str, Any]:
        """Renew a database credential lease.

        Args:
            lease_id: The lease ID to renew
            increment: Optional lease increment in seconds (default: use Vault default)

        Returns:
            Dict with renewed lease information
        """
        client = self._ensure_client()
        if increment:
            response = client.sys.renew_lease(lease_id=lease_id, increment=increment)
        else:
            response = client.sys.renew_lease(lease_id=lease_id)

        return {
            "lease_id": response["lease_id"],
            "lease_duration": response["lease_duration"],
            "renewable": response["renewable"],
        }

    def revoke_database_lease(self, lease_id: str) -> None:
        """Revoke a database credential lease.

        Args:
            lease_id: The lease ID to revoke
        """
        client = self._ensure_client()
        client.sys.revoke_lease(lease_id=lease_id)
