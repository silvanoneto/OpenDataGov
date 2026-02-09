"""Kafka Connect connector manager for Debezium CDC.

Provides programmatic management of Debezium connectors via REST API.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import requests

logger = logging.getLogger(__name__)


class ConnectorManager:
    """Manager for Debezium CDC connectors via Kafka Connect REST API.

    Example:
        >>> manager = ConnectorManager("http://kafka-connect:8083")
        >>> manager.create_connector("postgresql-cdc.json")
        >>> status = manager.get_connector_status("odg-postgresql-cdc")
        >>> print(f"Connector state: {status['connector']['state']}")
    """

    def __init__(self, connect_url: str = "http://localhost:8083"):
        """Initialize connector manager.

        Args:
            connect_url: Kafka Connect REST API URL
        """
        self.connect_url = connect_url.rstrip("/")
        self.base_url = f"{self.connect_url}/connectors"

    def list_connectors(self) -> list[str]:
        """List all registered connectors.

        Returns:
            List of connector names
        """
        try:
            response = requests.get(self.base_url, timeout=10)
            response.raise_for_status()
            connectors: list[str] = response.json()
            return connectors
        except requests.RequestException as e:
            logger.error(f"Failed to list connectors: {e}")
            return []

    def get_connector(self, name: str) -> dict[str, Any] | None:
        """Get connector configuration.

        Args:
            name: Connector name

        Returns:
            Connector configuration or None if not found
        """
        try:
            response = requests.get(f"{self.base_url}/{name}", timeout=10)
            response.raise_for_status()
            result: dict[str, Any] = response.json()
            return result
        except requests.RequestException as e:
            logger.error(f"Failed to get connector {name}: {e}")
            return None

    def get_connector_status(self, name: str) -> dict[str, Any] | None:
        """Get connector status.

        Args:
            name: Connector name

        Returns:
            Connector status including state and tasks
        """
        try:
            response = requests.get(f"{self.base_url}/{name}/status", timeout=10)
            response.raise_for_status()
            status: dict[str, Any] = response.json()
            return status
        except requests.RequestException as e:
            logger.error(f"Failed to get connector status {name}: {e}")
            return None

    def create_connector(self, config_path: str) -> bool:
        """Create a new connector from JSON config file.

        Args:
            config_path: Path to connector configuration JSON file

        Returns:
            True if successful, False otherwise
        """
        try:
            with open(config_path) as f:
                config = json.load(f)

            response = requests.post(
                self.base_url, json=config, headers={"Content-Type": "application/json"}, timeout=30
            )
            response.raise_for_status()

            logger.info(f"Created connector: {config['name']}")
            return True

        except FileNotFoundError:
            logger.error(f"Config file not found: {config_path}")
            return False
        except requests.RequestException as e:
            logger.error(f"Failed to create connector: {e}")
            if e.response is not None and hasattr(e.response, "text"):
                logger.error(f"Response: {e.response.text}")
            return False

    def update_connector(self, name: str, config: dict[str, Any]) -> bool:
        """Update existing connector configuration.

        Args:
            name: Connector name
            config: New configuration

        Returns:
            True if successful, False otherwise
        """
        try:
            response = requests.put(
                f"{self.base_url}/{name}/config", json=config, headers={"Content-Type": "application/json"}, timeout=30
            )
            response.raise_for_status()

            logger.info(f"Updated connector: {name}")
            return True

        except requests.RequestException as e:
            logger.error(f"Failed to update connector {name}: {e}")
            return False

    def delete_connector(self, name: str) -> bool:
        """Delete a connector.

        Args:
            name: Connector name

        Returns:
            True if successful, False otherwise
        """
        try:
            response = requests.delete(f"{self.base_url}/{name}", timeout=30)
            response.raise_for_status()

            logger.info(f"Deleted connector: {name}")
            return True

        except requests.RequestException as e:
            logger.error(f"Failed to delete connector {name}: {e}")
            return False

    def pause_connector(self, name: str) -> bool:
        """Pause a connector.

        Args:
            name: Connector name

        Returns:
            True if successful, False otherwise
        """
        try:
            response = requests.put(f"{self.base_url}/{name}/pause", timeout=30)
            response.raise_for_status()

            logger.info(f"Paused connector: {name}")
            return True

        except requests.RequestException as e:
            logger.error(f"Failed to pause connector {name}: {e}")
            return False

    def resume_connector(self, name: str) -> bool:
        """Resume a paused connector.

        Args:
            name: Connector name

        Returns:
            True if successful, False otherwise
        """
        try:
            response = requests.put(f"{self.base_url}/{name}/resume", timeout=30)
            response.raise_for_status()

            logger.info(f"Resumed connector: {name}")
            return True

        except requests.RequestException as e:
            logger.error(f"Failed to resume connector {name}: {e}")
            return False

    def restart_connector(self, name: str) -> bool:
        """Restart a connector.

        Args:
            name: Connector name

        Returns:
            True if successful, False otherwise
        """
        try:
            response = requests.post(f"{self.base_url}/{name}/restart", timeout=30)
            response.raise_for_status()

            logger.info(f"Restarted connector: {name}")
            return True

        except requests.RequestException as e:
            logger.error(f"Failed to restart connector {name}: {e}")
            return False

    def get_connector_topics(self, name: str) -> list[str]:
        """Get list of topics used by a connector.

        Args:
            name: Connector name

        Returns:
            List of Kafka topic names
        """
        try:
            response = requests.get(f"{self.base_url}/{name}/topics", timeout=10)
            response.raise_for_status()
            result = response.json()
            topics: list[str] = result.get(name, {}).get("topics", [])
            return topics

        except requests.RequestException as e:
            logger.error(f"Failed to get topics for connector {name}: {e}")
            return []

    def health_check(self) -> bool:
        """Check if Kafka Connect is healthy.

        Returns:
            True if healthy, False otherwise
        """
        try:
            response = requests.get(self.connect_url, timeout=5)
            response.raise_for_status()
            return True
        except requests.RequestException:
            return False
