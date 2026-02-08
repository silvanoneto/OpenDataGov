"""MinIO Server-Side Encryption via Vault Transit (ADR-073).

Provides SSE-KMS integration between MinIO and Vault Transit engine
for encryption-at-rest of lakehouse data.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from odg_core.vault.client import VaultClient

logger = logging.getLogger(__name__)

DEFAULT_TRANSIT_KEY = "opendatagov-minio"


def ensure_transit_key(vault: VaultClient, key_name: str = DEFAULT_TRANSIT_KEY) -> bool:
    """Ensure the transit encryption key exists in Vault.

    Returns True if key exists or was created, False on failure.
    """
    try:
        client = vault._ensure_client()
        try:
            client.secrets.transit.read_key(name=key_name)
            logger.debug("Transit key '%s' already exists", key_name)
        except Exception:
            client.secrets.transit.create_key(name=key_name, key_type="aes256-gcm96")
            logger.info("Created transit key '%s'", key_name)
    except Exception:
        logger.warning("Failed to ensure transit key '%s'", key_name, exc_info=True)
        return False
    else:
        return True


def get_sse_headers(key_name: str = DEFAULT_TRANSIT_KEY) -> dict[str, Any]:
    """Return MinIO SSE-KMS headers for server-side encryption.

    Usage with minio-py:
        headers = get_sse_headers()
        client.put_object(bucket, key, data, metadata=headers)
    """
    return {
        "x-amz-server-side-encryption": "aws:kms",
        "x-amz-server-side-encryption-aws-kms-key-id": key_name,
    }
