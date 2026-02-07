"""Audit service for managing the hash-chained audit trail."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from odg_core.audit import GENESIS_HASH, AuditEvent, verify_chain

if TYPE_CHECKING:
    from odg_core.enums import AuditEventType

    from governance_engine.repository.protocols import AuditRepository


class AuditService:
    """Manages the append-only, hash-chained audit trail."""

    def __init__(self, repo: AuditRepository) -> None:
        self._repo = repo

    async def record_event(
        self,
        *,
        event_type: AuditEventType,
        entity_type: str,
        entity_id: str,
        actor_id: str,
        description: str = "",
        details: dict[str, Any] | None = None,
    ) -> AuditEvent:
        """Record a new audit event, extending the hash chain."""
        last_hash = await self._repo.get_last_hash()

        event = AuditEvent(
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            actor_id=actor_id,
            description=description,
            details=details or {},
            previous_hash=last_hash or GENESIS_HASH,
        )
        event.seal()

        return await self._repo.create(event)

    async def verify_integrity(self, *, limit: int = 1000) -> bool:
        """Verify the integrity of the audit chain."""
        events = await self._repo.get_chain(limit=limit)
        return verify_chain(events)

    async def get_events_for_entity(
        self,
        entity_id: str,
        *,
        limit: int = 50,
    ) -> list[AuditEvent]:
        return await self._repo.list_by_entity(entity_id, limit=limit)

    async def get_events(
        self,
        *,
        event_type: AuditEventType | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[AuditEvent]:
        return await self._repo.list_events(event_type=event_type, limit=limit, offset=offset)
