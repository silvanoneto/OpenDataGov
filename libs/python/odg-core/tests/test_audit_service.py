"""Tests for audit service module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from odg_core.audit.service import AuditService


class TestAuditService:
    @patch("odg_core.audit.encryption.AuditEncryption")
    def test_log_event(self, mock_enc_cls: MagicMock) -> None:
        mock_enc = MagicMock()
        mock_enc.encrypt_event.return_value = {
            "encrypted_event": b"encrypted",
            "event_hash": "hash123",
            "previous_hash": None,
        }
        mock_enc_cls.return_value = mock_enc

        svc = AuditService()
        result = svc.log_event(
            event_type="decision_created",
            entity_id="entity-1",
            actor_id="user-1",
            action="created",
        )

        assert result["event_type"] == "decision_created"
        assert result["entity_id"] == "entity-1"
        assert result["actor_id"] == "user-1"
        assert result["event_hash"] == "hash123"
        mock_enc.encrypt_event.assert_called_once()

    @patch("odg_core.audit.encryption.AuditEncryption")
    def test_log_event_with_metadata(self, mock_enc_cls: MagicMock) -> None:
        mock_enc = MagicMock()
        mock_enc.encrypt_event.return_value = {
            "encrypted_event": b"encrypted",
            "event_hash": "hash123",
            "previous_hash": None,
        }
        mock_enc_cls.return_value = mock_enc

        svc = AuditService()
        svc.log_event(
            event_type="access_granted",
            entity_id="entity-2",
            actor_id="user-2",
            action="granted",
            metadata={"ip": "10.0.0.1"},
        )

        # Verify the event passed to encrypt includes metadata
        call_args = mock_enc.encrypt_event.call_args[0][0]
        assert call_args["metadata"] == {"ip": "10.0.0.1"}

    @patch("odg_core.audit.encryption.AuditEncryption")
    def test_verify_integrity(self, mock_enc_cls: MagicMock) -> None:
        mock_enc = MagicMock()
        mock_enc.verify_chain_integrity.return_value = (True, None)
        mock_enc_cls.return_value = mock_enc

        svc = AuditService()
        events = [{"event_hash": "h1", "previous_hash": None}]
        valid, broken_at = svc.verify_integrity(events)

        assert valid is True
        assert broken_at is None
        mock_enc.verify_chain_integrity.assert_called_once_with(events)

    @patch("odg_core.audit.encryption.AuditEncryption")
    def test_verify_integrity_broken(self, mock_enc_cls: MagicMock) -> None:
        mock_enc = MagicMock()
        mock_enc.verify_chain_integrity.return_value = (False, 2)
        mock_enc_cls.return_value = mock_enc

        svc = AuditService()
        valid, broken_at = svc.verify_integrity([])
        assert valid is False
        assert broken_at == 2

    @patch("odg_core.audit.encryption.AuditEncryption")
    def test_log_event_default_metadata(self, mock_enc_cls: MagicMock) -> None:
        mock_enc = MagicMock()
        mock_enc.encrypt_event.return_value = {
            "encrypted_event": b"encrypted",
            "event_hash": "hash",
            "previous_hash": None,
        }
        mock_enc_cls.return_value = mock_enc

        svc = AuditService()
        svc.log_event(
            event_type="test",
            entity_id="e",
            actor_id="a",
            action="x",
        )

        call_args = mock_enc.encrypt_event.call_args[0][0]
        assert call_args["metadata"] == {}
