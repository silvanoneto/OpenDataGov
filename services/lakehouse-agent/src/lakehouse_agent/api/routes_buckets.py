"""Bucket management endpoints: /api/v1/buckets."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from lakehouse_agent.minio_client import MinIOBucketManager

router = APIRouter(prefix="/api/v1/buckets", tags=["buckets"])


def _get_bucket_manager(request: Request) -> MinIOBucketManager:
    """Retrieve the ``MinIOBucketManager`` stored on the app state."""
    return request.app.state.bucket_manager  # type: ignore[no-any-return]


@router.post("/{domain_id}", status_code=201, responses={500: {"description": "Bucket creation failed"}})
async def create_buckets_for_domain(
    domain_id: str,
    request: Request,
) -> dict[str, list[str]]:
    """Create medallion-layer buckets for *domain_id* with versioning."""
    manager = _get_bucket_manager(request)
    try:
        buckets = await manager.ensure_buckets(domain_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"buckets": buckets}


@router.get("", responses={500: {"description": "Failed to list buckets"}})
async def list_all_buckets(
    request: Request,
) -> dict[str, list[dict[str, str]]]:
    """List every bucket visible to the configured credentials."""
    manager = _get_bucket_manager(request)
    try:
        buckets = await manager.list_buckets()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"buckets": buckets}
