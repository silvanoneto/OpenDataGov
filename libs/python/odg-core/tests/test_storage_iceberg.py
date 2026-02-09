"""Tests for odg_core.storage.iceberg_catalog module."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from odg_core.storage.iceberg_catalog import IcebergCatalog


@pytest.fixture()
def mock_catalog() -> MagicMock:
    """Create a mock pyiceberg catalog."""
    return MagicMock()


@pytest.fixture()
def iceberg(mock_catalog: MagicMock) -> IcebergCatalog:
    """Create an IcebergCatalog with a pre-injected mock catalog."""
    ic = IcebergCatalog(warehouse_path="s3://test-warehouse/")
    ic._catalog = mock_catalog
    return ic


# ──── _get_catalog / catalog property ────────────────────────


class TestGetCatalog:
    """Tests for lazy catalog loading."""

    def test_catalog_property_returns_mock(self, iceberg: IcebergCatalog, mock_catalog: MagicMock) -> None:
        assert iceberg.catalog is mock_catalog

    @patch("odg_core.storage.iceberg_catalog.IcebergCatalog._get_catalog")
    def test_get_catalog_called_once(self, mock_get: MagicMock) -> None:
        mock_get.return_value = MagicMock()
        ic = IcebergCatalog()
        _ = ic.catalog
        mock_get.assert_called_once()


# ──── create_table ───────────────────────────────────────────


class TestCreateTable:
    """Tests for IcebergCatalog.create_table."""

    def test_calls_catalog_create_table(self, iceberg: IcebergCatalog, mock_catalog: MagicMock) -> None:
        mock_schema = MagicMock()
        iceberg.create_table("gold", "customers", mock_schema)

        mock_catalog.create_table.assert_called_once()
        call_args = mock_catalog.create_table.call_args
        assert call_args[0][0] == "gold.customers"
        assert call_args[1]["schema"] is mock_schema

    def test_create_table_returns_result(self, iceberg: IcebergCatalog, mock_catalog: MagicMock) -> None:
        mock_table = MagicMock()
        mock_catalog.create_table.return_value = mock_table

        result = iceberg.create_table("bronze", "raw", MagicMock())
        assert result is mock_table


# ──── get_snapshot_id ────────────────────────────────────────


class TestGetSnapshotId:
    """Tests for IcebergCatalog.get_snapshot_id."""

    def test_returns_snapshot_id_as_string(self, iceberg: IcebergCatalog, mock_catalog: MagicMock) -> None:
        mock_table = MagicMock()
        mock_snapshot = MagicMock()
        mock_snapshot.snapshot_id = 1234567890
        mock_table.current_snapshot.return_value = mock_snapshot
        mock_catalog.load_table.return_value = mock_table

        result = iceberg.get_snapshot_id("gold", "customers")
        assert result == "1234567890"
        mock_catalog.load_table.assert_called_once_with("gold.customers")

    def test_raises_value_error_when_no_snapshot(self, iceberg: IcebergCatalog, mock_catalog: MagicMock) -> None:
        mock_table = MagicMock()
        mock_table.current_snapshot.return_value = None
        mock_catalog.load_table.return_value = mock_table

        with pytest.raises(ValueError, match="has no snapshots"):
            iceberg.get_snapshot_id("gold", "customers")


# ──── time_travel ────────────────────────────────────────────


class TestTimeTravel:
    """Tests for IcebergCatalog.time_travel."""

    def test_passes_snapshot_id_as_int(self, iceberg: IcebergCatalog, mock_catalog: MagicMock) -> None:
        mock_table = MagicMock()
        mock_scan = MagicMock()
        mock_table.scan.return_value = mock_scan
        mock_scan.to_pandas.return_value = "fake_df"
        mock_catalog.load_table.return_value = mock_table

        result = iceberg.time_travel("gold", "customers", "999")

        mock_table.scan.assert_called_once_with(snapshot_id=999)
        assert result == "fake_df"


# ──── list_snapshots ─────────────────────────────────────────


class TestListSnapshots:
    """Tests for IcebergCatalog.list_snapshots."""

    def test_returns_list_of_snapshot_dicts(self, iceberg: IcebergCatalog, mock_catalog: MagicMock) -> None:
        mock_snap1 = MagicMock()
        mock_snap1.snapshot_id = 100
        mock_snap1.timestamp_ms = 1700000000000
        mock_snap1.summary = {"operation": "append"}

        mock_snap2 = MagicMock()
        mock_snap2.snapshot_id = 200
        mock_snap2.timestamp_ms = 1700001000000
        mock_snap2.summary = {"operation": "overwrite"}

        mock_table = MagicMock()
        mock_table.history.return_value = [mock_snap1, mock_snap2]
        mock_catalog.load_table.return_value = mock_table

        result = iceberg.list_snapshots("gold", "customers")

        assert len(result) == 2
        assert result[0]["snapshot_id"] == "100"
        assert result[0]["operation"] == "append"
        assert result[1]["snapshot_id"] == "200"
        assert "timestamp" in result[0]
        assert "timestamp_ms" in result[0]


# ──── rollback_to_snapshot ───────────────────────────────────


class TestRollbackToSnapshot:
    """Tests for IcebergCatalog.rollback_to_snapshot."""

    def test_calls_manage_snapshots_rollback(self, iceberg: IcebergCatalog, mock_catalog: MagicMock) -> None:
        mock_table = MagicMock()
        mock_manage = MagicMock()
        mock_table.manageSnapshots.return_value = mock_manage
        mock_manage.rollback_to_snapshot.return_value = mock_manage
        mock_catalog.load_table.return_value = mock_table

        iceberg.rollback_to_snapshot("gold", "customers", "555")

        mock_manage.rollback_to_snapshot.assert_called_once_with(555)
        mock_manage.commit.assert_called_once()


# ──── tag_snapshot ───────────────────────────────────────────


class TestTagSnapshot:
    """Tests for IcebergCatalog.tag_snapshot."""

    def test_calls_create_tag_and_commit(self, iceberg: IcebergCatalog, mock_catalog: MagicMock) -> None:
        mock_table = MagicMock()
        mock_manage = MagicMock()
        mock_table.manageSnapshots.return_value = mock_manage
        mock_manage.createTag.return_value = mock_manage
        mock_catalog.load_table.return_value = mock_table

        iceberg.tag_snapshot("gold", "customers", "777", "production_v1")

        mock_manage.createTag.assert_called_once_with("production_v1", 777)
        mock_manage.commit.assert_called_once()


# ──── get_snapshot_by_tag ────────────────────────────────────


class TestGetSnapshotByTag:
    """Tests for IcebergCatalog.get_snapshot_by_tag."""

    def test_returns_snapshot_id(self, iceberg: IcebergCatalog, mock_catalog: MagicMock) -> None:
        mock_table = MagicMock()
        mock_ref = MagicMock()
        mock_ref.snapshot_id = 888
        mock_table.snapshot_by_name.return_value = mock_ref
        mock_catalog.load_table.return_value = mock_table

        result = iceberg.get_snapshot_by_tag("gold", "customers", "production")
        assert result == "888"

    def test_raises_when_tag_not_found(self, iceberg: IcebergCatalog, mock_catalog: MagicMock) -> None:
        mock_table = MagicMock()
        mock_table.snapshot_by_name.return_value = None
        mock_catalog.load_table.return_value = mock_table

        with pytest.raises(ValueError, match=r"Tag .* not found"):
            iceberg.get_snapshot_by_tag("gold", "customers", "nonexistent")


# ──── expire_old_snapshots ───────────────────────────────────


class TestExpireOldSnapshots:
    """Tests for IcebergCatalog.expire_old_snapshots."""

    def test_returns_zero_when_no_old_snapshots(self, iceberg: IcebergCatalog, mock_catalog: MagicMock) -> None:
        mock_snap = MagicMock()
        mock_snap.snapshot_id = 1
        # Very recent timestamp (won't be expired)
        mock_snap.timestamp_ms = int(datetime.now().timestamp() * 1000)

        mock_table = MagicMock()
        mock_table.history.return_value = [mock_snap]
        mock_catalog.load_table.return_value = mock_table

        result = iceberg.expire_old_snapshots("gold", "customers", older_than_days=90, keep_last_n=30)
        assert result == 0

    def test_returns_count_of_expired_snapshots(self, iceberg: IcebergCatalog, mock_catalog: MagicMock) -> None:
        # Create snapshots: 2 old + 1 recent
        old_ts = int((datetime.now().timestamp() - 200 * 86400) * 1000)  # 200 days ago
        recent_ts = int(datetime.now().timestamp() * 1000)

        old_snap1 = MagicMock()
        old_snap1.snapshot_id = 1
        old_snap1.timestamp_ms = old_ts

        old_snap2 = MagicMock()
        old_snap2.snapshot_id = 2
        old_snap2.timestamp_ms = old_ts

        recent_snap = MagicMock()
        recent_snap.snapshot_id = 3
        recent_snap.timestamp_ms = recent_ts

        mock_table = MagicMock()
        mock_table.history.return_value = [old_snap1, old_snap2, recent_snap]
        mock_manage = MagicMock()
        mock_manage.expireOlderThan.return_value = mock_manage
        mock_table.manageSnapshots.return_value = mock_manage
        mock_catalog.load_table.return_value = mock_table

        result = iceberg.expire_old_snapshots("gold", "customers", older_than_days=90, keep_last_n=1)

        assert result == 2
        mock_manage.expireOlderThan.assert_called_once()
        mock_manage.commit.assert_called_once()
