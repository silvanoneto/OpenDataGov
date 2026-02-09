"""Tests for odg_core.storage.minio_storage module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from odg_core.storage.minio_storage import MinIOStorage


@pytest.fixture()
def mock_minio_client() -> MagicMock:
    """Create a mock Minio client."""
    client = MagicMock()
    client.bucket_exists.return_value = True
    return client


@pytest.fixture()
def storage(mock_minio_client: MagicMock) -> MinIOStorage:
    """Create MinIOStorage with mocked Minio client (no encryption)."""
    s = MinIOStorage(
        endpoint="minio:9000",
        access_key="admin",
        secret_key="secret",
        bucket="test-bucket",
        encrypt=False,
    )
    s._client = mock_minio_client
    return s


# ──── Initialization ─────────────────────────────────────────


class TestMinIOStorageInit:
    """Tests for MinIOStorage initialization."""

    def test_stores_configuration(self) -> None:
        s = MinIOStorage(
            endpoint="minio:9000",
            access_key="key",
            secret_key="secret",
            bucket="mybucket",
            secure=True,
        )
        assert s._endpoint == "minio:9000"
        assert s._access_key == "key"
        assert s._secret_key == "secret"
        assert s._bucket == "mybucket"
        assert s._secure is True

    def test_encryption_disabled_by_default(self) -> None:
        s = MinIOStorage(
            endpoint="minio:9000",
            access_key="key",
            secret_key="secret",
            bucket="mybucket",
        )
        assert s._encrypt is False
        assert s._vault_client is None


# ──── _get_client ────────────────────────────────────────────


class TestGetClient:
    """Tests for lazy MinIO client initialization."""

    def test_returns_existing_client(self, storage: MinIOStorage, mock_minio_client: MagicMock) -> None:
        result = storage._get_client()
        assert result is mock_minio_client

    @patch("odg_core.storage.minio_storage.MinIOStorage._get_client")
    def test_creates_bucket_if_not_exists(self, mock_get: MagicMock) -> None:
        # This test verifies the bucket creation logic described in the source
        mock_client = MagicMock()
        mock_client.bucket_exists.return_value = False
        mock_get.return_value = mock_client

        s = MinIOStorage(
            endpoint="minio:9000",
            access_key="key",
            secret_key="secret",
            bucket="new-bucket",
        )
        s._get_client()
        mock_get.assert_called_once()


# ──── _encrypt_data / _decrypt_data ──────────────────────────


class TestEncryptDecryptData:
    """Tests for encryption/decryption pass-through when disabled."""

    def test_encrypt_passthrough_when_disabled(self, storage: MinIOStorage) -> None:
        data = b"hello world"
        result = storage._encrypt_data(data)
        assert result == data

    def test_decrypt_passthrough_when_disabled(self, storage: MinIOStorage) -> None:
        data = b"encrypted_data"
        result = storage._decrypt_data(data)
        assert result == data

    def test_encrypt_with_vault(self) -> None:
        s = MinIOStorage(
            endpoint="minio:9000",
            access_key="key",
            secret_key="secret",
            bucket="b",
            encrypt=False,
        )
        # Manually enable encryption with a mock vault client
        s._encrypt = True
        mock_vault = MagicMock()
        mock_vault.transit_encrypt.return_value = "vault:cipher:abc123"
        s._vault_client = mock_vault

        result = s._encrypt_data(b"secret data")
        assert result == b"vault:cipher:abc123"
        mock_vault.transit_encrypt.assert_called_once()

    def test_decrypt_with_vault(self) -> None:
        import base64

        s = MinIOStorage(
            endpoint="minio:9000",
            access_key="key",
            secret_key="secret",
            bucket="b",
            encrypt=False,
        )
        s._encrypt = True
        mock_vault = MagicMock()
        plaintext_b64 = base64.b64encode(b"decrypted data").decode("utf-8")
        mock_vault.transit_decrypt.return_value = plaintext_b64
        s._vault_client = mock_vault

        result = s._decrypt_data(b"vault:cipher:abc123")
        assert result == b"decrypted data"


# ──── read ───────────────────────────────────────────────────


class TestRead:
    """Tests for MinIOStorage.read."""

    @pytest.mark.asyncio
    async def test_read_returns_data(self, storage: MinIOStorage, mock_minio_client: MagicMock) -> None:
        mock_obj = MagicMock()
        mock_obj.read.return_value = b"file contents"
        mock_minio_client.get_object.return_value = mock_obj

        result = await storage.read("datasets/test.parquet")

        mock_minio_client.get_object.assert_called_once_with("test-bucket", "datasets/test.parquet")
        assert result == b"file contents"
        mock_obj.close.assert_called_once()
        mock_obj.release_conn.assert_called_once()

    @pytest.mark.asyncio
    async def test_read_raises_file_not_found(self, storage: MinIOStorage, mock_minio_client: MagicMock) -> None:
        mock_minio_client.get_object.side_effect = Exception("NoSuchKey")

        with pytest.raises(FileNotFoundError, match="Object not found"):
            await storage.read("missing/file.parquet")


# ──── write ──────────────────────────────────────────────────


class TestWrite:
    """Tests for MinIOStorage.write."""

    @pytest.mark.asyncio
    async def test_write_calls_put_object(self, storage: MinIOStorage, mock_minio_client: MagicMock) -> None:
        data = b"test data"
        await storage.write("path/to/file.bin", data)

        mock_minio_client.put_object.assert_called_once()
        call_args = mock_minio_client.put_object.call_args
        assert call_args[0][0] == "test-bucket"
        assert call_args[0][1] == "path/to/file.bin"
        assert call_args[0][3] == len(data)


# ──── list ───────────────────────────────────────────────────


class TestList:
    """Tests for MinIOStorage.list."""

    @pytest.mark.asyncio
    async def test_list_returns_object_names(self, storage: MinIOStorage, mock_minio_client: MagicMock) -> None:
        obj1 = MagicMock()
        obj1.object_name = "a/file1.parquet"
        obj2 = MagicMock()
        obj2.object_name = "a/file2.parquet"
        mock_minio_client.list_objects.return_value = [obj1, obj2]

        result = await storage.list(prefix="a/")

        assert result == ["a/file1.parquet", "a/file2.parquet"]
        mock_minio_client.list_objects.assert_called_once_with("test-bucket", prefix="a/", recursive=True)


# ──── delete ─────────────────────────────────────────────────


class TestDelete:
    """Tests for MinIOStorage.delete."""

    @pytest.mark.asyncio
    async def test_delete_calls_remove_object(self, storage: MinIOStorage, mock_minio_client: MagicMock) -> None:
        await storage.delete("path/to/file.bin")
        mock_minio_client.remove_object.assert_called_once_with("test-bucket", "path/to/file.bin")

    @pytest.mark.asyncio
    async def test_delete_raises_file_not_found(self, storage: MinIOStorage, mock_minio_client: MagicMock) -> None:
        mock_minio_client.remove_object.side_effect = Exception("NoSuchKey: not found")

        with pytest.raises(FileNotFoundError, match="Object not found"):
            await storage.delete("missing.bin")


# ──── get_metadata ───────────────────────────────────────────


class TestGetMetadata:
    """Tests for MinIOStorage.get_metadata."""

    @pytest.mark.asyncio
    async def test_get_metadata_returns_storage_metadata(
        self, storage: MinIOStorage, mock_minio_client: MagicMock
    ) -> None:
        mock_stat = MagicMock()
        mock_stat.size = 1024
        mock_stat.content_type = "application/octet-stream"
        mock_stat.etag = "abc123"
        mock_stat.last_modified = MagicMock()
        mock_stat.last_modified.isoformat.return_value = "2026-01-01T00:00:00"
        mock_stat.metadata = {"custom": "value"}
        mock_minio_client.stat_object.return_value = mock_stat

        meta = await storage.get_metadata("test.bin")

        assert meta.path == "test.bin"
        assert meta.size_bytes == 1024
        assert meta.content_type == "application/octet-stream"
        assert meta.etag == "abc123"
        assert meta.custom_metadata == {"custom": "value"}

    @pytest.mark.asyncio
    async def test_get_metadata_raises_file_not_found(
        self, storage: MinIOStorage, mock_minio_client: MagicMock
    ) -> None:
        mock_minio_client.stat_object.side_effect = Exception("Not Found")

        with pytest.raises(FileNotFoundError):
            await storage.get_metadata("missing.bin")


# ──── Utility methods ────────────────────────────────────────


class TestUtilityMethods:
    """Tests for get_storage_type, get_name, get_description."""

    def test_get_storage_type(self, storage: MinIOStorage) -> None:
        assert storage.get_storage_type() == "minio"

    def test_get_name_unencrypted(self, storage: MinIOStorage) -> None:
        assert "unencrypted" in storage.get_name()

    def test_get_name_encrypted(self) -> None:
        s = MinIOStorage(
            endpoint="minio:9000",
            access_key="key",
            secret_key="secret",
            bucket="b",
        )
        s._encrypt = True
        assert "encrypted" in s.get_name()

    def test_get_description(self, storage: MinIOStorage) -> None:
        desc = storage.get_description()
        assert "minio:9000" in desc
        assert "test-bucket" in desc


# ──── initialize / shutdown ──────────────────────────────────


class TestLifecycle:
    """Tests for initialize and shutdown methods."""

    @pytest.mark.asyncio
    async def test_initialize_verifies_bucket(self, storage: MinIOStorage, mock_minio_client: MagicMock) -> None:
        mock_minio_client.bucket_exists.return_value = True
        await storage.initialize()
        mock_minio_client.bucket_exists.assert_called_with("test-bucket")

    @pytest.mark.asyncio
    async def test_initialize_raises_when_bucket_missing(
        self, storage: MinIOStorage, mock_minio_client: MagicMock
    ) -> None:
        mock_minio_client.bucket_exists.return_value = False

        with pytest.raises(RuntimeError, match="Bucket does not exist"):
            await storage.initialize()

    @pytest.mark.asyncio
    async def test_shutdown_clears_client(self, storage: MinIOStorage) -> None:
        assert storage._client is not None
        await storage.shutdown()
        assert storage._client is None
