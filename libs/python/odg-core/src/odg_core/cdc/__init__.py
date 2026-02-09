"""CDC (Change Data Capture) integration for OpenDataGov.

Provides utilities for managing Debezium connectors and consuming CDC events.
"""

from odg_core.cdc.cdc_consumer import CDCConsumer, CDCEvent
from odg_core.cdc.connector_manager import ConnectorManager

__all__ = [
    "CDCConsumer",
    "CDCEvent",
    "ConnectorManager",
]
