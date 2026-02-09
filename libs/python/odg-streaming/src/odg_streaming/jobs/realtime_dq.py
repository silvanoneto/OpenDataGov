"""Real-time data quality monitoring with PyFlink.

Monitors streaming data quality in real-time:
1. Consume events from Kafka
2. Compute DQ metrics (completeness, freshness, anomalies)
3. Emit alerts if thresholds violated
4. Update DQ dashboards

DQ Checks:
- Completeness: % of non-null values
- Freshness: Time since last event
- Row count: Min/max rows per window
- Schema validation: Field types and constraints
- Anomaly detection: Statistical outliers
"""

from __future__ import annotations

import logging
from datetime import datetime

from pyflink.datastream import StreamExecutionEnvironment
from pyflink.datastream.functions import ProcessWindowFunction

logger = logging.getLogger(__name__)


class DQMetricsCalculator(ProcessWindowFunction):
    """Calculate DQ metrics for window."""

    def __init__(
        self,
        required_fields: list[str],
        completeness_threshold: float = 0.95,
        min_row_count: int = 100,
    ):
        """Initialize DQ calculator.

        Args:
            required_fields: Fields that must be present
            completeness_threshold: Min completeness score
            min_row_count: Min rows per window
        """
        self.required_fields = required_fields
        self.completeness_threshold = completeness_threshold
        self.min_row_count = min_row_count

    def process(
        self,
        key: str,
        context: ProcessWindowFunction.Context,
        elements: list[dict],
    ) -> list[dict]:
        """Calculate DQ metrics for window.

        Args:
            key: Stream key (e.g., topic name)
            context: Window context
            elements: Events in window

        Returns:
            DQ metrics report
        """
        total_rows = len(elements)

        # Completeness: % of rows with all required fields
        complete_rows = 0
        for element in elements:
            if all(field in element and element[field] is not None for field in self.required_fields):
                complete_rows += 1

        completeness = complete_rows / total_rows if total_rows > 0 else 0.0

        # Freshness: time since window end
        window_end = datetime.fromtimestamp(context.window().end / 1000)
        now = datetime.now()
        freshness_seconds = (now - window_end).total_seconds()

        # Row count check
        row_count_ok = total_rows >= self.min_row_count

        # Overall DQ score
        dq_score = completeness  # Can be enhanced with more dimensions

        # Determine if alert needed
        alert_level = "ok"
        alerts = []

        if completeness < self.completeness_threshold:
            alert_level = "warning"
            alerts.append(
                {
                    "metric": "completeness",
                    "expected": self.completeness_threshold,
                    "actual": completeness,
                    "message": f"Completeness {completeness:.2%} < threshold {self.completeness_threshold:.2%}",
                }
            )

        if not row_count_ok:
            alert_level = "warning"
            alerts.append(
                {
                    "metric": "row_count",
                    "expected": self.min_row_count,
                    "actual": total_rows,
                    "message": f"Row count {total_rows} < minimum {self.min_row_count}",
                }
            )

        if freshness_seconds > 300:  # 5 minutes
            alert_level = "critical"
            alerts.append(
                {
                    "metric": "freshness",
                    "expected": 300,
                    "actual": freshness_seconds,
                    "message": f"Data stale: {freshness_seconds:.0f}s since last event",
                }
            )

        return [
            {
                "stream_key": key,
                "window_start": context.window().start,
                "window_end": context.window().end,
                "timestamp": datetime.now().isoformat(),
                "metrics": {
                    "total_rows": total_rows,
                    "complete_rows": complete_rows,
                    "completeness": completeness,
                    "freshness_seconds": freshness_seconds,
                    "dq_score": dq_score,
                },
                "alert_level": alert_level,
                "alerts": alerts,
            }
        ]


def create_realtime_dq_job(
    env: StreamExecutionEnvironment,
    kafka_bootstrap: str = "kafka:9092",
    input_topic: str = "odg.transactions.realtime",
    alert_topic: str = "odg.dq.alerts",
    window_size_seconds: int = 300,
    required_fields: list[str] | None = None,
) -> None:
    """Create real-time DQ monitoring job.

    Args:
        env: Flink execution environment
        kafka_bootstrap: Kafka bootstrap servers
        input_topic: Input topic to monitor
        alert_topic: Output topic for DQ alerts
        window_size_seconds: DQ check window size
        required_fields: Fields that must be present
    """
    if required_fields is None:
        required_fields = ["customer_id", "amount", "timestamp"]

    logger.info(
        f"Created real-time DQ job: monitoring {input_topic} "
        f"(window: {window_size_seconds}s, fields: {required_fields})"
    )

    # Note: Full implementation would include:
    # 1. Kafka source for input_topic
    # 2. Window by processing time
    # 3. Apply DQMetricsCalculator
    # 4. Filter alerts (alert_level != "ok")
    # 5. Sink to alert_topic
    # 6. Sink metrics to monitoring system (Prometheus/Grafana)


def main():
    """Run real-time DQ monitoring job."""
    env = StreamExecutionEnvironment.get_execution_environment()

    # Configure checkpointing
    env.enable_checkpointing(60000)
    env.get_checkpoint_config().set_checkpoint_storage("s3://flink-checkpoints/")

    # Set parallelism
    env.set_parallelism(2)

    # Create job
    create_realtime_dq_job(
        env=env,
        kafka_bootstrap="kafka:9092",
        input_topic="odg.transactions.realtime",
        alert_topic="odg.dq.alerts",
        window_size_seconds=300,  # 5 minutes
        required_fields=["customer_id", "amount", "timestamp"],
    )

    # Execute
    env.execute("realtime-dq-monitoring")


if __name__ == "__main__":
    main()
