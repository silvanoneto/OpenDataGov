"""OTel gauge for data freshness (seconds since last update)."""

from __future__ import annotations

from opentelemetry import metrics

_meter = metrics.get_meter("odg.data.observability")
_freshness_gauge = _meter.create_gauge(
    name="odg.data.freshness_seconds",
    description="Seconds since the dataset was last updated",
    unit="s",
)


def record_freshness(
    dataset: str,
    domain: str,
    layer: str,
    seconds_since_update: float,
) -> None:
    """Record freshness for a dataset as an OTel gauge."""
    _freshness_gauge.set(
        seconds_since_update,
        attributes={"dataset": dataset, "domain": domain, "layer": layer},
    )
