"""Tests for odg_core audit hash chain."""

from odg_core.audit import GENESIS_HASH, AuditEvent, verify_chain
from odg_core.enums import AuditEventType


def _make_event(
    previous_hash: str = GENESIS_HASH,
    event_type: AuditEventType = AuditEventType.DECISION_CREATED,
) -> AuditEvent:
    return AuditEvent(
        event_type=event_type,
        entity_type="decision",
        entity_id="dec-001",
        actor_id="user-1",
        description="Test event",
        previous_hash=previous_hash,
    )


class TestAuditEvent:
    def test_compute_hash_deterministic(self) -> None:
        e = _make_event()
        h1 = e.compute_hash()
        h2 = e.compute_hash()
        assert h1 == h2
        assert len(h1) == 64

    def test_seal_sets_hash(self) -> None:
        e = _make_event()
        assert e.event_hash == ""
        e.seal()
        assert e.event_hash != ""
        assert len(e.event_hash) == 64

    def test_verify_after_seal(self) -> None:
        e = _make_event()
        e.seal()
        assert e.verify() is True

    def test_verify_fails_after_tamper(self) -> None:
        e = _make_event()
        e.seal()
        e.description = "tampered"
        assert e.verify() is False

    def test_different_events_different_hashes(self) -> None:
        e1 = _make_event(event_type=AuditEventType.DECISION_CREATED)
        e1.seal()
        e2 = _make_event(event_type=AuditEventType.DECISION_APPROVED)
        e2.seal()
        assert e1.event_hash != e2.event_hash


class TestVerifyChain:
    def test_empty_chain(self) -> None:
        assert verify_chain([]) is True

    def test_single_event_chain(self) -> None:
        e = _make_event()
        e.seal()
        assert verify_chain([e]) is True

    def test_valid_chain(self) -> None:
        e1 = _make_event()
        e1.seal()

        e2 = AuditEvent(
            event_type=AuditEventType.APPROVAL_CAST,
            entity_type="decision",
            entity_id="dec-001",
            actor_id="user-2",
            description="Approved",
            previous_hash=e1.event_hash,
        )
        e2.seal()

        e3 = AuditEvent(
            event_type=AuditEventType.DECISION_APPROVED,
            entity_type="decision",
            entity_id="dec-001",
            actor_id="system",
            description="Finalized",
            previous_hash=e2.event_hash,
        )
        e3.seal()

        assert verify_chain([e1, e2, e3]) is True

    def test_broken_chain_tampered_event(self) -> None:
        e1 = _make_event()
        e1.seal()

        e2 = AuditEvent(
            event_type=AuditEventType.APPROVAL_CAST,
            entity_type="decision",
            entity_id="dec-001",
            actor_id="user-2",
            previous_hash=e1.event_hash,
        )
        e2.seal()
        e2.description = "tampered"

        assert verify_chain([e1, e2]) is False

    def test_broken_chain_wrong_previous_hash(self) -> None:
        e1 = _make_event()
        e1.seal()

        e2 = AuditEvent(
            event_type=AuditEventType.APPROVAL_CAST,
            entity_type="decision",
            entity_id="dec-001",
            actor_id="user-2",
            previous_hash="wrong_hash",
        )
        e2.seal()

        assert verify_chain([e1, e2]) is False

    def test_chain_fails_if_first_not_genesis(self) -> None:
        e = AuditEvent(
            event_type=AuditEventType.DECISION_CREATED,
            entity_type="decision",
            entity_id="dec-001",
            actor_id="user-1",
            previous_hash="not_genesis",
        )
        e.seal()

        assert verify_chain([e]) is False
