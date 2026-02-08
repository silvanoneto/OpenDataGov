"""OpenLineage event emitter (ADR-060).

Publishes lineage events to Kafka for consumption by the DataHub ingester.
Falls back to logging if Kafka is unavailable.
"""

from __future__ import annotations

import json
import logging
import uuid

from odg_core.lineage.models import LineageDataset, LineageJob, LineageRunEvent

logger = logging.getLogger(__name__)

_TOPIC = "openlineage.events"


def emit_lineage_event(
    *,
    job_name: str,
    inputs: list[dict[str, str]],
    outputs: list[dict[str, str]],
    event_type: str = "COMPLETE",
) -> LineageRunEvent:
    """Create and emit an OpenLineage run event.

    Args:
        job_name: Name of the job (e.g., "promotion.bronze_to_silver").
        inputs: List of dicts with 'namespace' and 'name' keys.
        outputs: List of dicts with 'namespace' and 'name' keys.
        event_type: One of START, RUNNING, COMPLETE, FAIL, ABORT.

    Returns:
        The created LineageRunEvent.
    """
    event = LineageRunEvent(
        event_type=event_type,
        run={"runId": str(uuid.uuid4())},
        job=LineageJob(name=job_name),
        inputs=[LineageDataset(**inp) for inp in inputs],
        outputs=[LineageDataset(**out) for out in outputs],
    )

    # Log the event (Kafka integration will be added when aiokafka is wired)
    logger.info(
        "OpenLineage event: %s %s (%d inputs, %d outputs)",
        event.event_type,
        event.job.name,
        len(event.inputs),
        len(event.outputs),
    )
    logger.debug("OpenLineage payload: %s", json.dumps(event.model_dump(), default=str))

    return event
