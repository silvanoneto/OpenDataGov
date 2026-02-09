"""Real-time feature materialization with PyFlink.

Materializes features to Feast online store in real-time:
1. Consume events from Kafka
2. Compute features (aggregations, transformations)
3. Write to Feast online store (Redis)
4. Emit DQ metrics

Example use case:
- Customer transaction stream → Real-time customer features
- Clickstream → Real-time user behavior features
- IoT sensors → Real-time device features
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from pyflink.common import Types, WatermarkStrategy
from pyflink.datastream import StreamExecutionEnvironment
from pyflink.datastream.connectors.kafka import (
    KafkaRecordSerializationSchema,
    KafkaSink,
    KafkaSource,
)
from pyflink.datastream.formats.json import JsonRowDeserializationSchema, JsonRowSerializationSchema
from pyflink.datastream.functions import MapFunction, ProcessWindowFunction
from pyflink.datastream.window import TumblingEventTimeWindows

logger = logging.getLogger(__name__)


class TransactionToFeatures(MapFunction):
    """Transform transaction events to customer features."""

    def map(self, value: dict[str, Any]) -> dict[str, Any]:
        """Transform transaction to feature record.

        Args:
            value: Transaction event

        Returns:
            Feature record with entity_id and feature values
        """
        return {
            "entity_type": "customer",
            "entity_id": value["customer_id"],
            "features": {
                "last_transaction_amount": float(value["amount"]),
                "last_transaction_timestamp": value["timestamp"],
                "transaction_count": 1,  # Will be aggregated
            },
            "event_timestamp": value["timestamp"],
        }


class CustomerFeatureAggregator(ProcessWindowFunction):
    """Aggregate customer features over time window."""

    def process(
        self,
        key: str,
        context: ProcessWindowFunction.Context,
        elements: list[dict],
    ) -> list[dict]:
        """Aggregate features for customer.

        Args:
            key: Customer ID
            context: Window context
            elements: Feature records in window

        Returns:
            Aggregated feature record
        """
        total_amount = sum(e["features"]["last_transaction_amount"] for e in elements)
        transaction_count = len(elements)
        avg_amount = total_amount / transaction_count if transaction_count > 0 else 0.0

        # Get latest timestamp
        latest_timestamp = max(e["event_timestamp"] for e in elements)

        return [
            {
                "entity_type": "customer",
                "entity_id": key,
                "features": {
                    "total_transaction_amount_1h": total_amount,
                    "transaction_count_1h": transaction_count,
                    "avg_transaction_amount_1h": avg_amount,
                    "last_transaction_timestamp": latest_timestamp,
                },
                "event_timestamp": latest_timestamp,
                "window_start": context.window().start,
                "window_end": context.window().end,
            }
        ]


def create_realtime_feature_job(
    env: StreamExecutionEnvironment,
    kafka_bootstrap: str = "kafka:9092",
    input_topic: str = "odg.transactions.realtime",
    output_topic: str = "odg.features.realtime",
    window_size_minutes: int = 60,
) -> None:
    """Create real-time feature materialization job.

    Args:
        env: Flink execution environment
        kafka_bootstrap: Kafka bootstrap servers
        input_topic: Input topic (transaction events)
        output_topic: Output topic (computed features)
        window_size_minutes: Aggregation window size
    """
    # Configure Kafka source
    kafka_source = (
        KafkaSource.builder()
        .set_bootstrap_servers(kafka_bootstrap)
        .set_topics(input_topic)
        .set_group_id("flink-feature-materializer")
        .set_starting_offsets_to_earliest()
        .set_value_only_deserializer(
            JsonRowDeserializationSchema.builder()
            .type_info(
                Types.ROW(
                    [
                        Types.STRING(),  # customer_id
                        Types.DOUBLE(),  # amount
                        Types.STRING(),  # timestamp
                    ]
                )
            )
            .build()
        )
        .build()
    )

    # Create data stream
    transactions = env.from_source(
        kafka_source,
        WatermarkStrategy.for_bounded_out_of_orderness(timedelta(seconds=10)),
        "kafka-transactions",
    )

    # Transform to features
    features = transactions.map(
        TransactionToFeatures(),
        output_type=Types.MAP(Types.STRING(), Types.PICKLED_BYTE_ARRAY()),
    )

    # Aggregate over time window (1 hour)
    aggregated_features = (
        features.key_by(lambda x: x["entity_id"])
        .window(TumblingEventTimeWindows.of(timedelta(minutes=window_size_minutes)))
        .process(CustomerFeatureAggregator())
    )

    # Sink to Kafka (will be consumed by Feast materializer)
    kafka_sink = (
        KafkaSink.builder()
        .set_bootstrap_servers(kafka_bootstrap)
        .set_record_serializer(
            KafkaRecordSerializationSchema.builder()
            .set_topic(output_topic)
            .set_value_serialization_schema(JsonRowSerializationSchema.builder().build())
            .build()
        )
        .build()
    )

    aggregated_features.sink_to(kafka_sink)

    logger.info(f"Created real-time feature job: {input_topic} → {output_topic} (window: {window_size_minutes}min)")


def main():
    """Run real-time feature materialization job."""
    # Create execution environment
    env = StreamExecutionEnvironment.get_execution_environment()

    # Configure checkpointing
    env.enable_checkpointing(60000)  # 1 minute
    env.get_checkpoint_config().set_checkpoint_storage("s3://flink-checkpoints/")

    # Set parallelism
    env.set_parallelism(4)

    # Create job
    create_realtime_feature_job(
        env=env,
        kafka_bootstrap="kafka:9092",
        input_topic="odg.transactions.realtime",
        output_topic="odg.features.realtime",
        window_size_minutes=60,
    )

    # Execute
    env.execute("realtime-feature-materialization")


if __name__ == "__main__":
    main()
