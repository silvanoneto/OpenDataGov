"""Data promotion logic across medallion layers.

Promotion rules (ADR-024):

* Bronze -> Silver  : automatic if ``dq_score >= 0.7``
* Silver -> Gold    : requires governance decision if ``dq_score >= 0.85``
* Gold   -> Platinum: always requires governance decision if ``dq_score >= 0.95``
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

from odg_core.enums import MedallionLayer

from lakehouse_agent.protocols import BucketManager, bucket_name

# ── Thresholds ───────────────────────────────────────────

_DQ_THRESHOLDS: dict[tuple[MedallionLayer, MedallionLayer], float] = {
    (MedallionLayer.BRONZE, MedallionLayer.SILVER): 0.7,
    (MedallionLayer.SILVER, MedallionLayer.GOLD): 0.85,
    (MedallionLayer.GOLD, MedallionLayer.PLATINUM): 0.95,
}

_LAYER_ORDER: list[MedallionLayer] = [
    MedallionLayer.BRONZE,
    MedallionLayer.SILVER,
    MedallionLayer.GOLD,
    MedallionLayer.PLATINUM,
]


class PromotionError(Exception):
    """Raised when a promotion cannot be performed."""


# ── Promotion strategies (OCP) ───────────────────────────


class _AutoPromotionStrategy:
    """Bronze -> Silver: automatic promotion when DQ threshold is met."""

    async def execute(
        self,
        bucket_manager: BucketManager,
        domain_id: str,
        source_layer: MedallionLayer,
        target_layer: MedallionLayer,
        dataset_id: str,
        dq_score: float,
    ) -> dict[str, Any]:
        source_bucket = bucket_name(source_layer, domain_id)
        target_bucket = bucket_name(target_layer, domain_id)

        data = await bucket_manager.get_object(source_bucket, dataset_id)
        await bucket_manager.upload_object(target_bucket, dataset_id, data)

        return {
            "promoted": True,
            "auto_approved": True,
            "governance_decision_id": None,
            "source_layer": source_layer.value,
            "target_layer": target_layer.value,
            "dataset_id": dataset_id,
            "dq_score": dq_score,
            "reason": f"Automatic promotion: DQ score meets {source_layer.value} -> {target_layer.value} threshold",
        }


class _GovernancePromotionStrategy:
    """Silver -> Gold / Gold -> Platinum: requires governance decision."""

    async def execute(
        self,
        _bucket_manager: BucketManager,
        _domain_id: str,
        source_layer: MedallionLayer,
        target_layer: MedallionLayer,
        dataset_id: str,
        dq_score: float,
    ) -> dict[str, Any]:
        await asyncio.sleep(0)  # Cooperative yield; real impl will call governance API
        governance_decision_id = str(uuid.uuid4())

        return {
            "promoted": False,
            "auto_approved": False,
            "governance_decision_id": governance_decision_id,
            "source_layer": source_layer.value,
            "target_layer": target_layer.value,
            "dataset_id": dataset_id,
            "dq_score": dq_score,
            "reason": f"Governance decision required for {source_layer.value} -> {target_layer.value} promotion",
        }


# Registry: maps (source, target) → strategy instance.
# To add a new transition, register a strategy here — no changes to PromotionService needed.
_STRATEGIES: dict[
    tuple[MedallionLayer, MedallionLayer],
    _AutoPromotionStrategy | _GovernancePromotionStrategy,
] = {
    (MedallionLayer.BRONZE, MedallionLayer.SILVER): _AutoPromotionStrategy(),
    (MedallionLayer.SILVER, MedallionLayer.GOLD): _GovernancePromotionStrategy(),
    (MedallionLayer.GOLD, MedallionLayer.PLATINUM): _GovernancePromotionStrategy(),
}


# ── Service ──────────────────────────────────────────────


class PromotionService:
    """Orchestrates data promotion between medallion layers."""

    def __init__(self, bucket_manager: BucketManager) -> None:
        self._bucket_manager = bucket_manager

    async def promote(
        self,
        domain_id: str,
        source_layer: MedallionLayer,
        target_layer: MedallionLayer,
        dataset_id: str,
        dq_score: float,
    ) -> dict[str, Any]:
        """Promote a dataset from *source_layer* to *target_layer*.

        Returns a dict describing the outcome::

            {
                "promoted": bool,
                "auto_approved": bool,
                "governance_decision_id": str | None,
                "source_layer": str,
                "target_layer": str,
                "dataset_id": str,
                "dq_score": float,
                "reason": str,
            }
        """
        _validate_transition(source_layer, target_layer)

        threshold = _DQ_THRESHOLDS[(source_layer, target_layer)]

        if dq_score < threshold:
            return {
                "promoted": False,
                "auto_approved": False,
                "governance_decision_id": None,
                "source_layer": source_layer.value,
                "target_layer": target_layer.value,
                "dataset_id": dataset_id,
                "dq_score": dq_score,
                "reason": (
                    f"Data quality score {dq_score} is below the required "
                    f"threshold {threshold} for {source_layer.value} -> "
                    f"{target_layer.value} promotion"
                ),
            }

        strategy = _STRATEGIES[(source_layer, target_layer)]
        return await strategy.execute(
            self._bucket_manager,
            domain_id,
            source_layer,
            target_layer,
            dataset_id,
            dq_score,
        )


# ── Helpers ──────────────────────────────────────────────


def _validate_transition(source: MedallionLayer, target: MedallionLayer) -> None:
    """Ensure the promotion is exactly one step forward."""
    try:
        src_idx = _LAYER_ORDER.index(source)
        tgt_idx = _LAYER_ORDER.index(target)
    except ValueError as exc:
        raise PromotionError(f"Unknown layer: {exc}") from exc

    if tgt_idx != src_idx + 1:
        raise PromotionError(
            f"Invalid promotion: {source.value} -> {target.value}. Promotions must advance exactly one layer."
        )
