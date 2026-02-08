"""OTel counter for data volume (row count per dataset)."""

from __future__ import annotations

from opentelemetry import metrics

_meter = metrics.get_meter("odg.data.observability")
_row_counter = _meter.create_counter(
    name="odg.data.row_count",
    description="Total rows ingested or promoted per dataset",
    unit="rows",
)


def record_row_count(
    dataset: str,
    domain: str,
    layer: str,
    rows: int,
) -> None:
    """Record row count for a dataset promotion as an OTel counter."""
    _row_counter.add(
        rows,
        attributes={"dataset": dataset, "domain": domain, "layer": layer},
    )
