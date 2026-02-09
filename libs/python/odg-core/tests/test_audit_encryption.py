"""Tests for audit encryption module."""

from __future__ import annotations

import base64
import json
from typing import Any
from unittest.mock import MagicMock

import pytest

from odg_core.audit.encryption import AuditEncryption


@pytest.fixture
def mock_vault() -> MagicMock:
    vault = MagicMock()
    vault.is_configured = True
    vault.transit_encrypt.return_value = "vault:v1:ciphertext"
    vault.transit_decrypt.return_value = base64.b64encode(
        json.dumps({"event_type": "test"}, sort_keys=True).encode()
    ).decode()
    return vault


@pytest.fixture
def disabled_vault() -> MagicMock:
    vault = MagicMock()
    vault.is_configured = False
    return vault


class TestAuditEncryptionInit:
    def test_enabled_when_vault_configured(self, mock_vault: MagicMock) -> None:
        enc = AuditEncryption(vault_client=mock_vault)
        assert enc.enabled is True

    def test_disabled_when_vault_not_configured(self, disabled_vault: MagicMock) -> None:
        enc = AuditEncryption(vault_client=disabled_vault)
        assert enc.enabled is False


class TestEncryptEvent:
    def test_encrypt_with_vault(self, mock_vault: MagicMock) -> None:
        enc = AuditEncryption(vault_client=mock_vault)
        event = {"event_type": "test", "actor_id": "user1"}
        result = enc.encrypt_event(event)
        assert "encrypted_event" in result
        assert "event_hash" in result
        assert result["previous_hash"] is None
        mock_vault.transit_encrypt.assert_called_once()

    def test_encrypt_with_previous_hash(self, mock_vault: MagicMock) -> None:
        enc = AuditEncryption(vault_client=mock_vault)
        event = {"event_type": "test"}
        result = enc.encrypt_event(event, previous_hash="abc123")
        assert result["previous_hash"] == "abc123"

    def test_encrypt_without_vault_uses_base64(self, disabled_vault: MagicMock) -> None:
        enc = AuditEncryption(vault_client=disabled_vault)
        event = {"event_type": "test"}
        result = enc.encrypt_event(event)
        # Should be base64 encoded
        plaintext = base64.b64decode(result["encrypted_event"])
        decoded = json.loads(plaintext)
        assert decoded["event_type"] == "test"

    def test_encrypt_vault_failure_falls_back(self, mock_vault: MagicMock) -> None:
        mock_vault.transit_encrypt.side_effect = Exception("Vault error")
        enc = AuditEncryption(vault_client=mock_vault)
        event = {"event_type": "test"}
        result = enc.encrypt_event(event)
        # Should fallback to base64
        assert result["event_hash"] is not None

    def test_event_hash_is_deterministic(self, mock_vault: MagicMock) -> None:
        enc = AuditEncryption(vault_client=mock_vault)
        event = {"event_type": "test", "actor": "user1"}
        r1 = enc.encrypt_event(event)
        r2 = enc.encrypt_event(event)
        assert r1["event_hash"] == r2["event_hash"]

    def test_different_events_different_hashes(self, mock_vault: MagicMock) -> None:
        enc = AuditEncryption(vault_client=mock_vault)
        r1 = enc.encrypt_event({"event_type": "a"})
        r2 = enc.encrypt_event({"event_type": "b"})
        assert r1["event_hash"] != r2["event_hash"]


class TestDecryptEvent:
    def test_decrypt_with_vault(self, mock_vault: MagicMock) -> None:
        enc = AuditEncryption(vault_client=mock_vault)
        encrypted_data = b"vault:v1:ciphertext"
        result = enc.decrypt_event(encrypted_data, is_vault_encrypted=True)
        assert result["event_type"] == "test"
        mock_vault.transit_decrypt.assert_called_once()

    def test_decrypt_base64_only(self, disabled_vault: MagicMock) -> None:
        enc = AuditEncryption(vault_client=disabled_vault)
        event = {"event_type": "test"}
        encoded = base64.b64encode(json.dumps(event).encode())
        result = enc.decrypt_event(encoded, is_vault_encrypted=False)
        assert result["event_type"] == "test"

    def test_decrypt_vault_failure_raises(self, mock_vault: MagicMock) -> None:
        mock_vault.transit_decrypt.side_effect = Exception("Decrypt failed")
        enc = AuditEncryption(vault_client=mock_vault)
        with pytest.raises(Exception, match="Decrypt failed"):
            enc.decrypt_event(b"ciphertext", is_vault_encrypted=True)


class TestVerifyHash:
    def test_verify_matching_hash(self, mock_vault: MagicMock) -> None:
        enc = AuditEncryption(vault_client=mock_vault)
        event = {"event_type": "test"}
        result = enc.encrypt_event(event)
        assert enc.verify_hash(event, result["event_hash"]) is True

    def test_verify_mismatched_hash(self, mock_vault: MagicMock) -> None:
        enc = AuditEncryption(vault_client=mock_vault)
        event = {"event_type": "test"}
        assert enc.verify_hash(event, "wrong_hash") is False


class TestVerifyChainIntegrity:
    def test_empty_chain(self, mock_vault: MagicMock) -> None:
        enc = AuditEncryption(vault_client=mock_vault)
        valid, broken_at = enc.verify_chain_integrity([])
        assert valid is True
        assert broken_at is None

    def test_valid_chain(self, mock_vault: MagicMock) -> None:
        enc = AuditEncryption(vault_client=mock_vault)
        events: list[dict[str, Any]] = [
            {"event_hash": "hash1", "previous_hash": None},
            {"event_hash": "hash2", "previous_hash": "hash1"},
            {"event_hash": "hash3", "previous_hash": "hash2"},
        ]
        valid, broken_at = enc.verify_chain_integrity(events)
        assert valid is True
        assert broken_at is None

    def test_broken_chain_at_start(self, mock_vault: MagicMock) -> None:
        enc = AuditEncryption(vault_client=mock_vault)
        events = [
            {"event_hash": "hash1", "previous_hash": "unexpected"},
        ]
        valid, broken_at = enc.verify_chain_integrity(events)
        assert valid is False
        assert broken_at == 0

    def test_broken_chain_in_middle(self, mock_vault: MagicMock) -> None:
        enc = AuditEncryption(vault_client=mock_vault)
        events: list[dict[str, Any]] = [
            {"event_hash": "hash1", "previous_hash": None},
            {"event_hash": "hash2", "previous_hash": "wrong"},
        ]
        valid, broken_at = enc.verify_chain_integrity(events)
        assert valid is False
        assert broken_at == 1
