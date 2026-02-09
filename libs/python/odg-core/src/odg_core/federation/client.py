"""COSMOS Federation client for multi-instance data sharing."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any

import grpc
from grpc import ssl_channel_credentials

from odg_core.proto_gen import federation_pb2, federation_pb2_grpc

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = logging.getLogger(__name__)


class FederatedCatalogClient:
    """Client for interacting with COSMOS Federation Service."""

    def __init__(
        self,
        endpoint: str = "federation-service:50060",
        cert_file: str | None = None,
        key_file: str | None = None,
        ca_cert_file: str | None = None,
    ):
        """Initialize federation client with mTLS.

        Args:
            endpoint: Federation service gRPC endpoint
            cert_file: Client certificate file path
            key_file: Client private key file path
            ca_cert_file: CA certificate file path
        """
        self.endpoint = endpoint

        # Setup mTLS credentials
        if cert_file and key_file and ca_cert_file:
            with open(cert_file, "rb") as f:
                client_cert = f.read()
            with open(key_file, "rb") as f:
                client_key = f.read()
            with open(ca_cert_file, "rb") as f:
                ca_cert = f.read()

            credentials = ssl_channel_credentials(
                root_certificates=ca_cert, private_key=client_key, certificate_chain=client_cert
            )
        else:
            # Insecure for development
            credentials = grpc.local_channel_credentials()

        self.channel = grpc.aio.secure_channel(endpoint, credentials)
        self.stub = federation_pb2_grpc.FederationServiceStub(self.channel)  # type: ignore[no-untyped-call]

    async def register_instance(
        self,
        instance_id: str,
        instance_name: str,
        graphql_endpoint: str,
        grpc_endpoint: str,
        region: str = "local",
        organization: str = "Default",
        shared_namespaces: list[str] | None = None,
    ) -> dict[str, Any]:
        """Register this instance in the federation registry.

        Args:
            instance_id: Unique instance identifier
            instance_name: Human-readable name
            graphql_endpoint: GraphQL API URL
            grpc_endpoint: gRPC API URL
            region: Deployment region
            organization: Organization name
            shared_namespaces: Namespaces available for sharing

        Returns:
            Registration response

        Example:
            >>> client = FederatedCatalogClient()
            >>> response = await client.register_instance(
            ...     instance_id="opendatagov-eu",
            ...     instance_name="OpenDataGov EU",
            ...     graphql_endpoint="https://eu.opendatagov.example.com/graphql",
            ...     grpc_endpoint="eu.opendatagov.example.com:50060",
            ...     region="eu-west-1",
            ...     shared_namespaces=["gold", "platinum"]
            ... )
        """
        if shared_namespaces is None:
            shared_namespaces = ["gold"]

        request = federation_pb2.InstanceInfo(
            instance_id=instance_id,
            instance_name=instance_name,
            graphql_endpoint=graphql_endpoint,
            grpc_endpoint=grpc_endpoint,
            region=region,
            organization=organization,
            shared_namespaces=shared_namespaces,
            status=federation_pb2.INSTANCE_STATUS_ACTIVE,
        )

        response = await self.stub.RegisterInstance(request)

        logger.info(f"Registered instance {instance_id}: {response.message}")

        return {
            "success": response.success,
            "message": response.message,
            "expires_at": response.expires_at.ToDatetime() if response.expires_at else None,
        }

    async def discover_instances(
        self, region: str | None = None, organization: str | None = None
    ) -> AsyncIterator[dict[str, Any]]:
        """Discover federated instances.

        Args:
            region: Filter by region (optional)
            organization: Filter by organization (optional)

        Yields:
            Instance information dictionaries

        Example:
            >>> client = FederatedCatalogClient()
            >>> async for instance in client.discover_instances(region="eu-west-1"):
            ...     print(f"Found instance: {instance['instance_id']}")
        """
        request = federation_pb2.DiscoveryRequest(region=region or "", organization=organization or "")

        async for instance in self.stub.DiscoverInstances(request):
            yield {
                "instance_id": instance.instance_id,
                "instance_name": instance.instance_name,
                "graphql_endpoint": instance.graphql_endpoint,
                "grpc_endpoint": instance.grpc_endpoint,
                "region": instance.region,
                "organization": instance.organization,
                "shared_namespaces": list(instance.shared_namespaces),
                "status": federation_pb2.InstanceStatus.Name(instance.status),
                "registered_at": instance.registered_at.ToDatetime() if instance.registered_at else None,
            }

    async def create_sharing_agreement(
        self,
        agreement_id: str,
        source_instance_id: str,
        target_instance_id: str,
        shared_datasets: list[str],
        access_level: str = "metadata_only",
        raci_approvals: dict[str, str] | None = None,
        compliance_frameworks: list[str] | None = None,
        valid_from: datetime | None = None,
        valid_until: datetime | None = None,
        created_by: str = "system",
    ) -> dict[str, Any]:
        """Create a data sharing agreement.

        Args:
            agreement_id: Unique agreement identifier
            source_instance_id: Instance sharing data
            target_instance_id: Instance consuming data
            shared_datasets: Dataset IDs allowed
            access_level: "metadata_only", "read_only", or "full"
            raci_approvals: RACI role -> approver mapping
            compliance_frameworks: Required compliance frameworks
            valid_from: Agreement start date
            valid_until: Agreement end date (optional)
            created_by: Creator email/username

        Returns:
            Agreement response

        Example:
            >>> agreement = await client.create_sharing_agreement(
            ...     agreement_id="pharma-research-2026",
            ...     source_instance_id="opendatagov-pharma",
            ...     target_instance_id="opendatagov-research",
            ...     shared_datasets=["gold/clinical_trials"],
            ...     access_level="metadata_only",
            ...     compliance_frameworks=["HIPAA", "GDPR"],
            ...     valid_until=datetime(2027, 2, 1)
            ... )
        """
        if raci_approvals is None:
            raci_approvals = {}
        if compliance_frameworks is None:
            compliance_frameworks = []
        if valid_from is None:
            valid_from = datetime.now()

        # Map access level string to enum
        access_level_map = {
            "metadata_only": federation_pb2.ACCESS_LEVEL_METADATA_ONLY,
            "read_only": federation_pb2.ACCESS_LEVEL_READ_ONLY,
            "full": federation_pb2.ACCESS_LEVEL_FULL,
        }

        from google.protobuf.timestamp_pb2 import Timestamp

        valid_from_ts = Timestamp()
        valid_from_ts.FromDatetime(valid_from)

        valid_until_ts = None
        if valid_until:
            valid_until_ts = Timestamp()
            valid_until_ts.FromDatetime(valid_until)

        request = federation_pb2.SharingAgreement(
            agreement_id=agreement_id,
            source_instance_id=source_instance_id,
            target_instance_id=target_instance_id,
            shared_datasets=shared_datasets,
            access_level=access_level_map.get(access_level, federation_pb2.ACCESS_LEVEL_METADATA_ONLY),
            raci_approvals=raci_approvals,
            compliance_frameworks=compliance_frameworks,
            encryption_required=True,
            valid_from=valid_from_ts,
            valid_until=valid_until_ts,
            created_by=created_by,
        )

        response = await self.stub.CreateSharingAgreement(request)

        logger.info(f"Created sharing agreement {response.agreement_id}")

        return {"success": response.success, "agreement_id": response.agreement_id, "message": response.message}

    async def get_sharing_agreement(self, agreement_id: str) -> dict[str, Any]:
        """Get sharing agreement details.

        Args:
            agreement_id: Agreement identifier

        Returns:
            Agreement details
        """
        request = federation_pb2.GetAgreementRequest(agreement_id=agreement_id)
        agreement = await self.stub.GetSharingAgreement(request)

        return {
            "agreement_id": agreement.agreement_id,
            "source_instance_id": agreement.source_instance_id,
            "target_instance_id": agreement.target_instance_id,
            "shared_datasets": list(agreement.shared_datasets),
            "access_level": federation_pb2.AccessLevel.Name(agreement.access_level),
            "raci_approvals": dict(agreement.raci_approvals),
            "compliance_frameworks": list(agreement.compliance_frameworks),
            "encryption_required": agreement.encryption_required,
            "valid_from": agreement.valid_from.ToDatetime() if agreement.valid_from else None,
            "valid_until": agreement.valid_until.ToDatetime() if agreement.valid_until else None,
            "revoked": agreement.revoked,
            "created_by": agreement.created_by,
        }

    async def revoke_sharing_agreement(self, agreement_id: str, reason: str, revoked_by: str) -> None:
        """Revoke a sharing agreement.

        Args:
            agreement_id: Agreement to revoke
            reason: Reason for revocation
            revoked_by: User revoking the agreement
        """
        request = federation_pb2.RevokeRequest(agreement_id=agreement_id, reason=reason, revoked_by=revoked_by)

        await self.stub.RevokeSharingAgreement(request)
        logger.info(f"Revoked agreement {agreement_id}: {reason}")

    async def query_remote_dataset(
        self,
        instance_id: str,
        dataset_id: str,
        agreement_id: str,
        include_schema: bool = True,
        include_stats: bool = True,
        include_lineage: bool = False,
    ) -> dict[str, Any]:
        """Query metadata from a remote dataset.

        Args:
            instance_id: Remote instance identifier
            dataset_id: Dataset ID (e.g., "gold/customers")
            agreement_id: Sharing agreement ID for authorization
            include_schema: Include schema information
            include_stats: Include statistics
            include_lineage: Include lineage graph

        Returns:
            Dataset metadata

        Example:
            >>> metadata = await client.query_remote_dataset(
            ...     instance_id="opendatagov-us",
            ...     dataset_id="gold/customers",
            ...     agreement_id="cross-region-2026"
            ... )
            >>> print(f"Rows: {metadata['row_count']}, Quality: {metadata['quality_score']}")
        """
        request = federation_pb2.RemoteDatasetRequest(
            instance_id=instance_id,
            dataset_id=dataset_id,
            agreement_id=agreement_id,
            include_schema=include_schema,
            include_stats=include_stats,
            include_lineage=include_lineage,
        )

        response = await self.stub.QueryRemoteDataset(request)

        return {
            "dataset_id": response.dataset_id,
            "namespace": response.namespace,
            "table_name": response.table_name,
            "schema": [
                {"name": col.name, "type": col.type, "nullable": col.nullable, "description": col.description}
                for col in response.schema
            ]
            if include_schema
            else None,
            "row_count": response.row_count if include_stats else None,
            "size_bytes": response.size_bytes if include_stats else None,
            "last_modified": response.last_modified.ToDatetime() if response.last_modified else None,
            "current_snapshot_id": response.current_snapshot_id,
            "total_snapshots": response.total_snapshots,
            "owner": response.owner,
            "tags": list(response.tags),
            "quality_score": response.quality_score,
        }

    async def federated_lineage_query(
        self, dataset_id: str, max_depth: int = 5, include_remote: bool = True, direction: str = "both"
    ) -> dict[str, Any]:
        """Execute federated lineage query across instances.

        Args:
            dataset_id: Starting dataset ID
            max_depth: Maximum traversal depth
            include_remote: Include cross-instance edges
            direction: "upstream", "downstream", or "both"

        Returns:
            Lineage graph

        Example:
            >>> lineage = await client.federated_lineage_query(
            ...     dataset_id="gold/customers_global",
            ...     include_remote=True
            ... )
            >>> print(f"Graph has {lineage['node_count']} nodes, {lineage['edge_count']} edges")
        """
        direction_map = {
            "upstream": federation_pb2.LINEAGE_DIRECTION_UPSTREAM,
            "downstream": federation_pb2.LINEAGE_DIRECTION_DOWNSTREAM,
            "both": federation_pb2.LINEAGE_DIRECTION_BOTH,
        }

        request = federation_pb2.LineageRequest(
            dataset_id=dataset_id,
            max_depth=max_depth,
            include_remote=include_remote,
            direction=direction_map.get(direction, federation_pb2.LINEAGE_DIRECTION_BOTH),
        )

        response = await self.stub.FederatedLineageQuery(request)

        return {
            "nodes": [
                {
                    "id": node.id,
                    "label": node.label,
                    "instance_id": node.instance_id,
                    "remote_url": node.remote_url,
                    "properties": dict(node.properties),
                }
                for node in response.nodes
            ],
            "edges": [
                {
                    "id": edge.id,
                    "label": edge.label,
                    "source_id": edge.source_id,
                    "target_id": edge.target_id,
                    "is_remote": edge.is_remote,
                    "properties": dict(edge.properties),
                }
                for edge in response.edges
            ],
            "node_count": response.node_count,
            "edge_count": response.edge_count,
        }

    async def ping_instance(self, instance_id: str) -> dict[str, Any]:
        """Ping a remote instance for health check.

        Args:
            instance_id: Instance to ping

        Returns:
            Pong response with latency
        """
        from google.protobuf.timestamp_pb2 import Timestamp

        now_ts = Timestamp()
        now_ts.FromDatetime(datetime.now())

        request = federation_pb2.PingRequest(instance_id=instance_id, timestamp=now_ts)

        response = await self.stub.PingInstance(request)

        return {
            "instance_id": response.instance_id,
            "latency_ms": response.latency_ms,
            "status": federation_pb2.InstanceStatus.Name(response.status),
            "timestamp": response.timestamp.ToDatetime() if response.timestamp else None,
        }

    async def close(self) -> None:
        """Close the gRPC channel."""
        await self.channel.close()

    async def __aenter__(self) -> FederatedCatalogClient:
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()
