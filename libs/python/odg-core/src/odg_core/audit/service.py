"""Audit service for encrypted, tamper-proof logging (ADR-073, Phase 5).

Provides:
- Encrypted audit event storage
- Hash chain verification
- Compliance reporting
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class AuditService:
    """Service for managing encrypted audit events."""

    def __init__(self) -> None:
        """Initialize audit service."""
        from odg_core.audit.encryption import AuditEncryption

        self._encryption = AuditEncryption()

    def log_event(
        self,
        event_type: str,
        entity_id: str,
        actor_id: str,
        action: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Log an encrypted audit event.

        Args:
            event_type: Type of event (e.g., "decision_created", "access_granted")
            entity_id: ID of entity being audited
            actor_id: ID of user/service performing action
            action: Action description
            metadata: Additional event metadata

        Returns:
            Encrypted audit record ready for storage
        """
        # Construct event
        event = {
            "event_type": event_type,
            "entity_id": entity_id,
            "actor_id": actor_id,
            "action": action,
            "metadata": metadata or {},
        }

        # TODO: Fetch previous_hash from database
        previous_hash = None

        # Encrypt and hash
        encrypted_record = self._encryption.encrypt_event(event, previous_hash)

        # Add event metadata for storage
        encrypted_record["event_type"] = event_type
        encrypted_record["entity_id"] = entity_id
        encrypted_record["actor_id"] = actor_id

        return encrypted_record

    def verify_integrity(self, events: list[dict[str, Any]]) -> tuple[bool, int | None]:
        """Verify audit chain integrity.

        Args:
            events: List of audit events from database

        Returns:
            Tuple of (is_valid, broken_at_index)
        """
        return self._encryption.verify_chain_integrity(events)
