"""Tests for vault lease manager module."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from odg_core.vault.lease_manager import LeaseManager


@pytest.fixture
def mock_vault() -> MagicMock:
    vault = MagicMock()
    vault.renew_database_lease.return_value = {
        "lease_id": "lease-renewed",
        "lease_duration": 3600,
        "renewable": True,
    }
    return vault


class TestLeaseManagerInit:
    def test_default_threshold(self, mock_vault: MagicMock) -> None:
        mgr = LeaseManager(vault_client=mock_vault)
        assert mgr._renewal_threshold == 0.5

    def test_custom_threshold(self, mock_vault: MagicMock) -> None:
        mgr = LeaseManager(vault_client=mock_vault, renewal_threshold=0.3)
        assert mgr._renewal_threshold == 0.3


class TestRegisterLease:
    def test_register_lease(self, mock_vault: MagicMock) -> None:
        mgr = LeaseManager(vault_client=mock_vault)
        mgr.register_lease("lease-1", 3600)
        info = mgr.get_lease_info("lease-1")
        assert info is not None
        assert info["duration"] == 3600
        assert info["remaining"] == 3600

    def test_register_with_callback(self, mock_vault: MagicMock) -> None:
        cb = MagicMock()
        mgr = LeaseManager(vault_client=mock_vault)
        mgr.register_lease("lease-1", 3600, callback=cb)
        info = mgr.get_lease_info("lease-1")
        assert info is not None
        assert info["callback"] is cb

    def test_unregister_lease(self, mock_vault: MagicMock) -> None:
        mgr = LeaseManager(vault_client=mock_vault)
        mgr.register_lease("lease-1", 3600)
        mgr.unregister_lease("lease-1")
        assert mgr.get_lease_info("lease-1") is None

    def test_unregister_nonexistent(self, mock_vault: MagicMock) -> None:
        mgr = LeaseManager(vault_client=mock_vault)
        mgr.unregister_lease("nonexistent")  # Should not raise


class TestGetLeaseInfo:
    def test_get_existing(self, mock_vault: MagicMock) -> None:
        mgr = LeaseManager(vault_client=mock_vault)
        mgr.register_lease("lease-1", 3600)
        assert mgr.get_lease_info("lease-1") is not None

    def test_get_nonexistent(self, mock_vault: MagicMock) -> None:
        mgr = LeaseManager(vault_client=mock_vault)
        assert mgr.get_lease_info("nonexistent") is None


class TestListLeases:
    def test_list_empty(self, mock_vault: MagicMock) -> None:
        mgr = LeaseManager(vault_client=mock_vault)
        assert mgr.list_leases() == []

    def test_list_multiple(self, mock_vault: MagicMock) -> None:
        mgr = LeaseManager(vault_client=mock_vault)
        mgr.register_lease("lease-1", 3600)
        mgr.register_lease("lease-2", 7200)
        leases = mgr.list_leases()
        assert len(leases) == 2
        assert leases[0]["lease_id"] == "lease-1"
        assert leases[1]["lease_id"] == "lease-2"

    def test_list_shows_expiring_soon(self, mock_vault: MagicMock) -> None:
        mgr = LeaseManager(vault_client=mock_vault, renewal_threshold=0.5)
        mgr.register_lease("lease-1", 3600)
        # Simulate low remaining
        mgr._leases["lease-1"]["remaining"] = 100
        leases = mgr.list_leases()
        assert leases[0]["expiring_soon"] is True


class TestCheckAndRenewLeases:
    @pytest.mark.asyncio
    async def test_renew_expiring_lease(self, mock_vault: MagicMock) -> None:
        mgr = LeaseManager(vault_client=mock_vault, renewal_threshold=0.5)
        mgr.register_lease("lease-1", 3600)
        # Set remaining below threshold
        mgr._leases["lease-1"]["remaining"] = 1000
        await mgr._check_and_renew_leases()
        mock_vault.renew_database_lease.assert_called_once_with("lease-1")

    @pytest.mark.asyncio
    async def test_no_renew_healthy_lease(self, mock_vault: MagicMock) -> None:
        mgr = LeaseManager(vault_client=mock_vault, renewal_threshold=0.5)
        mgr.register_lease("lease-1", 3600)
        # remaining is 3600, threshold is 1800 -> still OK after -30
        await mgr._check_and_renew_leases()
        mock_vault.renew_database_lease.assert_not_called()

    @pytest.mark.asyncio
    async def test_renew_calls_callback(self, mock_vault: MagicMock) -> None:
        cb = MagicMock()
        mgr = LeaseManager(vault_client=mock_vault, renewal_threshold=0.5)
        mgr.register_lease("lease-1", 3600, callback=cb)
        mgr._leases["lease-1"]["remaining"] = 100
        await mgr._check_and_renew_leases()
        cb.assert_called_once()

    @pytest.mark.asyncio
    async def test_renew_calls_async_callback(self, mock_vault: MagicMock) -> None:
        called_with: list[tuple[str, dict[str, object]]] = []

        async def async_cb(lease_id: str, result: dict[str, object]) -> None:
            called_with.append((lease_id, result))

        mgr = LeaseManager(vault_client=mock_vault, renewal_threshold=0.5)
        mgr.register_lease("lease-1", 3600, callback=async_cb)
        mgr._leases["lease-1"]["remaining"] = 100
        await mgr._check_and_renew_leases()
        assert len(called_with) == 1
        assert called_with[0][0] == "lease-1"

    @pytest.mark.asyncio
    async def test_expired_lease_unregistered(self, mock_vault: MagicMock) -> None:
        mock_vault.renew_database_lease.side_effect = Exception("Vault unavailable")
        mgr = LeaseManager(vault_client=mock_vault, renewal_threshold=0.5)
        mgr.register_lease("lease-1", 3600)
        mgr._leases["lease-1"]["remaining"] = -10
        await mgr._check_and_renew_leases()
        assert mgr.get_lease_info("lease-1") is None


class TestStartStop:
    @pytest.mark.asyncio
    async def test_start_and_stop(self, mock_vault: MagicMock) -> None:
        mgr = LeaseManager(vault_client=mock_vault)
        await mgr.start()
        assert mgr._running is True
        assert mgr._task is not None
        await mgr.stop()
        assert mgr._running is False
        assert mgr._task is None

    @pytest.mark.asyncio
    async def test_start_twice_noop(self, mock_vault: MagicMock) -> None:
        mgr = LeaseManager(vault_client=mock_vault)
        await mgr.start()
        task1 = mgr._task
        await mgr.start()  # Should not create new task
        assert mgr._task is task1
        await mgr.stop()

    @pytest.mark.asyncio
    async def test_stop_when_not_running(self, mock_vault: MagicMock) -> None:
        mgr = LeaseManager(vault_client=mock_vault)
        await mgr.stop()  # Should not raise
