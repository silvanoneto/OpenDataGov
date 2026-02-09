"""Tests for odg_core.federation.client module."""

from __future__ import annotations

import sys
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ──── Mock all heavy dependencies ─────────────────────────────
# grpc, grpc.aio, protobuf generated modules need to be mocked
# before importing the client module.

_mock_grpc = MagicMock()
_mock_grpc_aio = MagicMock()
_mock_ssl_channel_credentials = MagicMock()
_mock_grpc.aio = _mock_grpc_aio
_mock_grpc.ssl_channel_credentials = _mock_ssl_channel_credentials
_mock_grpc.local_channel_credentials = MagicMock()

_mock_federation_pb2 = MagicMock()
_mock_federation_pb2_grpc = MagicMock()

_mock_proto_gen = MagicMock()
_mock_proto_gen.federation_pb2 = _mock_federation_pb2
_mock_proto_gen.federation_pb2_grpc = _mock_federation_pb2_grpc

# Set up enum-like attributes
_mock_federation_pb2.INSTANCE_STATUS_ACTIVE = 1
_mock_federation_pb2.ACCESS_LEVEL_METADATA_ONLY = 0
_mock_federation_pb2.ACCESS_LEVEL_READ_ONLY = 1
_mock_federation_pb2.ACCESS_LEVEL_FULL = 2
_mock_federation_pb2.LINEAGE_DIRECTION_UPSTREAM = 0
_mock_federation_pb2.LINEAGE_DIRECTION_DOWNSTREAM = 1
_mock_federation_pb2.LINEAGE_DIRECTION_BOTH = 2
_mock_federation_pb2.InstanceStatus = MagicMock()
_mock_federation_pb2.InstanceStatus.Name = MagicMock(return_value="INSTANCE_STATUS_ACTIVE")
_mock_federation_pb2.AccessLevel = MagicMock()
_mock_federation_pb2.AccessLevel.Name = MagicMock(return_value="ACCESS_LEVEL_METADATA_ONLY")


_modules_to_mock = {
    "grpc": _mock_grpc,
    "grpc.aio": _mock_grpc_aio,
    "odg_core.proto_gen": _mock_proto_gen,
    "odg_core.proto_gen.federation_pb2": _mock_federation_pb2,
    "odg_core.proto_gen.federation_pb2_grpc": _mock_federation_pb2_grpc,
    "google": MagicMock(),
    "google.protobuf": MagicMock(),
    "google.protobuf.timestamp_pb2": MagicMock(),
}


@pytest.fixture(autouse=True)
def mock_grpc_modules() -> Any:
    """Mock gRPC and protobuf modules for all tests."""
    with patch.dict(sys.modules, _modules_to_mock):
        yield


def _make_client() -> Any:
    """Create a FederatedCatalogClient with mocked gRPC channel."""
    from odg_core.federation.client import FederatedCatalogClient

    client = FederatedCatalogClient(endpoint="federation-service:50060")
    return client


# ──── Initialization ─────────────────────────────────────────


class TestFederatedCatalogClientInit:
    """Tests for FederatedCatalogClient initialization."""

    def test_stores_endpoint(self) -> None:
        client = _make_client()
        assert client.endpoint == "federation-service:50060"

    def test_creates_channel_and_stub(self) -> None:
        client = _make_client()
        assert client.channel is not None
        assert client.stub is not None


# ──── register_instance ──────────────────────────────────────


class TestRegisterInstance:
    """Tests for FederatedCatalogClient.register_instance."""

    @pytest.mark.asyncio
    async def test_register_returns_result(self) -> None:
        client = _make_client()

        mock_response = MagicMock()
        mock_response.success = True
        mock_response.message = "Registered"
        mock_response.expires_at = None
        client.stub.RegisterInstance = AsyncMock(return_value=mock_response)

        result = await client.register_instance(
            instance_id="odg-eu",
            instance_name="OpenDataGov EU",
            graphql_endpoint="https://eu.example.com/graphql",
            grpc_endpoint="eu.example.com:50060",
            region="eu-west-1",
            organization="TestOrg",
            shared_namespaces=["gold"],
        )

        assert result["success"] is True
        assert result["message"] == "Registered"
        client.stub.RegisterInstance.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_register_default_namespaces(self) -> None:
        client = _make_client()

        mock_response = MagicMock()
        mock_response.success = True
        mock_response.message = "OK"
        mock_response.expires_at = None
        client.stub.RegisterInstance = AsyncMock(return_value=mock_response)

        await client.register_instance(
            instance_id="odg-us",
            instance_name="US",
            graphql_endpoint="https://us.example.com/graphql",
            grpc_endpoint="us.example.com:50060",
        )

        # Verify the InstanceInfo was called with default shared_namespaces=["gold"]
        call_args = _mock_federation_pb2.InstanceInfo.call_args
        assert call_args[1]["shared_namespaces"] == ["gold"]


# ──── create_sharing_agreement ───────────────────────────────


class TestCreateSharingAgreement:
    """Tests for FederatedCatalogClient.create_sharing_agreement."""

    @pytest.mark.asyncio
    async def test_create_returns_agreement_info(self) -> None:
        client = _make_client()

        mock_response = MagicMock()
        mock_response.success = True
        mock_response.agreement_id = "agreement-123"
        mock_response.message = "Created"
        client.stub.CreateSharingAgreement = AsyncMock(return_value=mock_response)

        result = await client.create_sharing_agreement(
            agreement_id="agreement-123",
            source_instance_id="odg-pharma",
            target_instance_id="odg-research",
            shared_datasets=["gold/clinical_trials"],
            access_level="metadata_only",
        )

        assert result["success"] is True
        assert result["agreement_id"] == "agreement-123"
        client.stub.CreateSharingAgreement.assert_awaited_once()


# ──── get_sharing_agreement ──────────────────────────────────


class TestGetSharingAgreement:
    """Tests for FederatedCatalogClient.get_sharing_agreement."""

    @pytest.mark.asyncio
    async def test_returns_agreement_details(self) -> None:
        client = _make_client()

        mock_agreement = MagicMock()
        mock_agreement.agreement_id = "ag-1"
        mock_agreement.source_instance_id = "src"
        mock_agreement.target_instance_id = "tgt"
        mock_agreement.shared_datasets = ["gold/data"]
        mock_agreement.access_level = 0
        mock_agreement.raci_approvals = {"owner": "alice"}
        mock_agreement.compliance_frameworks = ["GDPR"]
        mock_agreement.encryption_required = True
        mock_agreement.valid_from = MagicMock()
        mock_agreement.valid_from.ToDatetime.return_value = "2026-01-01"
        mock_agreement.valid_until = None
        mock_agreement.revoked = False
        mock_agreement.created_by = "admin"
        client.stub.GetSharingAgreement = AsyncMock(return_value=mock_agreement)

        result = await client.get_sharing_agreement("ag-1")

        assert result["agreement_id"] == "ag-1"
        assert result["source_instance_id"] == "src"
        assert result["encryption_required"] is True
        assert result["revoked"] is False


# ──── revoke_sharing_agreement ───────────────────────────────


class TestRevokeSharingAgreement:
    """Tests for FederatedCatalogClient.revoke_sharing_agreement."""

    @pytest.mark.asyncio
    async def test_calls_stub(self) -> None:
        client = _make_client()
        client.stub.RevokeSharingAgreement = AsyncMock()

        await client.revoke_sharing_agreement(
            agreement_id="ag-1",
            reason="Compliance violation",
            revoked_by="admin",
        )

        client.stub.RevokeSharingAgreement.assert_awaited_once()


# ──── query_remote_dataset ───────────────────────────────────


class TestQueryRemoteDataset:
    """Tests for FederatedCatalogClient.query_remote_dataset."""

    @pytest.mark.asyncio
    async def test_returns_dataset_metadata(self) -> None:
        client = _make_client()

        mock_col = MagicMock()
        mock_col.name = "id"
        mock_col.type = "STRING"
        mock_col.nullable = False
        mock_col.description = "Primary key"

        mock_response = MagicMock()
        mock_response.dataset_id = "gold/customers"
        mock_response.namespace = "gold"
        mock_response.table_name = "customers"
        mock_response.schema = [mock_col]
        mock_response.row_count = 1000
        mock_response.size_bytes = 50000
        mock_response.last_modified = MagicMock()
        mock_response.last_modified.ToDatetime.return_value = "2026-01-15"
        mock_response.current_snapshot_id = "snap-123"
        mock_response.total_snapshots = 5
        mock_response.owner = "data-team"
        mock_response.tags = ["production"]
        mock_response.quality_score = 0.95
        client.stub.QueryRemoteDataset = AsyncMock(return_value=mock_response)

        result = await client.query_remote_dataset(
            instance_id="odg-us",
            dataset_id="gold/customers",
            agreement_id="ag-1",
        )

        assert result["dataset_id"] == "gold/customers"
        assert result["namespace"] == "gold"
        assert result["row_count"] == 1000
        assert result["quality_score"] == 0.95
        assert len(result["schema"]) == 1
        assert result["schema"][0]["name"] == "id"


# ──── federated_lineage_query ────────────────────────────────


class TestFederatedLineageQuery:
    """Tests for FederatedCatalogClient.federated_lineage_query."""

    @pytest.mark.asyncio
    async def test_returns_lineage_graph(self) -> None:
        client = _make_client()

        mock_node = MagicMock()
        mock_node.id = "n1"
        mock_node.label = "Dataset"
        mock_node.instance_id = "odg-us"
        mock_node.remote_url = ""
        mock_node.properties = {"layer": "gold"}

        mock_edge = MagicMock()
        mock_edge.id = "e1"
        mock_edge.label = "DERIVED_FROM"
        mock_edge.source_id = "n1"
        mock_edge.target_id = "n2"
        mock_edge.is_remote = False
        mock_edge.properties = {}

        mock_response = MagicMock()
        mock_response.nodes = [mock_node]
        mock_response.edges = [mock_edge]
        mock_response.node_count = 1
        mock_response.edge_count = 1
        client.stub.FederatedLineageQuery = AsyncMock(return_value=mock_response)

        result = await client.federated_lineage_query(
            dataset_id="gold/customers",
            max_depth=3,
            include_remote=True,
            direction="both",
        )

        assert result["node_count"] == 1
        assert result["edge_count"] == 1
        assert len(result["nodes"]) == 1
        assert result["nodes"][0]["id"] == "n1"
        assert len(result["edges"]) == 1
        assert result["edges"][0]["label"] == "DERIVED_FROM"


# ──── ping_instance ──────────────────────────────────────────


class TestPingInstance:
    """Tests for FederatedCatalogClient.ping_instance."""

    @pytest.mark.asyncio
    async def test_returns_pong(self) -> None:
        client = _make_client()

        mock_response = MagicMock()
        mock_response.instance_id = "odg-eu"
        mock_response.latency_ms = 42
        mock_response.status = 1
        mock_response.timestamp = MagicMock()
        mock_response.timestamp.ToDatetime.return_value = "2026-02-09T00:00:00"
        client.stub.PingInstance = AsyncMock(return_value=mock_response)

        result = await client.ping_instance("odg-eu")

        assert result["instance_id"] == "odg-eu"
        assert result["latency_ms"] == 42


# ──── close / context manager ────────────────────────────────


class TestCloseAndContextManager:
    """Tests for close and async context manager."""

    @pytest.mark.asyncio
    async def test_close_closes_channel(self) -> None:
        client = _make_client()
        client.channel.close = AsyncMock()

        await client.close()

        client.channel.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_async_context_manager(self) -> None:
        from odg_core.federation.client import FederatedCatalogClient

        client = FederatedCatalogClient(endpoint="test:50060")
        client.channel.close = AsyncMock()  # type: ignore[method-assign]

        async with client as c:
            assert c is client

        client.channel.close.assert_awaited_once()
