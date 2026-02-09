"""Tests for NATS event publisher."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from governance_engine.events.publisher import NATSPublisher


@pytest.mark.asyncio
async def test_nats_publisher_connect_success() -> None:
    """Test successful connection to NATS."""
    publisher = NATSPublisher()

    mock_nc = AsyncMock()
    mock_nc.is_closed = False
    mock_js = AsyncMock()
    # jetstream() returns a context synchronously in nats-py
    mock_nc.jetstream = MagicMock(return_value=mock_js)

    with patch("nats.connect", return_value=mock_nc):
        await publisher.connect("nats://localhost:4222")

    assert publisher.is_connected is True
    mock_js.add_stream.assert_called_once()


@pytest.mark.asyncio
async def test_nats_publisher_connect_failure() -> None:
    """Test connection failure."""
    publisher = NATSPublisher()

    with patch("nats.connect", side_effect=Exception("Connection failed")):
        await publisher.connect("nats://localhost:4222")

    assert publisher.is_connected is False


@pytest.mark.asyncio
async def test_nats_publisher_publish() -> None:
    """Test publishing an event."""
    publisher = NATSPublisher()

    # Mock connected state
    publisher._nc = AsyncMock()
    publisher._nc.is_closed = False
    publisher._js = AsyncMock()

    await publisher.publish("decision_created", {"id": "123"})

    publisher._js.publish.assert_called_once()
    subject = publisher._js.publish.call_args[0][0]
    assert subject == "governance.decisions.created"


@pytest.mark.asyncio
async def test_nats_publisher_publish_not_connected() -> None:
    """Test publish skip when not connected."""
    publisher = NATSPublisher()
    assert publisher._js is None

    await publisher.publish("decision_created", {"id": "123"})
    # Should not raise exception


@pytest.mark.asyncio
async def test_nats_publisher_disconnect() -> None:
    """Test disconnect."""
    publisher = NATSPublisher()
    mock_nc = AsyncMock()
    mock_nc.is_closed = False
    publisher._nc = mock_nc

    await publisher.disconnect()
    mock_nc.close.assert_called_once()


@pytest.mark.asyncio
async def test_nats_publisher_publish_unknown_subject() -> None:
    """Test publish with unknown subject key."""
    publisher = NATSPublisher()
    publisher._js = AsyncMock()

    await publisher.publish("unknown_key", {"data": 1})
    publisher._js.publish.assert_not_called()


@pytest.mark.asyncio
async def test_nats_publisher_publish_with_trace() -> None:
    """Test publish with trace headers."""
    publisher = NATSPublisher()
    publisher._js = AsyncMock()

    with patch("odg_core.telemetry.context.get_trace_headers", return_value={"trace": "123"}):
        await publisher.publish("decision_created", {"data": 1})

    args, _ = publisher._js.publish.call_args
    payload = json.loads(args[1].decode())
    assert payload["_trace"] == {"trace": "123"}


@pytest.mark.asyncio
async def test_nats_publisher_publish_error() -> None:
    """Test publish handling exception."""
    publisher = NATSPublisher()
    publisher._js = AsyncMock()
    publisher._js.publish.side_effect = Exception("Publish fail")

    # Should not raise exception
    await publisher.publish("decision_created", {"data": 1})
