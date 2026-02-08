"""NATS JetStream event publisher for governance events."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

import nats

if TYPE_CHECKING:
    from nats.aio.client import Client as NATSClient
    from nats.js.client import JetStreamContext

logger = logging.getLogger(__name__)

# NATS JetStream subjects
SUBJECTS = {
    "decision_created": "governance.decisions.created",
    "decision_finalized": "governance.decisions.finalized",
    "approval_requested": "governance.approvals.requested",
    "approval_cast": "governance.approvals.cast",
    "veto_exercised": "governance.veto.exercised",
    "veto_overridden": "governance.veto.overridden",
}

STREAM_NAME = "GOVERNANCE"


class NATSPublisher:
    """Publishes governance events to NATS JetStream."""

    def __init__(self) -> None:
        self._nc: NATSClient | None = None
        self._js: JetStreamContext | None = None

    async def connect(self, nats_url: str) -> None:
        """Connect to NATS and set up JetStream stream."""
        try:
            self._nc = await nats.connect(nats_url)
            self._js = self._nc.jetstream()

            # Create or update stream
            await self._js.add_stream(
                name=STREAM_NAME,
                subjects=["governance.>"],
                retention="limits",
                max_msgs=100_000,
                max_age=7 * 24 * 60 * 60 * 1_000_000_000,  # 7 days in nanoseconds
            )
            logger.info("Connected to NATS JetStream at %s", nats_url)
        except Exception:
            logger.warning("Failed to connect to NATS at %s, events will be skipped", nats_url, exc_info=True)
            self._nc = None
            self._js = None

    async def disconnect(self) -> None:
        """Disconnect from NATS."""
        if self._nc and not self._nc.is_closed:
            await self._nc.close()
            logger.info("Disconnected from NATS")

    async def publish(self, subject_key: str, payload: dict[str, Any]) -> None:
        """Publish an event to NATS JetStream.

        Silently skips if not connected (graceful degradation).
        """
        if self._js is None:
            return

        subject = SUBJECTS.get(subject_key)
        if subject is None:
            logger.warning("Unknown event subject: %s", subject_key)
            return

        try:
            from odg_core.telemetry.context import get_trace_headers

            trace_headers = get_trace_headers()
            if trace_headers:
                payload.setdefault("_trace", trace_headers)

            data = json.dumps(payload, default=str).encode()
            await self._js.publish(subject, data)
            logger.debug("Published event to %s", subject)
        except Exception:
            logger.warning("Failed to publish event to %s", subject, exc_info=True)

    @property
    def is_connected(self) -> bool:
        return self._nc is not None and not self._nc.is_closed
