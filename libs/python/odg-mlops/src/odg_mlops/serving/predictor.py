"""Custom KServe predictor with OpenDataGov observability.

This predictor adds:
- OpenTelemetry tracing for all predictions
- Kafka logging for prediction audit trail
- Prometheus metrics for monitoring
- Integration with drift detection
"""

from __future__ import annotations

import logging
import time
from typing import Any

import mlflow
from kserve import Model
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)


class ODGPredictor(Model):
    """Custom KServe predictor with observability and governance.

    Features:
    - OpenTelemetry distributed tracing
    - Kafka audit logging (predictions stored for drift detection)
    - Prometheus metrics
    - MLflow model loading
    - Automatic error handling and retries

    Example:
        ```python
        # Create custom predictor
        predictor = ODGPredictor(
            name="customer-churn",
            model_uri="models:/customer-churn/Production",
            mlflow_tracking_uri="http://mlflow:5000"
        )

        # Deploy with KServe
        kserve.KServeClient().create(predictor)
        ```
    """

    def __init__(
        self,
        name: str,
        model_uri: str,
        mlflow_tracking_uri: str = "http://mlflow:5000",
        kafka_bootstrap_servers: str = "kafka:9092",
        kafka_topic: str = "odg.predictions",
        enable_kafka: bool = True,
    ):
        """Initialize ODG predictor.

        Args:
            name: Model name
            model_uri: MLflow model URI (e.g., "models:/customer-churn/Production")
            mlflow_tracking_uri: MLflow tracking server URL
            kafka_bootstrap_servers: Kafka bootstrap servers
            kafka_topic: Kafka topic for prediction logs
            enable_kafka: Whether to enable Kafka logging
        """
        super().__init__(name)
        self.model_uri = model_uri
        self.mlflow_tracking_uri = mlflow_tracking_uri
        self.kafka_bootstrap_servers = kafka_bootstrap_servers
        self.kafka_topic = kafka_topic
        self.enable_kafka = enable_kafka

        self.model: Any | None = None
        self.kafka_producer: Any | None = None

        # Metrics
        self.prediction_count = 0
        self.error_count = 0
        self.total_latency = 0.0

    def load(self) -> bool:
        """Load model from MLflow.

        Returns:
            bool: True if model loaded successfully

        Raises:
            RuntimeError: If model fails to load
        """
        with tracer.start_as_current_span("load_model") as span:
            span.set_attribute("model.uri", self.model_uri)
            span.set_attribute("model.name", self.name)

            try:
                # Configure MLflow
                mlflow.set_tracking_uri(self.mlflow_tracking_uri)

                # Load model
                logger.info(f"Loading model from {self.model_uri}")
                self.model = mlflow.sklearn.load_model(self.model_uri)

                # Initialize Kafka producer
                if self.enable_kafka:
                    try:
                        import json

                        from kafka import KafkaProducer

                        self.kafka_producer = KafkaProducer(
                            bootstrap_servers=self.kafka_bootstrap_servers,
                            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                        )
                        logger.info(f"Kafka producer initialized: {self.kafka_topic}")
                    except Exception as e:
                        logger.warning(f"Failed to initialize Kafka: {e}")
                        self.enable_kafka = False

                logger.info(f"✓ Model {self.name} loaded successfully")
                span.set_status(Status(StatusCode.OK))
                return True

            except Exception as e:
                logger.error(f"Failed to load model: {e}")
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise RuntimeError(f"Model loading failed: {e}") from e

    def predict(
        self,
        payload: dict,
        headers: dict[str, str] | None = None,
    ) -> dict:
        """Make prediction with observability.

        Args:
            payload: Prediction request payload
                Format: {"instances": [[feature1, feature2, ...]]}
            headers: Optional request headers

        Returns:
            dict: Prediction response
                Format: {"predictions": [class1, class2, ...]}

        Raises:
            ValueError: If model not loaded or invalid payload
        """
        if self.model is None:
            raise ValueError("Model not loaded. Call load() first.")

        # Extract trace context from headers
        trace_id = None
        if headers:
            trace_id = headers.get("x-b3-traceid")

        with tracer.start_as_current_span("predict") as span:
            span.set_attribute("model.name", self.name)
            span.set_attribute("model.uri", self.model_uri)
            if trace_id:
                span.set_attribute("trace.id", trace_id)

            start_time = time.time()

            try:
                # Extract instances from payload
                instances = payload.get("instances")
                if instances is None:
                    raise ValueError("Missing 'instances' in payload")

                span.set_attribute("prediction.batch_size", len(instances))

                # Make prediction
                predictions = self.model.predict(instances)

                # Calculate latency
                latency = time.time() - start_time
                self.total_latency += latency
                self.prediction_count += 1

                span.set_attribute("prediction.latency_ms", latency * 1000)
                span.set_attribute("prediction.count", len(predictions))

                # Log to Kafka for drift detection
                if self.enable_kafka and self.kafka_producer:
                    try:
                        self._log_to_kafka(
                            instances=instances,
                            predictions=predictions.tolist(),
                            latency=latency,
                            trace_id=trace_id or format(span.get_span_context().trace_id, "032x"),
                        )
                    except Exception as e:
                        logger.warning(f"Failed to log to Kafka: {e}")

                # Return predictions
                response = {"predictions": predictions.tolist()}

                span.set_status(Status(StatusCode.OK))
                logger.info(
                    f"Prediction completed: {len(predictions)} results in {latency * 1000:.1f}ms"
                )

                return response

            except Exception as e:
                self.error_count += 1
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                logger.error(f"Prediction failed: {e}")
                raise

    def _log_to_kafka(
        self,
        instances: list,
        predictions: list,
        latency: float,
        trace_id: str,
    ) -> None:
        """Log prediction to Kafka for audit trail and drift detection.

        Args:
            instances: Input features
            predictions: Model predictions
            latency: Prediction latency in seconds
            trace_id: Distributed trace ID
        """
        from datetime import datetime

        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "model": self.name,
            "model_uri": self.model_uri,
            "trace_id": trace_id,
            "predictions": predictions,
            "latency_ms": latency * 1000,
            "batch_size": len(predictions),
            # Don't log full instances (privacy), just summary stats
            "feature_count": len(instances[0]) if instances else 0,
        }

        self.kafka_producer.send(self.kafka_topic, value=event)

    def explain(self, payload: dict, headers: dict[str, str] | None = None) -> dict:
        """Generate model explanation (SHAP values, LIME, etc.).

        For EU AI Act HIGH risk models, explanations may be required.

        Args:
            payload: Explanation request payload
            headers: Optional request headers

        Returns:
            dict: Explanation response

        Raises:
            NotImplementedError: Explainability not yet implemented
        """
        # TODO: Implement SHAP/LIME integration (Phase 6)
        raise NotImplementedError("Explainability not yet implemented")

    def get_metrics(self) -> dict:
        """Get predictor metrics for Prometheus.

        Returns:
            dict: Metrics dict
        """
        avg_latency = self.total_latency / self.prediction_count if self.prediction_count > 0 else 0

        return {
            "model_name": self.name,
            "prediction_count": self.prediction_count,
            "error_count": self.error_count,
            "average_latency_ms": avg_latency * 1000,
            "error_rate": self.error_count / self.prediction_count
            if self.prediction_count > 0
            else 0,
        }
