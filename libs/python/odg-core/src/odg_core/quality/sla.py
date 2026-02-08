"""Quality SLA threshold management (ADR-052)."""

from __future__ import annotations

from odg_core.enums import DAMADimension

# Default SLA thresholds per medallion layer
DEFAULT_THRESHOLDS: dict[str, dict[str, float]] = {
    "bronze": {dim.value: 0.70 for dim in DAMADimension},
    "silver": {dim.value: 0.85 for dim in DAMADimension},
    "gold": {dim.value: 0.95 for dim in DAMADimension},
    "platinum": {dim.value: 0.98 for dim in DAMADimension},
}


def check_sla(
    dimension_scores: dict[str, float],
    thresholds: dict[str, float],
) -> dict[str, bool]:
    """Check each dimension score against its SLA threshold.

    Returns a dict of dimension → passes_sla (True/False).
    """
    return {dim: dimension_scores.get(dim, 0.0) >= threshold for dim, threshold in thresholds.items()}


def get_layer_thresholds(layer: str) -> dict[str, float]:
    """Get default SLA thresholds for a medallion layer."""
    return DEFAULT_THRESHOLDS.get(layer, DEFAULT_THRESHOLDS["bronze"])
