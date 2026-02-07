"""SHA-256 hash-chained audit events for immutable audit trail."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field

from odg_core.enums import AuditEventType  # noqa: TC001 — runtime needed by Pydantic

# Genesis hash for the first event in the chain
GENESIS_HASH = "0" * 64


class AuditEvent(BaseModel):
    """An immutable, hash-chained audit event.

    Each event references the hash of the previous event, forming a
    tamper-evident chain. The hash covers all fields except `id` and
    `event_hash` itself.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    event_type: AuditEventType
    entity_type: str = Field(min_length=1, max_length=100)
    entity_id: str = Field(min_length=1, max_length=200)
    actor_id: str = Field(min_length=1, max_length=200)
    description: str = Field(default="")
    details: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    previous_hash: str = Field(default=GENESIS_HASH, max_length=64)
    event_hash: str = Field(default="", max_length=64)

    def compute_hash(self) -> str:
        """Compute SHA-256 hash of this event's content.

        Hash covers: event_type, entity_type, entity_id, actor_id,
        description, details, occurred_at, previous_hash.
        """
        payload = {
            "event_type": self.event_type,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "actor_id": self.actor_id,
            "description": self.description,
            "details": self.details,
            "occurred_at": self.occurred_at.isoformat(),
            "previous_hash": self.previous_hash,
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def seal(self) -> AuditEvent:
        """Compute and set the event hash. Returns self for chaining."""
        self.event_hash = self.compute_hash()
        return self

    def verify(self) -> bool:
        """Verify that the stored hash matches the computed hash."""
        return self.event_hash == self.compute_hash()


def verify_chain(events: list[AuditEvent]) -> bool:
    """Verify the integrity of a chain of audit events.

    Checks:
    1. Each event's hash matches its computed hash
    2. Each event's previous_hash matches the prior event's event_hash
    3. First event's previous_hash is the genesis hash
    """
    if not events:
        return True

    if events[0].previous_hash != GENESIS_HASH:
        return False

    for i, event in enumerate(events):
        if not event.verify():
            return False
        if i > 0 and event.previous_hash != events[i - 1].event_hash:
            return False

    return True
