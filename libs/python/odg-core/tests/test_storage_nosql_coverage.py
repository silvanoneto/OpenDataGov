"""Coverage tests for storage (base_storage, minio) and nosql (couchdb, feast) modules."""

from __future__ import annotations

import sys
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from odg_core.storage.base_storage import BaseStorage, StorageMetadata

# ── StorageMetadata ──────────────────────────────────────────


class TestStorageMetadata:
    def test_create_minimal(self) -> None:
        meta = StorageMetadata(path="test/path")
        assert meta.path == "test/path"
        assert meta.size_bytes is None
        assert meta.content_type is None
        assert meta.etag is None
        assert meta.last_modified is None
        assert meta.custom_metadata == {}

    def test_create_full(self) -> None:
        meta = StorageMetadata(
            path="data/file.parquet",
            size_bytes=1024,
            content_type="application/octet-stream",
            etag="abc123",
            last_modified="2026-01-01T00:00:00",
            custom_metadata={"layer": "gold"},
        )
        assert meta.size_bytes == 1024
        assert meta.custom_metadata["layer"] == "gold"


# ── BaseStorage ──────────────────────────────────────────────


class _DummyStorage(BaseStorage):
    """Concrete storage for testing."""

    def __init__(self) -> None:
        self._data: dict[str, bytes] = {}

    async def read(self, path: str) -> bytes:
        if path not in self._data:
            raise FileNotFoundError(f"Not found: {path}")
        return self._data[path]

    async def write(self, path: str, data: bytes) -> None:
        self._data[path] = data

    async def list(self, prefix: str = "") -> list[str]:
        return [k for k in self._data if k.startswith(prefix)]

    async def delete(self, path: str) -> None:
        if path not in self._data:
            raise FileNotFoundError(f"Not found: {path}")
        del self._data[path]

    def get_storage_type(self) -> str:
        return "dummy"


class TestBaseStorage:
    @pytest.mark.asyncio
    async def test_exists_true(self) -> None:
        storage = _DummyStorage()
        storage._data["test/file"] = b"data"
        # exists calls get_metadata which raises NotImplementedError for base
        # But _DummyStorage doesn't implement it, so exists returns False
        result = await storage.exists("test/file")
        assert result is False  # Because get_metadata raises NotImplementedError

    @pytest.mark.asyncio
    async def test_exists_file_not_found(self) -> None:
        storage = _DummyStorage()
        result = await storage.exists("missing/file")
        assert result is False

    @pytest.mark.asyncio
    async def test_get_metadata_not_implemented(self) -> None:
        storage = _DummyStorage()
        with pytest.raises(NotImplementedError, match="_DummyStorage"):
            await storage.get_metadata("test")

    def test_get_name_default(self) -> None:
        storage = _DummyStorage()
        assert storage.get_name() == "_DummyStorage"

    def test_get_description_default(self) -> None:
        storage = _DummyStorage()
        assert "Concrete storage" in storage.get_description()

    @pytest.mark.asyncio
    async def test_initialize_noop(self) -> None:
        storage = _DummyStorage()
        await storage.initialize()  # Should not raise

    @pytest.mark.asyncio
    async def test_shutdown_noop(self) -> None:
        storage = _DummyStorage()
        await storage.shutdown()  # Should not raise


# ── MinIOStorage additional coverage ─────────────────────────


class TestMinIOStorageAdditional:
    def test_encryption_init_vault_not_configured(self) -> None:
        from odg_core.storage.minio_storage import MinIOStorage

        mock_vault = MagicMock()
        mock_vault.is_configured = False

        with patch("odg_core.vault.client.VaultClient", return_value=mock_vault):
            storage = MinIOStorage(
                endpoint="minio:9000",
                access_key="key",
                secret_key="secret",
                bucket="b",
                encrypt=True,
            )
        assert storage._encrypt is False

    def test_encryption_init_vault_exception(self) -> None:
        from odg_core.storage.minio_storage import MinIOStorage

        with patch("odg_core.vault.client.VaultClient", side_effect=Exception("Vault down")):
            storage = MinIOStorage(
                endpoint="minio:9000",
                access_key="key",
                secret_key="secret",
                bucket="b",
                encrypt=True,
            )
        assert storage._encrypt is False

    def test_get_client_creates_new(self) -> None:
        from odg_core.storage.minio_storage import MinIOStorage

        storage = MinIOStorage(
            endpoint="minio:9000",
            access_key="key",
            secret_key="secret",
            bucket="b",
        )

        mock_minio_cls = MagicMock()
        mock_client = MagicMock()
        mock_minio_cls.return_value = mock_client
        mock_client.bucket_exists.return_value = True

        with patch.dict(sys.modules, {"minio": MagicMock(Minio=mock_minio_cls)}):
            client = storage._get_client()

        assert client is mock_client

    def test_get_client_creates_bucket(self) -> None:
        from odg_core.storage.minio_storage import MinIOStorage

        storage = MinIOStorage(
            endpoint="minio:9000",
            access_key="key",
            secret_key="secret",
            bucket="new-bucket",
        )

        mock_minio_cls = MagicMock()
        mock_client = MagicMock()
        mock_minio_cls.return_value = mock_client
        mock_client.bucket_exists.return_value = False

        with patch.dict(sys.modules, {"minio": MagicMock(Minio=mock_minio_cls)}):
            storage._get_client()

        mock_client.make_bucket.assert_called_once_with("new-bucket")

    def test_encrypt_error_raises(self) -> None:
        from odg_core.storage.minio_storage import MinIOStorage

        storage = MinIOStorage(
            endpoint="minio:9000",
            access_key="key",
            secret_key="secret",
            bucket="b",
        )
        storage._encrypt = True
        mock_vault = MagicMock()
        mock_vault.transit_encrypt.side_effect = Exception("Encryption failed")
        storage._vault_client = mock_vault

        with pytest.raises(Exception, match="Encryption failed"):
            storage._encrypt_data(b"data")

    def test_decrypt_error_raises(self) -> None:
        from odg_core.storage.minio_storage import MinIOStorage

        storage = MinIOStorage(
            endpoint="minio:9000",
            access_key="key",
            secret_key="secret",
            bucket="b",
        )
        storage._encrypt = True
        mock_vault = MagicMock()
        mock_vault.transit_decrypt.side_effect = Exception("Decryption failed")
        storage._vault_client = mock_vault

        with pytest.raises(Exception, match="Decryption failed"):
            storage._decrypt_data(b"cipher")

    @pytest.mark.asyncio
    async def test_read_not_found_general_exception(self) -> None:
        from odg_core.storage.minio_storage import MinIOStorage

        storage = MinIOStorage(
            endpoint="minio:9000",
            access_key="key",
            secret_key="secret",
            bucket="b",
        )
        mock_client = MagicMock()
        mock_client.get_object.side_effect = Exception("General error")
        storage._client = mock_client

        with pytest.raises(Exception, match="General error"):
            await storage.read("path")

    @pytest.mark.asyncio
    async def test_delete_general_exception(self) -> None:
        from odg_core.storage.minio_storage import MinIOStorage

        storage = MinIOStorage(
            endpoint="minio:9000",
            access_key="key",
            secret_key="secret",
            bucket="b",
        )
        mock_client = MagicMock()
        mock_client.remove_object.side_effect = Exception("General error")
        storage._client = mock_client

        with pytest.raises(Exception, match="General error"):
            await storage.delete("path")

    @pytest.mark.asyncio
    async def test_get_metadata_general_exception(self) -> None:
        from odg_core.storage.minio_storage import MinIOStorage

        storage = MinIOStorage(
            endpoint="minio:9000",
            access_key="key",
            secret_key="secret",
            bucket="b",
        )
        mock_client = MagicMock()
        mock_client.stat_object.side_effect = Exception("General error")
        storage._client = mock_client

        with pytest.raises(Exception, match="General error"):
            await storage.get_metadata("path")


# ── CouchDB additional coverage ──────────────────────────────


class TestCouchDBClientCoverage:
    def _make_client(self) -> Any:
        from odg_core.nosql import couchdb_client

        mock_couchdb = MagicMock()
        original = couchdb_client._couchdb_module  # type: ignore[attr-defined]
        couchdb_client._couchdb_module = mock_couchdb  # type: ignore[attr-defined]
        try:
            client = couchdb_client.CouchDBClient(url="http://localhost:5984", username="admin", password="admin")
        finally:
            couchdb_client._couchdb_module = original  # type: ignore[attr-defined]
        return client, mock_couchdb

    def test_query_view(self) -> None:
        client, _mock_couchdb = self._make_client()
        mock_server = MagicMock()
        client._server = mock_server
        client._connected = True

        # DB exists
        mock_server.__contains__ = MagicMock(return_value=True)
        mock_db = MagicMock()
        mock_server.__getitem__ = MagicMock(return_value=mock_db)

        mock_row = MagicMock()
        mock_row.id = "doc1"
        mock_row.key = "sklearn"
        mock_row.value = {"accuracy": 0.95}
        mock_db.view.return_value = [mock_row]

        results = client.query_view("model_registry", "models", "by_framework", key="sklearn")
        assert len(results) == 1
        assert results[0]["id"] == "doc1"

    def test_query_view_db_not_found(self) -> None:
        client, _ = self._make_client()
        mock_server = MagicMock()
        client._server = mock_server
        client._connected = True
        mock_server.__contains__ = MagicMock(return_value=False)

        results = client.query_view("nonexistent", "design", "view")
        assert results == []

    def test_query_view_exception(self) -> None:
        client, _ = self._make_client()
        mock_server = MagicMock()
        client._server = mock_server
        client._connected = True
        mock_server.__contains__ = MagicMock(return_value=True)
        mock_db = MagicMock()
        mock_server.__getitem__ = MagicMock(return_value=mock_db)
        mock_db.view.side_effect = Exception("View error")

        results = client.query_view("db", "design", "view")
        assert results == []

    def test_find(self) -> None:
        client, _ = self._make_client()
        mock_server = MagicMock()
        client._server = mock_server
        client._connected = True
        mock_server.__contains__ = MagicMock(return_value=True)

        mock_response = MagicMock()
        mock_response.json.return_value = {"docs": [{"_id": "doc1", "name": "test"}]}

        with patch("requests.post", return_value=mock_response):
            results = client.find("db", {"name": "test"})
            assert len(results) == 1

    def test_get_document_revisions(self) -> None:
        client, _ = self._make_client()
        mock_server = MagicMock()
        client._server = mock_server
        client._connected = True

        mock_db = MagicMock()
        mock_server.__getitem__ = MagicMock(return_value=mock_db)
        mock_db.__contains__ = MagicMock(return_value=True)
        mock_db.get.return_value = {
            "_revs_info": [
                {"rev": "3-abc", "status": "available"},
                {"rev": "2-def", "status": "available"},
                {"rev": "1-ghi", "status": "deleted"},
            ]
        }

        revs = client.get_document_revisions("db", "doc1")
        assert len(revs) == 2
        assert "3-abc" in revs

    def test_get_document_revisions_not_found(self) -> None:
        client, _ = self._make_client()
        mock_server = MagicMock()
        client._server = mock_server
        client._connected = True

        mock_db = MagicMock()
        mock_server.__getitem__ = MagicMock(return_value=mock_db)
        mock_db.__contains__ = MagicMock(return_value=False)

        revs = client.get_document_revisions("db", "missing")
        assert revs == []

    def test_get_document_revision(self) -> None:
        client, _ = self._make_client()
        mock_server = MagicMock()
        client._server = mock_server
        client._connected = True

        mock_db = MagicMock()
        mock_server.__getitem__ = MagicMock(return_value=mock_db)
        mock_db.get.return_value = {"_id": "doc1", "_rev": "2-abc", "data": "test"}

        doc = client.get_document_revision("db", "doc1", "2-abc")
        assert doc is not None
        assert doc["data"] == "test"

    def test_get_document_revision_not_found(self) -> None:
        client, _ = self._make_client()
        mock_server = MagicMock()
        client._server = mock_server
        client._connected = True

        mock_db = MagicMock()
        mock_server.__getitem__ = MagicMock(return_value=mock_db)
        mock_db.get.side_effect = Exception("Not found")

        doc = client.get_document_revision("db", "doc1", "1-xyz")
        assert doc is None


# ── MaterializationTracker additional coverage ────────────────


class TestMaterializationTrackerCoverage:
    def test_validate_feature_freshness_no_history(self) -> None:
        from odg_core.feast.materialization_tracker import MaterializationTracker

        mock_store = MagicMock()
        tracker = MaterializationTracker(mock_store)

        with patch.object(tracker, "get_materialization_history", return_value=[]):
            result = tracker.validate_feature_freshness("customer_features")

        assert result["is_fresh"] is False
        assert "No materialization history" in result["reason"]

    def test_validate_feature_freshness_fresh(self) -> None:
        from datetime import UTC, datetime

        from odg_core.feast.materialization_tracker import MaterializationTracker

        mock_store = MagicMock()
        tracker = MaterializationTracker(mock_store)

        recent_time = datetime.now(UTC).isoformat()
        with patch.object(
            tracker,
            "get_materialization_history",
            return_value=[
                {"materialization_time": recent_time, "source_pipeline_id": "p1", "source_pipeline_version": 1}
            ],
        ):
            result = tracker.validate_feature_freshness("customer_features", max_age_hours=24)

        assert result["is_fresh"] is True
        assert result["age_hours"] < 1

    def test_validate_feature_freshness_stale(self) -> None:
        from datetime import UTC, datetime, timedelta

        from odg_core.feast.materialization_tracker import MaterializationTracker

        mock_store = MagicMock()
        tracker = MaterializationTracker(mock_store)

        old_time = (datetime.now(UTC) - timedelta(hours=48)).isoformat()
        with patch.object(
            tracker,
            "get_materialization_history",
            return_value=[{"materialization_time": old_time, "source_pipeline_id": "p1", "source_pipeline_version": 1}],
        ):
            result = tracker.validate_feature_freshness("customer_features", max_age_hours=24)

        assert result["is_fresh"] is False
        assert result["age_hours"] > 24

    def test_get_materialization_history_db_error(self) -> None:
        from odg_core.feast.materialization_tracker import MaterializationTracker

        mock_store = MagicMock()
        tracker = MaterializationTracker(mock_store)

        result = tracker.get_materialization_history("customer_features")
        assert result == []

    def test_track_feast_materialization(self) -> None:
        from odg_core.feast.materialization_tracker import track_feast_materialization

        mock_store = MagicMock()

        with patch(
            "odg_core.feast.materialization_tracker.MaterializationTracker.track_materialization",
            return_value={"run_id": "test"},
        ):
            result = track_feast_materialization(mock_store, "customer_features")
        assert result == {"run_id": "test"}
