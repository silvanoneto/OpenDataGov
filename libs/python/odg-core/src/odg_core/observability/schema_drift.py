"""Schema drift detection via column comparison."""

from __future__ import annotations

import logging

from opentelemetry import trace

logger = logging.getLogger(__name__)
_tracer = trace.get_tracer("odg.data.observability")


def detect_schema_drift(
    dataset: str,
    domain: str,
    expected_columns: list[str],
    actual_columns: list[str],
) -> dict[str, object]:
    """Compare expected vs actual columns and report drift as an OTel span event.

    Returns a dict with added, removed, and has_drift fields.
    """
    expected = set(expected_columns)
    actual = set(actual_columns)

    added = sorted(actual - expected)
    removed = sorted(expected - actual)
    has_drift = bool(added or removed)

    if has_drift:
        span = trace.get_current_span()
        span.add_event(
            "schema_drift_detected",
            attributes={
                "dataset": dataset,
                "domain": domain,
                "columns_added": ", ".join(added) if added else "",
                "columns_removed": ", ".join(removed) if removed else "",
            },
        )
        logger.warning(
            "Schema drift for %s/%s: added=%s removed=%s",
            domain,
            dataset,
            added,
            removed,
        )

    return {"added": added, "removed": removed, "has_drift": has_drift}
