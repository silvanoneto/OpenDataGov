"""Differential privacy via OpenDP (ADR-070).

Provides a thin wrapper around OpenDP for applying Laplace noise
to numeric aggregates based on data classification level.
"""

from __future__ import annotations

import logging
from typing import Any

from odg_core.enums import DataClassification

logger = logging.getLogger(__name__)

# Epsilon budgets per classification level (lower = more private)
DEFAULT_EPSILON: dict[DataClassification, float] = {
    DataClassification.PUBLIC: 10.0,
    DataClassification.INTERNAL: 5.0,
    DataClassification.CONFIDENTIAL: 1.0,
    DataClassification.RESTRICTED: 0.1,
    DataClassification.TOP_SECRET: 0.01,
}


def get_epsilon(classification: DataClassification) -> float:
    """Get the default epsilon value for a classification level."""
    return DEFAULT_EPSILON.get(classification, 1.0)


def add_laplace_noise(
    value: float,
    sensitivity: float,
    epsilon: float,
    *,
    seed: int | None = None,
) -> float:
    """Add calibrated Laplace noise to a value.

    Uses OpenDP if available, otherwise falls back to numpy.

    Args:
        value: The true aggregate value.
        sensitivity: The sensitivity of the query (max change from one record).
        epsilon: Privacy budget parameter (lower = more private).

    Returns:
        Noised value.
    """
    scale = sensitivity / epsilon

    try:
        import opendp.prelude as dp

        dp.enable_features("contrib")
        space = dp.atom_domain(T=float), dp.absolute_distance(T=float)
        meas = space >> dp.then_laplace(scale=scale)  # type: ignore[attr-defined]
        noise: float = meas(0.0)
        return value + noise
    except ImportError:
        pass

    try:
        import numpy as np

        rng = np.random.default_rng(seed)
        noise_val: float = float(rng.laplace(0, scale))
        return value + noise_val
    except ImportError:
        logger.warning("Neither opendp nor numpy available, returning value without noise")
        return value


def apply_differential_privacy(
    aggregates: dict[str, float],
    *,
    sensitivity: float = 1.0,
    classification: DataClassification = DataClassification.CONFIDENTIAL,
    epsilon: float | None = None,
    seed: int | None = None,
) -> dict[str, Any]:
    """Apply differential privacy to a set of aggregates.

    Args:
        aggregates: Dict of metric_name -> raw_value.
        sensitivity: Query sensitivity.
        classification: Data classification level (determines epsilon if not provided).
        epsilon: Override epsilon (if None, derived from classification).

    Returns:
        Dict with noised values and metadata.
    """
    eps = epsilon if epsilon is not None else get_epsilon(classification)

    noised = {}
    for name, val in aggregates.items():
        noised[name] = add_laplace_noise(val, sensitivity, eps, seed=seed)

    return {
        "values": noised,
        "epsilon": eps,
        "sensitivity": sensitivity,
        "classification": classification.value,
        "mechanism": "laplace",
    }
