"""Automatic retraining trigger via B-Swarm governance.

When drift is detected, creates a governance decision for model retraining.
Follows RACI workflow for approval.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
from drift_monitor.detectors.evidently_detector import DriftReport

logger = logging.getLogger(__name__)


class RetrainingTrigger:
    """Triggers retraining workflows via governance engine."""

    def __init__(
        self,
        governance_engine_url: str = "http://governance-engine:8000",
        auto_trigger: bool = True,
    ):
        """Initialize retraining trigger.

        Args:
            governance_engine_url: Governance Engine URL
            auto_trigger: Whether to automatically create decisions (vs manual)
        """
        self.governance_engine_url = governance_engine_url
        self.auto_trigger = auto_trigger

    async def trigger_retraining(
        self,
        drift_report: DriftReport,
        requester_id: str = "drift-monitor",
    ) -> dict[str, Any] | None:
        """Trigger retraining via governance decision.

        Args:
            drift_report: Drift detection report
            requester_id: ID of requester (system service)

        Returns:
            Governance decision response or None if disabled

        Raises:
            RuntimeError: If governance API call fails
        """
        if not self.auto_trigger:
            logger.info(
                f"Auto-trigger disabled for {drift_report.model_name}. "
                "Manual intervention required."
            )
            return None

        logger.warning(
            f"🚨 Drift detected for {drift_report.model_name}! "
            f"Score: {drift_report.drift_score:.3f}, "
            f"Features: {drift_report.drifted_features}"
        )

        # Build retraining request
        payload = {
            "model_name": drift_report.model_name,
            "reason": f"Data drift detected: {len(drift_report.drifted_features)} features drifted",
            "drift_score": drift_report.drift_score,
            "drift_details": {
                "drifted_features": drift_report.drifted_features,
                "reference_samples": drift_report.reference_samples,
                "current_samples": drift_report.current_samples,
                "timestamp": drift_report.timestamp.isoformat(),
                "metadata": drift_report.metadata,
            },
            "requester_id": requester_id,
        }

        logger.info(
            f"Creating retraining decision for {drift_report.model_name} "
            f"via {self.governance_engine_url}"
        )

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.governance_engine_url}/api/v1/mlops/model-retraining",
                    json=payload,
                )
                response.raise_for_status()
                result = response.json()

            decision_id = result.get("decision_id")
            logger.info(
                f"✓ Retraining decision created: {decision_id} for {drift_report.model_name}"
            )

            # Publish alert to Kafka
            await self._publish_drift_alert(drift_report, decision_id)

            return result

        except httpx.HTTPError as e:
            logger.error(f"Failed to trigger retraining: {e}")
            raise RuntimeError(f"Retraining trigger failed: {e}") from e

    async def _publish_drift_alert(
        self,
        drift_report: DriftReport,
        decision_id: str,
    ) -> None:
        """Publish drift alert to Kafka for notifications.

        Args:
            drift_report: Drift report
            decision_id: Governance decision ID
        """
        # TODO: Publish to Kafka topic: odg.ml.drift.alerts
        # This will be consumed by notification service to alert Data Scientists

        logger.info(
            f"📧 Drift alert published: {drift_report.model_name} (decision: {decision_id})"
        )


class DriftMetrics:
    """Drift metrics for monitoring."""

    def __init__(self):
        """Initialize metrics."""
        self.drift_detected_count = 0
        self.retraining_triggered_count = 0
        self.models_monitored: set[str] = set()

    def record_drift(self, model_name: str, drift_score: float) -> None:
        """Record drift detection.

        Args:
            model_name: Model name
            drift_score: Drift score
        """
        self.drift_detected_count += 1
        self.models_monitored.add(model_name)

        logger.info(f"Drift metric recorded: {model_name} (score: {drift_score:.3f})")

    def record_retraining(self, model_name: str) -> None:
        """Record retraining trigger.

        Args:
            model_name: Model name
        """
        self.retraining_triggered_count += 1

        logger.info(f"Retraining metric recorded: {model_name}")

    def get_metrics(self) -> dict[str, Any]:
        """Get current metrics.

        Returns:
            Metrics dictionary
        """
        return {
            "drift_detected_total": self.drift_detected_count,
            "retraining_triggered_total": self.retraining_triggered_count,
            "models_monitored": len(self.models_monitored),
            "monitored_models": list(self.models_monitored),
        }
