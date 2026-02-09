"""Kubernetes admission webhooks for governance enforcement."""

from governance_engine.webhooks.kserve import router as kserve_webhook_router

__all__ = ["kserve_webhook_router"]
