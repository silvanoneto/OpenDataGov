"""Kafka consumer for model predictions.

Consumes predictions from KServe predictors and maintains
a sliding window for drift detection.
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

import pandas as pd
from kafka import KafkaConsumer

logger = logging.getLogger(__name__)


class PredictionWindow:
    """Sliding window of predictions for a model."""

    def __init__(self, model_name: str, window_size: timedelta = timedelta(days=7)):
        """Initialize prediction window.

        Args:
            model_name: Model name
            window_size: Window size for reference data
        """
        self.model_name = model_name
        self.window_size = window_size
        self.predictions: list[dict[str, Any]] = []

    def add_prediction(self, prediction: dict[str, Any]) -> None:
        """Add prediction to window.

        Args:
            prediction: Prediction event from Kafka
        """
        self.predictions.append(prediction)

        # Remove old predictions
        cutoff = datetime.utcnow() - self.window_size
        self.predictions = [
            p for p in self.predictions if datetime.fromisoformat(p["timestamp"]) > cutoff
        ]

    def get_reference_data(self) -> pd.DataFrame:
        """Get reference window data (all predictions in window).

        Returns:
            DataFrame with prediction features
        """
        if not self.predictions:
            return pd.DataFrame()

        # Extract features from predictions
        # Note: This is simplified - in production, you'd reconstruct
        # original features from predictions
        data = []
        for pred in self.predictions:
            data.append(
                {
                    "timestamp": pred["timestamp"],
                    "prediction": pred["predictions"][0] if pred.get("predictions") else None,
                    "latency_ms": pred.get("latency_ms", 0),
                }
            )

        return pd.DataFrame(data)

    def get_current_data(self, window: timedelta = timedelta(hours=24)) -> pd.DataFrame:
        """Get current window data (last N hours).

        Args:
            window: Current window size

        Returns:
            DataFrame with recent predictions
        """
        cutoff = datetime.utcnow() - window
        recent = [p for p in self.predictions if datetime.fromisoformat(p["timestamp"]) > cutoff]

        if not recent:
            return pd.DataFrame()

        data = []
        for pred in recent:
            data.append(
                {
                    "timestamp": pred["timestamp"],
                    "prediction": pred["predictions"][0] if pred.get("predictions") else None,
                    "latency_ms": pred.get("latency_ms", 0),
                }
            )

        return pd.DataFrame(data)

    @property
    def sample_count(self) -> int:
        """Get total number of predictions in window."""
        return len(self.predictions)


class PredictionConsumer:
    """Kafka consumer for model predictions."""

    def __init__(
        self,
        bootstrap_servers: str,
        topic: str = "odg.predictions",
        group_id: str = "drift-monitor",
    ):
        """Initialize prediction consumer.

        Args:
            bootstrap_servers: Kafka bootstrap servers
            topic: Kafka topic for predictions
            group_id: Consumer group ID
        """
        self.bootstrap_servers = bootstrap_servers
        self.topic = topic
        self.group_id = group_id

        # Model-specific windows
        self.windows: dict[str, PredictionWindow] = defaultdict(
            lambda: PredictionWindow(model_name="", window_size=timedelta(days=7))
        )

        # Kafka consumer
        self.consumer: KafkaConsumer | None = None

    def connect(self) -> None:
        """Connect to Kafka."""
        logger.info(f"Connecting to Kafka: {self.bootstrap_servers}, topic={self.topic}")

        self.consumer = KafkaConsumer(
            self.topic,
            bootstrap_servers=self.bootstrap_servers,
            group_id=self.group_id,
            value_deserializer=lambda v: json.loads(v.decode("utf-8")),
            auto_offset_reset="latest",
            enable_auto_commit=True,
        )

        logger.info("✓ Connected to Kafka")

    def consume(self, timeout_ms: int = 1000) -> list[dict[str, Any]]:
        """Consume predictions from Kafka.

        Args:
            timeout_ms: Consumer poll timeout

        Returns:
            List of prediction events
        """
        if self.consumer is None:
            raise RuntimeError("Consumer not connected. Call connect() first.")

        messages = self.consumer.poll(timeout_ms=timeout_ms)

        events = []
        for topic_partition, records in messages.items():
            for record in records:
                event = record.value
                model_name = event.get("model")

                if not model_name:
                    logger.warning(f"Skipping event without model name: {event}")
                    continue

                # Add to window
                if model_name not in self.windows:
                    self.windows[model_name] = PredictionWindow(model_name=model_name)

                self.windows[model_name].add_prediction(event)
                events.append(event)

        if events:
            logger.debug(f"Consumed {len(events)} prediction events")

        return events

    def get_window(self, model_name: str) -> PredictionWindow:
        """Get prediction window for a model.

        Args:
            model_name: Model name

        Returns:
            PredictionWindow for the model
        """
        if model_name not in self.windows:
            self.windows[model_name] = PredictionWindow(model_name=model_name)

        return self.windows[model_name]

    def close(self) -> None:
        """Close Kafka consumer."""
        if self.consumer:
            self.consumer.close()
            logger.info("Kafka consumer closed")
