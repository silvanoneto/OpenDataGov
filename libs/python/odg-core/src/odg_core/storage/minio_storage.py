"""MinIO storage backend with Vault Transit encryption (ADR-131, ADR-073).

Implements encrypted object storage using MinIO with Vault Transit engine
for encryption at rest.
"""

from __future__ import annotations

import base64
import io
import logging
from typing import TYPE_CHECKING

from odg_core.storage.base_storage import BaseStorage, StorageMetadata

if TYPE_CHECKING:
    from minio import Minio

logger = logging.getLogger(__name__)


class MinIOStorage(BaseStorage):
    """MinIO object storage with optional Vault Transit encryption.

    When encryption is enabled, all objects are encrypted with Vault Transit
    before being written to MinIO, and decrypted when read.

    Example:
        # Without encryption
        storage = MinIOStorage(
            endpoint="minio:9000",
            access_key="admin",
            secret_key="password",
            bucket="opendatagov",
        )

        # With Vault Transit encryption
        storage = MinIOStorage(
            endpoint="minio:9000",
            access_key="admin",
            secret_key="password",
            bucket="opendatagov",
            encrypt=True,
            vault_key="odg-minio-sse",
        )

        await storage.write("datasets/gold/customers.parquet", data)
        data = await storage.read("datasets/gold/customers.parquet")
    """

    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        secure: bool = False,
        encrypt: bool = False,
        vault_key: str = "odg-minio-sse",
    ) -> None:
        """Initialize MinIO storage backend.

        Args:
            endpoint: MinIO endpoint (e.g., "minio:9000")
            access_key: MinIO access key
            secret_key: MinIO secret key
            bucket: Bucket name
            secure: Use HTTPS (default: False)
            encrypt: Enable Vault Transit encryption (default: False)
            vault_key: Vault Transit key name (default: "odg-minio-sse")
        """
        self._endpoint = endpoint
        self._access_key = access_key
        self._secret_key = secret_key
        self._bucket = bucket
        self._secure = secure
        self._encrypt = encrypt
        self._vault_key = vault_key
        self._client: Minio | None = None
        self._vault_client = None

        if self._encrypt:
            try:
                from odg_core.vault.client import VaultClient

                self._vault_client = VaultClient()
                if not self._vault_client.is_configured:
                    logger.warning("Vault not configured, encryption will be disabled")
                    self._encrypt = False
                else:
                    logger.info("MinIO storage encryption enabled with Vault key: %s", self._vault_key)
            except Exception as e:
                logger.warning("Failed to initialize Vault client: %s. Encryption disabled.", e)
                self._encrypt = False

    def _get_client(self) -> Minio:
        """Lazily initialize MinIO client."""
        if self._client is not None:
            return self._client

        try:
            from minio import Minio
        except ImportError as e:
            msg = "minio package not installed (pip install minio)"
            raise RuntimeError(msg) from e

        self._client = Minio(
            self._endpoint,
            access_key=self._access_key,
            secret_key=self._secret_key,
            secure=self._secure,
        )

        # Ensure bucket exists
        if not self._client.bucket_exists(self._bucket):
            self._client.make_bucket(self._bucket)
            logger.info("Created MinIO bucket: %s", self._bucket)

        return self._client

    def _encrypt_data(self, data: bytes) -> bytes:
        """Encrypt data using Vault Transit if enabled."""
        if not self._encrypt or self._vault_client is None:
            return data

        try:
            plaintext_b64 = base64.b64encode(data).decode("utf-8")
            ciphertext = self._vault_client.transit_encrypt(self._vault_key, plaintext_b64)
            return ciphertext.encode("utf-8")
        except Exception as e:
            logger.error("Encryption failed: %s", e)
            raise

    def _decrypt_data(self, data: bytes) -> bytes:
        """Decrypt data using Vault Transit if enabled."""
        if not self._encrypt or self._vault_client is None:
            return data

        try:
            ciphertext = data.decode("utf-8")
            plaintext_b64 = self._vault_client.transit_decrypt(self._vault_key, ciphertext)
            return base64.b64decode(plaintext_b64)
        except Exception as e:
            logger.error("Decryption failed: %s", e)
            raise

    async def read(self, path: str) -> bytes:
        """Read object from MinIO (decrypts if encryption enabled)."""
        client = self._get_client()

        try:
            obj = client.get_object(self._bucket, path)
            data = obj.read()
            obj.close()
            obj.release_conn()

            # Decrypt if encryption is enabled
            return self._decrypt_data(data)

        except Exception as e:
            if "NoSuchKey" in str(e) or "Not Found" in str(e):
                raise FileNotFoundError(f"Object not found: {path}") from e
            raise

    async def write(self, path: str, data: bytes) -> None:
        """Write object to MinIO (encrypts if encryption enabled)."""
        client = self._get_client()

        # Encrypt if encryption is enabled
        encrypted_data = self._encrypt_data(data)

        client.put_object(
            self._bucket,
            path,
            io.BytesIO(encrypted_data),
            len(encrypted_data),
        )

    async def list(self, prefix: str = "") -> list[str]:
        """List objects in bucket with given prefix."""
        client = self._get_client()

        objects = client.list_objects(self._bucket, prefix=prefix, recursive=True)
        return [obj.object_name for obj in objects]

    async def delete(self, path: str) -> None:
        """Delete object from MinIO."""
        client = self._get_client()

        try:
            client.remove_object(self._bucket, path)
        except Exception as e:
            if "NoSuchKey" in str(e) or "Not Found" in str(e):
                raise FileNotFoundError(f"Object not found: {path}") from e
            raise

    async def get_metadata(self, path: str) -> StorageMetadata:
        """Get object metadata from MinIO."""
        client = self._get_client()

        try:
            stat = client.stat_object(self._bucket, path)

            return StorageMetadata(
                path=path,
                size_bytes=stat.size,
                content_type=stat.content_type,
                etag=stat.etag,
                last_modified=stat.last_modified.isoformat() if stat.last_modified else None,
                custom_metadata={str(k): str(v) for k, v in (stat.metadata or {}).items()},
            )
        except Exception as e:
            if "NoSuchKey" in str(e) or "Not Found" in str(e):
                raise FileNotFoundError(f"Object not found: {path}") from e
            raise

    def get_storage_type(self) -> str:
        """Return storage type identifier."""
        return "minio"

    def get_name(self) -> str:
        """Return human-readable storage name."""
        encryption_status = "encrypted" if self._encrypt else "unencrypted"
        return f"MinIO Storage ({encryption_status})"

    def get_description(self) -> str:
        """Return storage description."""
        return f"MinIO object storage at {self._endpoint} (bucket: {self._bucket})"

    async def initialize(self) -> None:
        """Initialize MinIO client and verify connectivity."""
        client = self._get_client()
        # Verify connectivity
        if not client.bucket_exists(self._bucket):
            msg = f"Bucket does not exist: {self._bucket}"
            raise RuntimeError(msg)
        logger.info("MinIO storage initialized successfully")

    async def shutdown(self) -> None:
        """Shutdown MinIO client."""
        # MinIO client doesn't require explicit shutdown
        self._client = None
        logger.info("MinIO storage shutdown")
