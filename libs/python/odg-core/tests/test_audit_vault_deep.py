"""Deep coverage tests for audit, vault/client, vault/lease_manager, and lineage/emitter.

Targets uncovered lines:
- audit.py lines 3-88 (0% coverage): GENESIS_HASH, AuditEvent, compute_hash, seal, verify, verify_chain
- vault/client.py lines 86-87, 106-112, 124-125: get_database_credentials, renew_database_lease, revoke_database_lease
- vault/lease_manager.py lines 107-115, 158-159: _renewal_loop error path, callback error in _check_and_renew_leases
- lineage/emitter.py lines 40-71: _persist_to_database
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from odg_core.audit import GENESIS_HASH, AuditEvent, verify_chain
from odg_core.enums import AuditEventType
from odg_core.lineage.models import LineageDataset, LineageJob, LineageRunEvent
from odg_core.settings import VaultSettings
from odg_core.vault.client import VaultClient
from odg_core.vault.lease_manager import LeaseManager

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_event(
    event_type: AuditEventType = AuditEventType.DECISION_CREATED,
    previous_hash: str = GENESIS_HASH,
    **kwargs: Any,
) -> AuditEvent:
    """Create an AuditEvent with sensible defaults."""
    defaults = {
        "entity_type": "decision",
        "entity_id": "d-001",
        "actor_id": "user@example.com",
        "description": "test event",
    }
    defaults.update(kwargs)
    return AuditEvent(event_type=event_type, previous_hash=previous_hash, **defaults)


def _build_chain(n: int = 3) -> list[AuditEvent]:
    """Build a valid sealed chain of *n* events."""
    events: list[AuditEvent] = []
    prev_hash = GENESIS_HASH
    for i in range(n):
        evt = _make_event(
            entity_id=f"d-{i:03d}",
            previous_hash=prev_hash,
        ).seal()
        prev_hash = evt.event_hash
        events.append(evt)
    return events


def _vault_settings(enabled: bool = True, token: str = "s.test-token") -> VaultSettings:
    """Return VaultSettings with the given overrides (bypass env)."""
    return VaultSettings(enabled=enabled, token=token, addr="http://vault:8200")


def _mock_hvac_client() -> MagicMock:
    """Return a MagicMock that mimics an hvac.Client."""
    client = MagicMock()
    client.is_authenticated.return_value = True
    return client


# ===========================================================================
# 1. audit.py — full coverage
# ===========================================================================


class TestGenesisHash:
    def test_genesis_hash_value(self):
        assert GENESIS_HASH == "0" * 64
        assert len(GENESIS_HASH) == 64


class TestAuditEventModel:
    def test_default_fields(self):
        evt = _make_event()
        assert isinstance(evt.id, uuid.UUID)
        assert evt.event_type == AuditEventType.DECISION_CREATED
        assert evt.entity_type == "decision"
        assert evt.entity_id == "d-001"
        assert evt.actor_id == "user@example.com"
        assert evt.description == "test event"
        assert evt.details == {}
        assert isinstance(evt.occurred_at, datetime)
        assert evt.previous_hash == GENESIS_HASH
        assert evt.event_hash == ""

    def test_all_event_types_accepted(self):
        """Every AuditEventType enum member can be used."""
        for member in AuditEventType:
            evt = _make_event(event_type=member)
            assert evt.event_type == member

    def test_custom_details(self):
        evt = _make_event(details={"key": "value", "count": 42, "flag": True, "empty": None})
        assert evt.details == {"key": "value", "count": 42, "flag": True, "empty": None}


class TestComputeHash:
    def test_returns_hex_string_64_chars(self):
        h = _make_event().compute_hash()
        assert isinstance(h, str)
        assert len(h) == 64
        int(h, 16)  # must be valid hex

    def test_deterministic(self):
        evt = _make_event()
        assert evt.compute_hash() == evt.compute_hash()

    def test_different_for_different_fields(self):
        e1 = _make_event(description="A")
        e2 = _make_event(description="B")
        assert e1.compute_hash() != e2.compute_hash()

    def test_hash_covers_event_type(self):
        e1 = _make_event(event_type=AuditEventType.DECISION_CREATED)
        e2 = _make_event(event_type=AuditEventType.DECISION_APPROVED)
        assert e1.compute_hash() != e2.compute_hash()

    def test_hash_covers_previous_hash(self):
        e1 = _make_event(previous_hash=GENESIS_HASH)
        e2 = _make_event(previous_hash="a" * 64)
        assert e1.compute_hash() != e2.compute_hash()

    def test_hash_covers_entity_id(self):
        e1 = _make_event(entity_id="d-001")
        e2 = _make_event(entity_id="d-002")
        assert e1.compute_hash() != e2.compute_hash()

    def test_hash_covers_actor_id(self):
        e1 = _make_event(actor_id="alice")
        e2 = _make_event(actor_id="bob")
        assert e1.compute_hash() != e2.compute_hash()

    def test_hash_covers_details(self):
        e1 = _make_event(details={"a": 1})
        e2 = _make_event(details={"a": 2})
        assert e1.compute_hash() != e2.compute_hash()


class TestSeal:
    def test_seal_sets_event_hash(self):
        evt = _make_event()
        assert evt.event_hash == ""
        evt.seal()
        assert evt.event_hash != ""
        assert len(evt.event_hash) == 64

    def test_seal_returns_self(self):
        evt = _make_event()
        assert evt.seal() is evt

    def test_seal_matches_compute_hash(self):
        evt = _make_event()
        expected = evt.compute_hash()
        evt.seal()
        assert evt.event_hash == expected


class TestVerify:
    def test_verify_after_seal(self):
        assert _make_event().seal().verify() is True

    def test_verify_fails_before_seal(self):
        evt = _make_event()
        assert evt.verify() is False

    def test_verify_fails_after_tamper(self):
        evt = _make_event().seal()
        evt.description = "tampered"
        assert evt.verify() is False

    def test_verify_fails_with_wrong_hash(self):
        evt = _make_event().seal()
        evt.event_hash = "f" * 64
        assert evt.verify() is False


class TestVerifyChain:
    def test_empty_chain(self):
        assert verify_chain([]) is True

    def test_single_valid_event(self):
        chain = _build_chain(1)
        assert verify_chain(chain) is True

    def test_multi_event_valid_chain(self):
        chain = _build_chain(5)
        assert verify_chain(chain) is True

    def test_first_event_wrong_previous_hash(self):
        chain = _build_chain(3)
        chain[0].previous_hash = "a" * 64
        # Re-seal so verify() passes but the genesis check fails
        chain[0].seal()
        assert verify_chain(chain) is False

    def test_tampered_event_in_chain(self):
        chain = _build_chain(3)
        chain[1].description = "tampered"
        assert verify_chain(chain) is False

    def test_broken_link_in_chain(self):
        """Swap order of two events so previous_hash link breaks."""
        chain = _build_chain(4)
        chain[1], chain[2] = chain[2], chain[1]
        assert verify_chain(chain) is False

    def test_single_unsealed_event_fails(self):
        evt = _make_event()
        assert verify_chain([evt]) is False


# ===========================================================================
# 2. vault/client.py — uncovered database methods
# ===========================================================================


class TestVaultGetDatabaseCredentials:
    def test_returns_credentials_dict(self):
        mock_client = _mock_hvac_client()
        mock_client.secrets.database.generate_credentials.return_value = {
            "data": {"username": "v-odg-app-abc", "password": "s3cret"},
            "lease_id": "database/creds/odg-app/lease-123",
            "lease_duration": 3600,
        }

        vc = VaultClient(settings=_vault_settings())
        vc._client = mock_client

        result = vc.get_database_credentials(role="odg-app")

        mock_client.secrets.database.generate_credentials.assert_called_once_with(name="odg-app")
        assert result == {
            "username": "v-odg-app-abc",
            "password": "s3cret",
            "lease_id": "database/creds/odg-app/lease-123",
            "lease_duration": 3600,
        }

    def test_default_role(self):
        mock_client = _mock_hvac_client()
        mock_client.secrets.database.generate_credentials.return_value = {
            "data": {"username": "u", "password": "p"},
            "lease_id": "lid",
            "lease_duration": 1800,
        }

        vc = VaultClient(settings=_vault_settings())
        vc._client = mock_client

        vc.get_database_credentials()
        mock_client.secrets.database.generate_credentials.assert_called_once_with(name="odg-app")


class TestVaultRenewDatabaseLease:
    def _setup_vc(self) -> tuple[VaultClient, MagicMock]:
        mock_client = _mock_hvac_client()
        mock_client.sys.renew_lease.return_value = {
            "lease_id": "database/creds/odg-app/lease-123",
            "lease_duration": 3600,
            "renewable": True,
        }
        vc = VaultClient(settings=_vault_settings())
        vc._client = mock_client
        return vc, mock_client

    def test_renew_without_increment(self):
        vc, mock_client = self._setup_vc()

        result = vc.renew_database_lease(lease_id="database/creds/odg-app/lease-123")

        mock_client.sys.renew_lease.assert_called_once_with(
            lease_id="database/creds/odg-app/lease-123",
        )
        assert result == {
            "lease_id": "database/creds/odg-app/lease-123",
            "lease_duration": 3600,
            "renewable": True,
        }

    def test_renew_with_increment(self):
        vc, mock_client = self._setup_vc()

        result = vc.renew_database_lease(
            lease_id="database/creds/odg-app/lease-123",
            increment=7200,
        )

        mock_client.sys.renew_lease.assert_called_once_with(
            lease_id="database/creds/odg-app/lease-123",
            increment=7200,
        )
        assert result["renewable"] is True

    def test_renew_with_zero_increment_takes_else_branch(self):
        """increment=0 is falsy, so the else branch should execute."""
        vc, mock_client = self._setup_vc()

        vc.renew_database_lease(lease_id="lid", increment=0)

        mock_client.sys.renew_lease.assert_called_once_with(lease_id="lid")


class TestVaultRevokeDatabaseLease:
    def test_revoke_calls_sys(self):
        mock_client = _mock_hvac_client()
        vc = VaultClient(settings=_vault_settings())
        vc._client = mock_client

        vc.revoke_database_lease(lease_id="database/creds/odg-app/lease-123")

        mock_client.sys.revoke_lease.assert_called_once_with(
            lease_id="database/creds/odg-app/lease-123",
        )


# ===========================================================================
# 3. vault/lease_manager.py — uncovered error paths
# ===========================================================================


class TestLeaseManagerRenewalLoopErrorPath:
    """Cover lines 107-115 (_renewal_loop exception handling)."""

    @pytest.mark.asyncio
    async def test_renewal_loop_catches_generic_exception_and_continues(self):
        """When _check_and_renew_leases raises a non-CancelledError, the loop
        should log the error, sleep 30s, and continue."""
        mock_vault = MagicMock(spec=VaultClient)
        mgr = LeaseManager(vault_client=mock_vault)

        call_count = 0

        async def _fake_check():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("transient DB failure")
            # On second call, stop the loop
            mgr._running = False

        mgr._check_and_renew_leases = _fake_check  # type: ignore[method-assign]

        with patch("odg_core.vault.lease_manager.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            mgr._running = True
            await mgr._renewal_loop()

        # First iteration: exception -> sleep(30); second: normal -> stop
        assert call_count == 2
        # The error path sleeps 30s
        mock_sleep.assert_any_call(30)

    @pytest.mark.asyncio
    async def test_renewal_loop_breaks_on_cancelled_error(self):
        """CancelledError should break out of the loop immediately."""
        mock_vault = MagicMock(spec=VaultClient)
        mgr = LeaseManager(vault_client=mock_vault)

        async def _fake_check():
            raise asyncio.CancelledError()

        mgr._check_and_renew_leases = _fake_check  # type: ignore[method-assign]

        mgr._running = True
        # Should not raise, should just break
        await mgr._renewal_loop()
        # After breaking, running is still True (loop exited via break, not flag)
        assert mgr._running is True


class TestLeaseManagerCallbackErrorPath:
    """Cover lines 158-159 (callback raises exception during _check_and_renew_leases)."""

    @pytest.mark.asyncio
    async def test_sync_callback_error_is_caught(self, caplog):
        """A sync callback that raises should be caught and logged, not propagated."""
        mock_vault = MagicMock(spec=VaultClient)
        mock_vault.renew_database_lease.return_value = {
            "lease_duration": 3600,
            "lease_id": "lid-1",
            "renewable": True,
        }
        mgr = LeaseManager(vault_client=mock_vault, renewal_threshold=1.0)

        def bad_callback(lease_id, result):
            raise ValueError("callback boom")

        mgr.register_lease("lid-1", lease_duration=100, callback=bad_callback)
        # Set remaining low so renewal triggers
        mgr._leases["lid-1"]["remaining"] = 10

        with caplog.at_level(logging.ERROR, logger="odg_core.vault.lease_manager"):
            await mgr._check_and_renew_leases()

        assert "Error in lease renewal callback" in caplog.text
        assert "callback boom" in caplog.text

    @pytest.mark.asyncio
    async def test_async_callback_error_is_caught(self, caplog):
        """An async callback that raises should also be caught and logged."""
        mock_vault = MagicMock(spec=VaultClient)
        mock_vault.renew_database_lease.return_value = {
            "lease_duration": 3600,
            "lease_id": "lid-2",
            "renewable": True,
        }
        mgr = LeaseManager(vault_client=mock_vault, renewal_threshold=1.0)

        async def bad_async_callback(lease_id, result):
            raise RuntimeError("async callback boom")

        mgr.register_lease("lid-2", lease_duration=100, callback=bad_async_callback)
        mgr._leases["lid-2"]["remaining"] = 10

        with caplog.at_level(logging.ERROR, logger="odg_core.vault.lease_manager"):
            await mgr._check_and_renew_leases()

        assert "Error in lease renewal callback" in caplog.text
        assert "async callback boom" in caplog.text


# ===========================================================================
# 4. lineage/emitter.py — _persist_to_database
# ===========================================================================


class TestPersistToDatabase:
    """Cover lines 40-71 of lineage/emitter.py (_persist_to_database)."""

    def _make_lineage_event(self) -> LineageRunEvent:
        return LineageRunEvent(
            event_type="COMPLETE",
            event_time=datetime.now(UTC),
            run={"runId": str(uuid.uuid4())},
            job=LineageJob(namespace="lakehouse", name="transform_sales"),
            inputs=[LineageDataset(namespace="bronze", name="raw_sales", facets={"schema": {}})],
            outputs=[LineageDataset(namespace="silver", name="clean_sales")],
        )

    def test_persist_success(self):
        """Happy path: event is persisted via SQLAlchemy session."""
        from odg_core.lineage.emitter import _persist_to_database

        event = self._make_lineage_event()

        mock_engine = MagicMock()
        mock_session_instance = MagicMock()
        mock_session_cm = MagicMock()
        mock_session_cm.__enter__ = MagicMock(return_value=mock_session_instance)
        mock_session_cm.__exit__ = MagicMock(return_value=False)
        mock_session_cls = MagicMock(return_value=mock_session_cm)
        mock_create_engine = MagicMock(return_value=mock_engine)

        mock_row_cls = MagicMock()
        mock_row_instance = MagicMock()
        mock_row_instance.id = uuid.uuid4()
        mock_row_cls.return_value = mock_row_instance

        with (
            patch("sqlalchemy.create_engine", mock_create_engine),
            patch("sqlalchemy.orm.Session", mock_session_cls),
            patch("odg_core.db.tables.LineageEventRow", mock_row_cls),
        ):
            _persist_to_database(event)

        mock_create_engine.assert_called_once()
        mock_session_cls.assert_called_once_with(mock_engine)
        mock_session_instance.add.assert_called_once_with(mock_row_instance)
        mock_session_instance.commit.assert_called_once()

    def test_persist_exception_is_caught(self, caplog):
        """When the database is unreachable, _persist_to_database logs a warning."""
        from odg_core.lineage.emitter import _persist_to_database

        event = self._make_lineage_event()

        with (
            patch(
                "sqlalchemy.create_engine",
                side_effect=Exception("connection refused"),
            ),
            caplog.at_level(logging.WARNING),
        ):
            # Should not raise
            _persist_to_database(event)

        assert "Failed to persist lineage event to database" in caplog.text

    def test_persist_with_event_time_as_string(self):
        """When event_time is a string, the fromisoformat branch executes."""

        event = LineageRunEvent(
            event_type="START",
            event_time="2025-01-15T10:30:00+00:00",
            run={"runId": "run-abc"},
            job=LineageJob(namespace="lakehouse", name="ingest_users"),
            inputs=[],
            outputs=[LineageDataset(namespace="silver", name="users")],
        )

        mock_engine = MagicMock()
        mock_session_instance = MagicMock()
        mock_session_cm = MagicMock()
        mock_session_cm.__enter__ = MagicMock(return_value=mock_session_instance)
        mock_session_cm.__exit__ = MagicMock(return_value=False)
        mock_session_cls = MagicMock(return_value=mock_session_cm)
        mock_create_engine = MagicMock(return_value=mock_engine)

        mock_row_cls = MagicMock()
        mock_row_instance = MagicMock()
        mock_row_instance.id = uuid.uuid4()
        mock_row_cls.return_value = mock_row_instance

        with (
            patch.dict(
                "sys.modules",
                {
                    "sqlalchemy": MagicMock(create_engine=mock_create_engine),
                    "sqlalchemy.orm": MagicMock(Session=mock_session_cls),
                },
            ),
            patch("odg_core.db.tables.LineageEventRow", mock_row_cls),
        ):
            import odg_core.lineage.emitter as emitter_mod

            emitter_mod._persist_to_database(event)

        mock_session_instance.add.assert_called_once()
        mock_session_instance.commit.assert_called_once()

    def test_persist_without_run_id_generates_uuid(self):
        """When run dict has no runId key, a UUID is generated as fallback."""

        event = LineageRunEvent(
            event_type="COMPLETE",
            event_time=datetime.now(UTC),
            run={},  # no runId
            job=LineageJob(namespace="lakehouse", name="job_x"),
            inputs=[],
            outputs=[],
        )

        mock_engine = MagicMock()
        mock_session_instance = MagicMock()
        mock_session_cm = MagicMock()
        mock_session_cm.__enter__ = MagicMock(return_value=mock_session_instance)
        mock_session_cm.__exit__ = MagicMock(return_value=False)
        mock_session_cls = MagicMock(return_value=mock_session_cm)
        mock_create_engine = MagicMock(return_value=mock_engine)

        captured_row = {}

        def capture_row(**kwargs):
            captured_row.update(kwargs)
            m = MagicMock()
            m.id = uuid.uuid4()
            return m

        mock_row_cls = MagicMock(side_effect=capture_row)

        with (
            patch.dict(
                "sys.modules",
                {
                    "sqlalchemy": MagicMock(create_engine=mock_create_engine),
                    "sqlalchemy.orm": MagicMock(Session=mock_session_cls),
                },
            ),
            patch("odg_core.db.tables.LineageEventRow", mock_row_cls),
        ):
            import odg_core.lineage.emitter as emitter_mod

            emitter_mod._persist_to_database(event)

        # The run_id should be a valid UUID string (the fallback from str(uuid.uuid4()))
        assert "run_id" in captured_row
        uuid.UUID(captured_row["run_id"])  # validates it's a UUID

    def test_emit_lineage_event_calls_persist(self):
        """emit_lineage_event should invoke _persist_to_database."""
        with patch("odg_core.lineage.emitter._persist_to_database") as mock_persist:
            from odg_core.lineage.emitter import emit_lineage_event

            result = emit_lineage_event(
                job_name="my_job",
                inputs=[{"namespace": "bronze", "name": "raw"}],
                outputs=[{"namespace": "silver", "name": "clean"}],
            )

        assert result.event_type == "COMPLETE"
        assert result.job.name == "my_job"
        mock_persist.assert_called_once()
