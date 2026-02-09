"""Tests for gRPC server."""

from __future__ import annotations

import grpc
import pytest
from odg_core.proto_gen import governance_pb2, governance_pb2_grpc


@pytest.mark.asyncio
@pytest.mark.skip(reason="Requires running gRPC server - integration test")
async def test_grpc_create_decision() -> None:
    """Test creating a decision via gRPC."""
    # Connect to gRPC server
    async with grpc.aio.insecure_channel("localhost:50051") as channel:
        stub = governance_pb2_grpc.GovernanceServiceStub(channel)  # type: ignore[no-untyped-call]

        # Create decision request
        request = governance_pb2.CreateDecisionRequest(
            decision_type=governance_pb2.DECISION_TYPE_DATA_PROMOTION,
            title="Test Decision via gRPC",
            description="Testing gRPC endpoint",
            domain_id="test-domain",
            created_by="test-user",
        )

        # Call gRPC method
        response = await stub.CreateDecision(request)

        # Verify response
        assert response.title == "Test Decision via gRPC"
        assert response.domain_id == "test-domain"
        assert response.decision_type == governance_pb2.DECISION_TYPE_DATA_PROMOTION


@pytest.mark.asyncio
@pytest.mark.skip(reason="Requires running gRPC server - integration test")
async def test_grpc_list_decisions() -> None:
    """Test listing decisions via gRPC."""
    async with grpc.aio.insecure_channel("localhost:50051") as channel:
        stub = governance_pb2_grpc.GovernanceServiceStub(channel)  # type: ignore[no-untyped-call]

        request = governance_pb2.ListDecisionsRequest(limit=10)

        response = await stub.ListDecisions(request)

        # Should return list (may be empty)
        assert isinstance(response.decisions, list)
        assert response.total_count >= 0


@pytest.mark.asyncio
@pytest.mark.skip(reason="Requires running gRPC server - integration test")
async def test_grpc_server_connectivity() -> None:
    """Test basic connectivity to gRPC server."""
    try:
        async with grpc.aio.insecure_channel("localhost:50051") as channel:
            # Wait for channel to be ready (with timeout)
            await channel.channel_ready()
            assert True  # If we get here, connection succeeded
    except grpc.aio.AioRpcError:
        pytest.fail("Could not connect to gRPC server on localhost:50051")


def test_proto_message_creation() -> None:
    """Test that proto messages can be created (unit test)."""
    # This test doesn't require a running server
    request = governance_pb2.CreateDecisionRequest(
        decision_type=governance_pb2.DECISION_TYPE_DATA_PROMOTION,
        title="Test",
        description="Test description",
        domain_id="test",
        created_by="user",
    )

    assert request.title == "Test"
    assert request.decision_type == governance_pb2.DECISION_TYPE_DATA_PROMOTION


def test_proto_enum_values() -> None:
    """Test proto enum values."""
    assert governance_pb2.DECISION_TYPE_DATA_PROMOTION == 1
    assert governance_pb2.DECISION_STATUS_PENDING == 1
    assert governance_pb2.VOTE_VALUE_APPROVE == 1
