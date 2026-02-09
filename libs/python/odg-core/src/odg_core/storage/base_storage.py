"""Base class for storage backends (ADR-131).

All storage backends must extend BaseStorage and implement read/write operations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel, Field


class StorageMetadata(BaseModel):
    """Metadata for stored objects."""

    path: str
    size_bytes: int | None = None
    content_type: str | None = None
    etag: str | None = None
    last_modified: str | None = None
    custom_metadata: dict[str, str] = Field(default_factory=dict)


class BaseStorage(ABC):
    """Abstract base class for storage backends.

    Implements the plugin pattern for extensible storage systems.
    Supports object storage (S3, MinIO), filesystems, databases, etc.

    Example:
        class MinIOStorage(BaseStorage):
            def __init__(self, endpoint: str, access_key: str, secret_key: str):
                self.client = Minio(endpoint, access_key, secret_key)

            async def read(self, path: str) -> bytes:
                obj = self.client.get_object("my-bucket", path)
                return obj.read()

            async def write(self, path: str, data: bytes) -> None:
                self.client.put_object("my-bucket", path, io.BytesIO(data), len(data))

            async def list(self, prefix: str) -> list[str]:
                return [obj.object_name for obj in self.client.list_objects("my-bucket", prefix=prefix)]

            async def delete(self, path: str) -> None:
                self.client.remove_object("my-bucket", path)

            def get_storage_type(self) -> str:
                return "minio"
    """

    @abstractmethod
    async def read(self, path: str) -> bytes:
        """Read data from storage.

        Args:
            path: Object path/key

        Returns:
            Raw bytes data

        Raises:
            FileNotFoundError: If path doesn't exist
            Exception: If read fails
        """
        ...

    @abstractmethod
    async def write(self, path: str, data: bytes) -> None:
        """Write data to storage.

        Args:
            path: Object path/key
            data: Raw bytes to write

        Raises:
            Exception: If write fails
        """
        ...

    @abstractmethod
    async def list(self, prefix: str = "") -> list[str]:
        """List objects with given prefix.

        Args:
            prefix: Path prefix to filter (empty = list all)

        Returns:
            List of object paths

        Raises:
            Exception: If list fails
        """
        ...

    @abstractmethod
    async def delete(self, path: str) -> None:
        """Delete object from storage.

        Args:
            path: Object path/key to delete

        Raises:
            FileNotFoundError: If path doesn't exist
            Exception: If delete fails
        """
        ...

    @abstractmethod
    def get_storage_type(self) -> str:
        """Return the storage backend type (e.g., 's3', 'minio', 'filesystem')."""
        ...

    async def exists(self, path: str) -> bool:
        """Check if object exists.

        Args:
            path: Object path/key

        Returns:
            True if exists, False otherwise
        """
        try:
            await self.get_metadata(path)
            return True
        except FileNotFoundError:
            return False
        except Exception:
            return False

    async def get_metadata(self, path: str) -> StorageMetadata:
        """Get object metadata.

        Args:
            path: Object path/key

        Returns:
            StorageMetadata with object information

        Raises:
            FileNotFoundError: If path doesn't exist
            NotImplementedError: If backend doesn't support metadata
        """
        msg = f"{self.__class__.__name__} doesn't implement get_metadata()"
        raise NotImplementedError(msg)

    def get_name(self) -> str:
        """Return human-readable backend name (defaults to class name)."""
        return self.__class__.__name__

    def get_description(self) -> str:
        """Return backend description (defaults to docstring)."""
        return (self.__class__.__doc__ or "").strip()

    async def initialize(self) -> None:  # noqa: B027
        """Initialize storage backend."""

    async def shutdown(self) -> None:  # noqa: B027
        """Gracefully shutdown backend."""
