"""Protocol interfaces for lakehouse agent storage backends."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from odg_core.enums import MedallionLayer


def bucket_name(layer: MedallionLayer, domain_id: str) -> str:
    """Return the canonical bucket name for a layer and domain."""
    return f"odg-{layer.value}-{domain_id}"


class BucketManager(Protocol):
    """Abstract storage backend for object operations.

    Any class that implements ``get_object`` and ``upload_object`` satisfies
    this protocol via structural subtyping — no explicit inheritance needed.
    """

    async def get_object(self, bucket: str, key: str) -> bytes: ...

    async def upload_object(
        self,
        bucket: str,
        key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> dict[str, Any]: ...
