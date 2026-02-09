"""Tests for odg_core.audit module - SHA-256 hash-chained audit events."""

from __future__ import annotations

import uuid

from odg_core.audit import GENESIS_HASH, AuditEvent, verify_chain
from odg_core.enums import AuditEventType

# ── GENESIS_HASH ──────────────────────────────────────────────


class TestGenesisHash:
    def test_is_64_zeros(self) -> None:
        assert GENESIS_HASH == "0" * 64

    def test_length(self) -> None:
        assert len(GENESIS_HASH) == 64


# ── AuditEvent creation ──────────────────────────────────────


class TestAuditEventCreation:
    def test_defaults(self) -> None:
        event = AuditEvent(
            event_type=AuditEventType.DECISION_CREATED,
            entity_type="decision",
            entity_id="d-1",
            actor_id="user-1",
        )
        assert isinstance(event.id, uuid.UUID)
        assert event.description == ""
        assert event.details == {}
        assert event.previous_hash == GENESIS_HASH
        assert event.event_hash == ""

    def test_custom_fields(self) -> None:
        event = AuditEvent(
            event_type=AuditEventType.DATA_PROMOTED,
            entity_type="model_card",
            entity_id="mc-1",
            actor_id="admin",
            description="Updated model card",
            details={"field": "accuracy", "old": 0.9, "new": 0.95},
        )
        assert event.description == "Updated model card"
        assert event.details["field"] == "accuracy"


# ── compute_hash ──────────────────────────────────────────────


class TestComputeHash:
    def test_returns_hex_string(self) -> None:
        event = AuditEvent(
            event_type=AuditEventType.DECISION_CREATED,
            entity_type="decision",
            entity_id="d-1",
            actor_id="user-1",
        )
        h = event.compute_hash()
        assert isinstance(h, str)
        assert len(h) == 64
        # valid hex characters
        int(h, 16)

    def test_deterministic(self) -> None:
        event = AuditEvent(
            event_type=AuditEventType.DECISION_CREATED,
            entity_type="decision",
            entity_id="d-1",
            actor_id="user-1",
        )
        assert event.compute_hash() == event.compute_hash()

    def test_different_events_different_hash(self) -> None:
        e1 = AuditEvent(
            event_type=AuditEventType.DECISION_CREATED,
            entity_type="decision",
            entity_id="d-1",
            actor_id="user-1",
        )
        e2 = AuditEvent(
            event_type=AuditEventType.DECISION_CREATED,
            entity_type="decision",
            entity_id="d-2",
            actor_id="user-1",
        )
        assert e1.compute_hash() != e2.compute_hash()


# ── seal ──────────────────────────────────────────────────────


class TestSeal:
    def test_seal_sets_event_hash(self) -> None:
        event = AuditEvent(
            event_type=AuditEventType.DECISION_CREATED,
            entity_type="decision",
            entity_id="d-1",
            actor_id="user-1",
        )
        assert event.event_hash == ""
        event.seal()
        assert event.event_hash != ""
        assert len(event.event_hash) == 64

    def test_seal_returns_self(self) -> None:
        event = AuditEvent(
            event_type=AuditEventType.DECISION_CREATED,
            entity_type="decision",
            entity_id="d-1",
            actor_id="user-1",
        )
        result = event.seal()
        assert result is event

    def test_seal_hash_matches_compute(self) -> None:
        event = AuditEvent(
            event_type=AuditEventType.DECISION_CREATED,
            entity_type="decision",
            entity_id="d-1",
            actor_id="user-1",
        )
        event.seal()
        assert event.event_hash == event.compute_hash()


# ── verify ────────────────────────────────────────────────────


class TestVerify:
    def test_sealed_event_verifies(self) -> None:
        event = AuditEvent(
            event_type=AuditEventType.DECISION_CREATED,
            entity_type="decision",
            entity_id="d-1",
            actor_id="user-1",
        ).seal()
        assert event.verify() is True

    def test_unsealed_event_does_not_verify(self) -> None:
        event = AuditEvent(
            event_type=AuditEventType.DECISION_CREATED,
            entity_type="decision",
            entity_id="d-1",
            actor_id="user-1",
        )
        # event_hash is "" which won't match computed hash
        assert event.verify() is False

    def test_tampered_event_does_not_verify(self) -> None:
        event = AuditEvent(
            event_type=AuditEventType.DECISION_CREATED,
            entity_type="decision",
            entity_id="d-1",
            actor_id="user-1",
        ).seal()

        # Tamper with the description
        event.description = "TAMPERED"
        assert event.verify() is False


# ── verify_chain ──────────────────────────────────────────────


class TestVerifyChain:
    def _build_chain(self, n: int) -> list[AuditEvent]:
        chain: list[AuditEvent] = []
        prev_hash = GENESIS_HASH
        for i in range(n):
            event = AuditEvent(
                event_type=AuditEventType.DECISION_CREATED,
                entity_type="decision",
                entity_id=f"d-{i}",
                actor_id="user-1",
                previous_hash=prev_hash,
            ).seal()
            chain.append(event)
            prev_hash = event.event_hash
        return chain

    def test_empty_chain_is_valid(self) -> None:
        assert verify_chain([]) is True

    def test_single_event_chain(self) -> None:
        chain = self._build_chain(1)
        assert verify_chain(chain) is True

    def test_multi_event_chain(self) -> None:
        chain = self._build_chain(5)
        assert verify_chain(chain) is True

    def test_tampered_hash_detected(self) -> None:
        chain = self._build_chain(3)
        chain[1].event_hash = "bad_hash"
        assert verify_chain(chain) is False

    def test_broken_link_detected(self) -> None:
        chain = self._build_chain(3)
        # Break the chain link
        chain[2].previous_hash = "0" * 64
        chain[2].seal()
        assert verify_chain(chain) is False

    def test_wrong_genesis_hash(self) -> None:
        event = AuditEvent(
            event_type=AuditEventType.DECISION_CREATED,
            entity_type="decision",
            entity_id="d-0",
            actor_id="user-1",
            previous_hash="wrong_genesis",
        ).seal()
        assert verify_chain([event]) is False
