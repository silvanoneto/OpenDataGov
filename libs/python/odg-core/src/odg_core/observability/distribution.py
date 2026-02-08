"""Distribution drift detection via Kolmogorov-Smirnov test."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from opentelemetry import trace

if TYPE_CHECKING:
    from collections.abc import Sequence

logger = logging.getLogger(__name__)


def detect_distribution_drift(
    dataset: str,
    column: str,
    reference: Sequence[float],
    current: Sequence[float],
    threshold: float = 0.05,
) -> dict[str, object]:
    """Run a two-sample KS test and report drift as an OTel span event.

    Returns a dict with statistic, p_value, and has_drift fields.
    Requires scipy; if unavailable, returns has_drift=False with a warning.
    """
    try:
        from scipy.stats import ks_2samp
    except ImportError:
        logger.warning("scipy not installed — skipping distribution drift check")
        return {"statistic": 0.0, "p_value": 1.0, "has_drift": False}

    stat, p_value = ks_2samp(reference, current)
    has_drift = p_value < threshold

    if has_drift:
        span = trace.get_current_span()
        span.add_event(
            "distribution_drift_detected",
            attributes={
                "dataset": dataset,
                "column": column,
                "ks_statistic": stat,
                "p_value": p_value,
                "threshold": threshold,
            },
        )
        logger.warning(
            "Distribution drift for %s.%s: KS=%.4f p=%.4f (threshold=%.4f)",
            dataset,
            column,
            stat,
            p_value,
            threshold,
        )

    return {"statistic": stat, "p_value": p_value, "has_drift": has_drift}
