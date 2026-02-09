"""Audit event encryption using Vault Transit engine (ADR-073, Phase 5).

Provides tamper-proof audit logging with:
- Encryption at rest using Vault Transit
- Hash chain linking for integrity verification
- Immutable append-only log structure
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
from typing import Any

from odg_core.vault.client import VaultClient

logger = logging.getLogger(__name__)


class AuditEncryption:
    """Encrypts audit events with Vault Transit and creates hash chain."""

    def __init__(self, vault_client: VaultClient | None = None, key_name: str = "odg-encryption") -> None:
        """Initialize audit encryption.

        Args:
            vault_client: Vault client instance (creates new if None)
            key_name: Vault Transit key name (default: "odg-encryption")
        """
        self._vault = vault_client or VaultClient()
        self._key_name = key_name
        self._enabled = self._vault.is_configured

        if not self._enabled:
            logger.warning("Vault not configured, audit events will NOT be encrypted")

    @property
    def enabled(self) -> bool:
        """Check if encryption is enabled."""
        return self._enabled

    def encrypt_event(self, event: dict[str, Any], previous_hash: str | None = None) -> dict[str, Any]:
        """Encrypt audit event with Vault Transit and create hash chain.

        Args:
            event: Audit event dictionary to encrypt
            previous_hash: SHA-256 hash of previous event (for chain linking)

        Returns:
            Dict with:
                - encrypted_event: Base64-encoded ciphertext
                - event_hash: SHA-256 hash of plaintext event
                - previous_hash: Hash of previous event (chain link)
        """
        # Serialize event to JSON
        plaintext = json.dumps(event, sort_keys=True).encode("utf-8")

        # Compute hash of plaintext event
        event_hash = self._compute_hash(plaintext)

        # Encrypt if Vault is configured
        if self._enabled:
            try:
                plaintext_b64 = base64.b64encode(plaintext).decode("utf-8")
                ciphertext = self._vault.transit_encrypt(self._key_name, plaintext_b64)
                encrypted_event = ciphertext
            except Exception as e:
                logger.error("Encryption failed, storing plaintext: %s", e)
                encrypted_event = base64.b64encode(plaintext).decode("utf-8")
        else:
            # Store as base64 if encryption disabled
            encrypted_event = base64.b64encode(plaintext).decode("utf-8")

        return {
            "encrypted_event": encrypted_event.encode("utf-8") if isinstance(encrypted_event, str) else encrypted_event,
            "event_hash": event_hash,
            "previous_hash": previous_hash,
        }

    def decrypt_event(self, encrypted_event: bytes, is_vault_encrypted: bool = True) -> dict[str, Any]:
        """Decrypt audit event.

        Args:
            encrypted_event: Encrypted event bytes
            is_vault_encrypted: Whether event is Vault-encrypted or just base64

        Returns:
            Decrypted event dictionary

        Raises:
            Exception: If decryption fails
        """
        if self._enabled and is_vault_encrypted:
            try:
                ciphertext = encrypted_event.decode("utf-8")
                plaintext_b64 = self._vault.transit_decrypt(self._key_name, ciphertext)
                plaintext = base64.b64decode(plaintext_b64)
            except Exception as e:
                logger.error("Vault decryption failed: %s", e)
                raise
        else:
            # Decrypt base64-only
            plaintext = base64.b64decode(encrypted_event)

        result: dict[str, Any] = json.loads(plaintext.decode("utf-8"))
        return result

    def verify_hash(self, event: dict[str, Any], stored_hash: str) -> bool:
        """Verify event hash matches stored hash.

        Args:
            event: Decrypted event dictionary
            stored_hash: SHA-256 hash stored in database

        Returns:
            True if hashes match, False otherwise
        """
        plaintext = json.dumps(event, sort_keys=True).encode("utf-8")
        computed_hash = self._compute_hash(plaintext)
        return computed_hash == stored_hash

    @staticmethod
    def _compute_hash(data: bytes) -> str:
        """Compute SHA-256 hash of data.

        Args:
            data: Bytes to hash

        Returns:
            Hex-encoded SHA-256 hash (64 characters)
        """
        return hashlib.sha256(data).hexdigest()

    def verify_chain_integrity(self, events: list[dict[str, Any]]) -> tuple[bool, int | None]:
        """Verify audit chain integrity.

        Args:
            events: List of events with 'event_hash' and 'previous_hash' fields

        Returns:
            Tuple of (is_valid, broken_at_index)
            - is_valid: True if chain is valid, False if broken
            - broken_at_index: Index where chain breaks (None if valid)
        """
        if not events:
            return True, None

        # First event should have no previous hash
        if events[0].get("previous_hash") is not None:
            return False, 0

        # Verify each link in the chain
        for i in range(1, len(events)):
            current = events[i]
            previous = events[i - 1]

            expected_previous_hash = previous.get("event_hash")
            actual_previous_hash = current.get("previous_hash")

            if actual_previous_hash != expected_previous_hash:
                return False, i

        return True, None
