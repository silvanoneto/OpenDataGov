#!/usr/bin/env python3
"""Initialize CDC connectors for OpenDataGov.

This script:
1. Waits for Kafka Connect to be ready
2. Creates Debezium connectors for PostgreSQL and TimescaleDB
3. Monitors connector status
4. Creates necessary Kafka topics for CDC events

Usage:
    python init_cdc_connectors.py --kafka-connect-url http://kafka-connect:8083
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

import requests
from kafka.admin import KafkaAdminClient, NewTopic

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class CDCInitializer:
    """Initialize CDC infrastructure for OpenDataGov."""

    def __init__(self, kafka_connect_url: str, kafka_bootstrap_servers: str, connector_configs_dir: str):
        self.kafka_connect_url = kafka_connect_url.rstrip("/")
        self.kafka_bootstrap_servers = kafka_bootstrap_servers
        self.connector_configs_dir = Path(connector_configs_dir)

    def wait_for_kafka_connect(self, timeout: int = 300) -> bool:
        """Wait for Kafka Connect to be ready.

        Args:
            timeout: Maximum time to wait in seconds

        Returns:
            True if Kafka Connect is ready, False otherwise
        """
        logger.info(f"Waiting for Kafka Connect at {self.kafka_connect_url}...")
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                response = requests.get(f"{self.kafka_connect_url}/connectors", timeout=5)
                if response.status_code == 200:
                    logger.info("Kafka Connect is ready!")
                    return True
            except requests.exceptions.RequestException:
                pass

            logger.debug("Kafka Connect not ready yet, waiting 5s...")
            time.sleep(5)

        logger.error(f"Kafka Connect did not become ready within {timeout}s")
        return False

    def create_cdc_topics(self) -> None:
        """Create Kafka topics for CDC events."""
        logger.info("Creating CDC Kafka topics...")

        admin_client = KafkaAdminClient(bootstrap_servers=self.kafka_bootstrap_servers, client_id="cdc-initializer")

        topics = [
            # PostgreSQL CDC topics
            NewTopic(name="cdc.odg.public.governance_decisions", num_partitions=3, replication_factor=1),
            NewTopic(name="cdc.odg.public.approval_records", num_partitions=3, replication_factor=1),
            NewTopic(name="cdc.odg.public.veto_records", num_partitions=3, replication_factor=1),
            NewTopic(name="cdc.odg.public.audit_events", num_partitions=5, replication_factor=1),
            NewTopic(name="cdc.odg.public.pipeline_versions", num_partitions=3, replication_factor=1),
            NewTopic(name="cdc.odg.public.pipeline_executions", num_partitions=5, replication_factor=1),
            NewTopic(name="cdc.odg.public.lineage_events", num_partitions=5, replication_factor=1),
            NewTopic(name="cdc.odg.public.model_cards", num_partitions=3, replication_factor=1),
            NewTopic(name="cdc.odg.public.quality_reports", num_partitions=3, replication_factor=1),
            NewTopic(name="cdc.odg.public.data_contracts", num_partitions=3, replication_factor=1),
            # TimescaleDB CDC topics
            NewTopic(name="cdc.timescale.public.model_performance_ts", num_partitions=5, replication_factor=1),
            NewTopic(name="cdc.timescale.public.quality_metrics_ts", num_partitions=5, replication_factor=1),
            NewTopic(name="cdc.timescale.public.pipeline_metrics_ts", num_partitions=5, replication_factor=1),
            # Kafka Connect internal topics
            NewTopic(name="connect-configs", num_partitions=1, replication_factor=1),
            NewTopic(name="connect-offsets", num_partitions=25, replication_factor=1),
            NewTopic(name="connect-status", num_partitions=5, replication_factor=1),
        ]

        try:
            result = admin_client.create_topics(new_topics=topics, validate_only=False)
            for topic, future in result.items():
                try:
                    future.result()
                    logger.info(f"Created topic: {topic}")
                except Exception as e:
                    if "TopicExistsException" in str(e):
                        logger.info(f"Topic already exists: {topic}")
                    else:
                        logger.error(f"Failed to create topic {topic}: {e}")
        finally:
            admin_client.close()

    def create_connector(self, config_file: Path) -> bool:
        """Create a Debezium connector.

        Args:
            config_file: Path to connector JSON configuration

        Returns:
            True if connector was created successfully, False otherwise
        """
        logger.info(f"Creating connector from {config_file.name}...")

        with open(config_file) as f:
            config = json.load(f)

        connector_name = config["name"]

        # Check if connector already exists
        try:
            response = requests.get(f"{self.kafka_connect_url}/connectors/{connector_name}", timeout=10)
            if response.status_code == 200:
                logger.info(f"Connector {connector_name} already exists, updating...")
                response = requests.put(
                    f"{self.kafka_connect_url}/connectors/{connector_name}/config",
                    json=config["config"],
                    headers={"Content-Type": "application/json"},
                    timeout=10,
                )
            else:
                # Create new connector
                response = requests.post(
                    f"{self.kafka_connect_url}/connectors",
                    json=config,
                    headers={"Content-Type": "application/json"},
                    timeout=10,
                )

            if response.status_code in (200, 201):
                logger.info(f"Successfully created/updated connector: {connector_name}")
                return True
            else:
                logger.error(f"Failed to create connector {connector_name}: {response.text}")
                return False

        except requests.exceptions.RequestException as e:
            logger.error(f"Error creating connector {connector_name}: {e}")
            return False

    def check_connector_status(self, connector_name: str) -> dict:
        """Check status of a connector.

        Args:
            connector_name: Name of the connector

        Returns:
            Connector status dictionary
        """
        try:
            response = requests.get(f"{self.kafka_connect_url}/connectors/{connector_name}/status", timeout=10)
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to get status for {connector_name}: {response.text}")
                return {}
        except requests.exceptions.RequestException as e:
            logger.error(f"Error checking status for {connector_name}: {e}")
            return {}

    def initialize(self) -> bool:
        """Initialize all CDC components.

        Returns:
            True if initialization was successful, False otherwise
        """
        # Step 1: Wait for Kafka Connect
        if not self.wait_for_kafka_connect():
            return False

        # Step 2: Create Kafka topics
        try:
            self.create_cdc_topics()
        except Exception as e:
            logger.error(f"Failed to create Kafka topics: {e}")
            return False

        # Step 3: Create connectors
        connector_files = list(self.connector_configs_dir.glob("*.json"))
        if not connector_files:
            logger.warning(f"No connector configs found in {self.connector_configs_dir}")
            return False

        success = True
        for config_file in connector_files:
            if not self.create_connector(config_file):
                success = False

        # Step 4: Check connector status
        logger.info("\nConnector Status:")
        logger.info("=" * 80)

        response = requests.get(f"{self.kafka_connect_url}/connectors", timeout=10)
        if response.status_code == 200:
            connectors = response.json()
            for connector in connectors:
                status = self.check_connector_status(connector)
                logger.info(f"\n{connector}:")
                logger.info(f"  State: {status.get('connector', {}).get('state', 'UNKNOWN')}")
                for task in status.get("tasks", []):
                    logger.info(f"  Task {task['id']}: {task['state']}")
        else:
            logger.error("Failed to list connectors")
            success = False

        return success


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Initialize CDC connectors for OpenDataGov")
    parser.add_argument("--kafka-connect-url", default="http://kafka-connect:8083", help="Kafka Connect REST API URL")
    parser.add_argument("--kafka-bootstrap-servers", default="kafka:9092", help="Kafka bootstrap servers")
    parser.add_argument(
        "--connector-configs-dir",
        default="../../deploy/helm/opendatagov/charts/kafka-connect/connectors",
        help="Directory containing connector JSON configs",
    )

    args = parser.parse_args()

    initializer = CDCInitializer(
        kafka_connect_url=args.kafka_connect_url,
        kafka_bootstrap_servers=args.kafka_bootstrap_servers,
        connector_configs_dir=args.connector_configs_dir,
    )

    success = initializer.initialize()

    if success:
        logger.info("\n" + "=" * 80)
        logger.info("CDC initialization completed successfully!")
        logger.info("=" * 80)
        sys.exit(0)
    else:
        logger.error("\n" + "=" * 80)
        logger.error("CDC initialization failed!")
        logger.error("=" * 80)
        sys.exit(1)


if __name__ == "__main__":
    main()
