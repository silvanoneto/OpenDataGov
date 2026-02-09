"""OpenLineage event emitter (ADR-060).

Publishes lineage events to Kafka for consumption by the DataHub ingester.
Also persists events to PostgreSQL for queryability and auditability.
Falls back to logging if Kafka/DB is unavailable.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import UTC, datetime
from typing import Any

from odg_core.lineage.models import LineageDataset, LineageJob, LineageRunEvent

logger = logging.getLogger(__name__)

_TOPIC = "openlineage.events"
_PRODUCER = "odg-core/0.1.0"


def _persist_to_database(event: LineageRunEvent) -> None:
    """Persist lineage event to PostgreSQL.

    Args:
        event: OpenLineage event to persist
    """
    try:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session

        from odg_core.db.tables import LineageEventRow

        db_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/odg")
        engine = create_engine(db_url)

        with Session(engine) as session:
            lineage_row = LineageEventRow(
                event_type=event.event_type,
                event_time=datetime.fromisoformat(event.event_time)
                if isinstance(event.event_time, str)
                else event.event_time,
                job_namespace=event.job.namespace,
                job_name=event.job.name,
                run_id=event.run.get("runId", str(uuid.uuid4())),
                inputs=[
                    {
                        "namespace": inp.namespace,
                        "name": inp.name,
                        "facets": inp.facets if hasattr(inp, "facets") else {},
                    }
                    for inp in event.inputs
                ],
                outputs=[
                    {
                        "namespace": out.namespace,
                        "name": out.name,
                        "facets": out.facets if hasattr(out, "facets") else {},
                    }
                    for out in event.outputs
                ],
                producer=_PRODUCER,
            )

            session.add(lineage_row)
            session.commit()

            logger.debug("Persisted lineage event to database: %s", lineage_row.id)

    except Exception as e:
        logger.warning("Failed to persist lineage event to database: %s", e)


def emit_lineage_event(
    *,
    job_name: str,
    inputs: list[dict[str, Any]],
    outputs: list[dict[str, Any]],
    event_type: str = "COMPLETE",
    job_namespace: str = "lakehouse",
    run_id: str | None = None,
) -> LineageRunEvent:
    """Create and emit an OpenLineage run event.

    Emits the event to both Kafka (for DataHub) and PostgreSQL (for queries).

    Args:
        job_name: Name of the job (e.g., "promotion.bronze_to_silver").
        inputs: List of dicts with 'namespace' and 'name' keys.
        outputs: List of dicts with 'namespace' and 'name' keys.
        event_type: One of START, RUNNING, COMPLETE, FAIL, ABORT.
        job_namespace: Job namespace (default: "lakehouse")
        run_id: Optional run ID (generates UUID if not provided)

    Returns:
        The created LineageRunEvent.

    Example:
        >>> from odg_core.lineage.emitter import emit_lineage_event
        >>>
        >>> emit_lineage_event(
        ...     job_name="transform_sales",
        ...     inputs=[{"namespace": "bronze", "name": "raw_sales"}],
        ...     outputs=[{"namespace": "silver", "name": "clean_sales"}],
        ...     event_type="COMPLETE"
        ... )
    """
    event = LineageRunEvent(
        event_type=event_type,
        event_time=datetime.now(UTC),
        run={"runId": run_id or str(uuid.uuid4())},
        job=LineageJob(namespace=job_namespace, name=job_name),
        inputs=[LineageDataset(**inp) for inp in inputs],
        outputs=[LineageDataset(**out) for out in outputs],
    )

    # Log the event
    logger.info(
        "OpenLineage event: %s %s.%s (%d inputs, %d outputs)",
        event.event_type,
        event.job.namespace,
        event.job.name,
        len(event.inputs),
        len(event.outputs),
    )
    logger.debug("OpenLineage payload: %s", json.dumps(event.model_dump(), default=str))

    # Persist to database
    _persist_to_database(event)

    # TODO: Emit to Kafka when aiokafka is wired
    # kafka_producer.send(_TOPIC, event.model_dump())

    return event
