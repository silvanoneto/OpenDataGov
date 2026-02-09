"""Drift Monitor Service - Main application.

Background service that:
1. Consumes predictions from Kafka (odg.predictions)
2. Maintains sliding windows per model
3. Periodically checks for drift using Evidently
4. Triggers retraining via B-Swarm governance when drift detected
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from pydantic_settings import BaseSettings, SettingsConfigDict

from drift_monitor.consumers.prediction_consumer import PredictionConsumer
from drift_monitor.detectors.evidently_detector import EvidentialyDriftDetector
from drift_monitor.triggers.retraining_trigger import DriftMetrics, RetrainingTrigger

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Drift monitor settings."""

    model_config = SettingsConfigDict(env_prefix="DRIFT_MONITOR_")

    # Kafka settings
    kafka_bootstrap_servers: str = "kafka:9092"
    kafka_topic: str = "odg.predictions"

    # Governance settings
    governance_engine_url: str = "http://governance-engine:8000"
    auto_trigger_retraining: bool = True

    # Drift detection settings
    drift_threshold: float = 0.5  # 50% of features must drift
    min_samples: int = 100
    check_interval_seconds: int = 3600  # Check every hour

    # Window sizes
    reference_window_days: int = 7
    current_window_hours: int = 24


settings = Settings()


# Global instances
consumer: PredictionConsumer | None = None
detector: EvidentialyDriftDetector | None = None
trigger: RetrainingTrigger | None = None
metrics: DriftMetrics | None = None
monitor_task: asyncio.Task | None = None


async def drift_monitoring_loop() -> None:
    """Background loop for drift monitoring.

    Periodically checks all models for drift and triggers retraining if needed.
    """
    global consumer, detector, trigger, metrics

    logger.info("Starting drift monitoring loop...")

    while True:
        try:
            # Consume new predictions
            consumer.consume(timeout_ms=1000)

            # Check each monitored model
            for model_name, window in consumer.windows.items():
                # Skip if insufficient samples
                if window.sample_count < settings.min_samples:
                    logger.debug(
                        f"Skipping {model_name}: insufficient samples "
                        f"({window.sample_count} < {settings.min_samples})"
                    )
                    continue

                # Get reference and current windows
                reference_data = window.get_reference_data()
                current_data = window.get_current_data()

                if len(current_data) < settings.min_samples:
                    logger.debug(f"Skipping {model_name}: insufficient current samples")
                    continue

                # Detect drift
                logger.info(
                    f"Checking drift for {model_name}: "
                    f"ref={len(reference_data)}, cur={len(current_data)}"
                )

                # For now, only check prediction drift (simplified)
                # In production, you'd also check feature drift
                reference_predictions = reference_data["prediction"]
                current_predictions = current_data["prediction"]

                drift_report = detector.detect_prediction_drift(
                    reference_predictions=reference_predictions,
                    current_predictions=current_predictions,
                    model_name=model_name,
                )

                # Record metrics
                metrics.record_drift(model_name, drift_report.drift_score)

                # Trigger retraining if drift detected
                if drift_report.drift_detected:
                    logger.warning(
                        f"🚨 Drift detected for {model_name}! Score: {drift_report.drift_score:.3f}"
                    )

                    try:
                        result = await trigger.trigger_retraining(drift_report)
                        if result:
                            metrics.record_retraining(model_name)
                            logger.info(
                                f"✓ Retraining triggered for {model_name}: "
                                f"decision {result['decision_id']}"
                            )
                    except Exception as e:
                        logger.error(f"Failed to trigger retraining for {model_name}: {e}")

                else:
                    logger.info(
                        f"✓ No drift detected for {model_name} "
                        f"(score: {drift_report.drift_score:.3f})"
                    )

        except Exception as e:
            logger.error(f"Error in drift monitoring loop: {e}", exc_info=True)

        # Wait before next check
        await asyncio.sleep(settings.check_interval_seconds)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Manage application lifecycle."""
    global consumer, detector, trigger, metrics, monitor_task

    logger.info("Starting Drift Monitor Service...")

    # Initialize components
    consumer = PredictionConsumer(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        topic=settings.kafka_topic,
    )
    consumer.connect()

    detector = EvidentialyDriftDetector(
        drift_threshold=settings.drift_threshold,
        min_samples=settings.min_samples,
    )

    trigger = RetrainingTrigger(
        governance_engine_url=settings.governance_engine_url,
        auto_trigger=settings.auto_trigger_retraining,
    )

    metrics = DriftMetrics()

    # Start background monitoring task
    monitor_task = asyncio.create_task(drift_monitoring_loop())

    logger.info("✓ Drift Monitor Service started")

    yield

    # Cleanup
    logger.info("Shutting down Drift Monitor Service...")

    if monitor_task:
        monitor_task.cancel()
        try:
            await monitor_task
        except asyncio.CancelledError:
            pass

    if consumer:
        consumer.close()

    logger.info("✓ Drift Monitor Service stopped")


app = FastAPI(
    title="OpenDataGov Drift Monitor",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}


@app.get("/metrics")
async def get_metrics() -> dict:
    """Get drift monitoring metrics."""
    if metrics is None:
        return {"error": "Metrics not initialized"}

    return metrics.get_metrics()


@app.get("/models/{model_name}/drift")
async def get_model_drift(model_name: str) -> dict:
    """Get drift status for a specific model.

    Args:
        model_name: Model name

    Returns:
        Drift status and window info
    """
    if consumer is None:
        return {"error": "Consumer not initialized"}

    window = consumer.get_window(model_name)

    return {
        "model_name": model_name,
        "sample_count": window.sample_count,
        "window_size_days": settings.reference_window_days,
        "last_check": "N/A",  # TODO: Track last check time
    }
