"""MinIO bucket management and object operations."""

from __future__ import annotations

import asyncio
import io
from functools import partial
from typing import Any

from minio import Minio
from minio.commonconfig import ENABLED
from minio.versioningconfig import VersioningConfig
from odg_core.enums import MedallionLayer
from odg_core.settings import MinIOSettings

from lakehouse_agent.protocols import bucket_name as _bucket_name

_MEDALLION_LAYERS: list[MedallionLayer] = [
    MedallionLayer.BRONZE,
    MedallionLayer.SILVER,
    MedallionLayer.GOLD,
    MedallionLayer.PLATINUM,
]


class MinIOBucketManager:
    """Manages MinIO buckets following the medallion architecture.

    Each domain receives four buckets named ``odg-{layer}-{domain_id}``,
    one for every medallion layer (bronze, silver, gold, platinum).
    All buckets are created with versioning enabled.
    """

    def __init__(self, settings: MinIOSettings | None = None) -> None:
        self._settings = settings or MinIOSettings()
        self._client = Minio(
            endpoint=self._settings.endpoint,
            access_key=self._settings.access_key,
            secret_key=self._settings.secret_key,
            secure=self._settings.secure,
        )

    @staticmethod
    def bucket_name(layer: MedallionLayer, domain_id: str) -> str:
        """Return the canonical bucket name for a layer and domain."""
        return _bucket_name(layer, domain_id)

    # ── Bucket operations ────────────────────────────────────

    async def ensure_buckets(self, domain_id: str) -> list[str]:
        """Create medallion-layer buckets for *domain_id* with versioning.

        Returns the list of bucket names that were created or already existed.
        """
        loop = asyncio.get_running_loop()
        created: list[str] = []

        for layer in _MEDALLION_LAYERS:
            name = self.bucket_name(layer, domain_id)

            exists = await loop.run_in_executor(None, self._client.bucket_exists, name)
            if not exists:
                await loop.run_in_executor(None, self._client.make_bucket, name)

            # Enable versioning regardless (idempotent).
            config = VersioningConfig(ENABLED)
            await loop.run_in_executor(None, self._client.set_bucket_versioning, name, config)
            created.append(name)

        return created

    async def list_buckets(self) -> list[dict[str, str]]:
        """Return all buckets visible to the configured credentials."""
        loop = asyncio.get_running_loop()
        buckets = await loop.run_in_executor(None, self._client.list_buckets)
        return [
            {
                "name": b.name,
                "creation_date": b.creation_date.isoformat() if b.creation_date else "",
            }
            for b in buckets
        ]

    async def get_bucket_policy(self, bucket_name: str) -> str:
        """Return the JSON policy string attached to *bucket_name*."""
        loop = asyncio.get_running_loop()
        policy: str = await loop.run_in_executor(None, self._client.get_bucket_policy, bucket_name)
        return policy

    # ── Object operations ────────────────────────────────────

    async def upload_object(
        self,
        bucket: str,
        key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> dict[str, Any]:
        """Upload *data* as an object to *bucket/key*.

        Returns a dict with ``bucket``, ``key``, ``etag``, and ``version_id``.
        """
        loop = asyncio.get_running_loop()
        stream = io.BytesIO(data)
        length = len(data)

        result = await loop.run_in_executor(
            None,
            partial(
                self._client.put_object,
                bucket_name=bucket,
                object_name=key,
                data=stream,
                length=length,
                content_type=content_type,
            ),
        )
        return {
            "bucket": result.bucket_name,
            "key": result.object_name,
            "etag": result.etag,
            "version_id": result.version_id,
        }

    async def get_object(self, bucket: str, key: str) -> bytes:
        """Download an object from *bucket/key* and return its bytes."""
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None,
            partial(self._client.get_object, bucket_name=bucket, object_name=key),
        )
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()
