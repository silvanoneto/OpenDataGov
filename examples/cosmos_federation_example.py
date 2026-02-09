"""COSMOS Federation - Complete End-to-End Example.

This example demonstrates:
1. Registering instances in federation
2. Creating data sharing agreements with RACI approval
3. Discovering federated datasets
4. Querying remote dataset metadata
5. Executing federated lineage queries
6. Health checking remote instances
"""

import asyncio
from datetime import datetime, timedelta

from odg_core.federation import FederatedCatalogClient


async def main():
    """Run complete federation example."""
    print("=" * 80)
    print("COSMOS FEDERATION - End-to-End Example")
    print("=" * 80)

    # ========================================================================
    # STEP 1: Register Local Instance
    # ========================================================================
    print("\n📍 STEP 1: Registering local instance...")

    async with FederatedCatalogClient() as client:
        registration = await client.register_instance(
            instance_id="opendatagov-pharma",
            instance_name="OpenDataGov Pharma (EU)",
            graphql_endpoint="https://pharma.opendatagov.example.com/graphql",
            grpc_endpoint="pharma.opendatagov.example.com:50060",
            region="eu-west-1",
            organization="Pharma Corp",
            shared_namespaces=["gold", "platinum"],
        )

        print(f"✅ Registered: {registration['message']}")
        print(f"   Expires: {registration['expires_at']}")

    # ========================================================================
    # STEP 2: Discover Remote Instances
    # ========================================================================
    print("\n🔍 STEP 2: Discovering remote instances...")

    async with FederatedCatalogClient() as client:
        instances = []
        async for instance in client.discover_instances(region="us-east-1"):
            instances.append(instance)
            print(f"   Found: {instance['instance_id']} ({instance['organization']})")
            print(f"          Region: {instance['region']}")
            print(f"          Shared Namespaces: {instance['shared_namespaces']}")

        print(f"\n✅ Discovered {len(instances)} instances")

    # ========================================================================
    # STEP 3: Create Data Sharing Agreement
    # ========================================================================
    print("\n📝 STEP 3: Creating data sharing agreement...")

    async with FederatedCatalogClient() as client:
        agreement = await client.create_sharing_agreement(
            agreement_id="pharma-research-2026",
            source_instance_id="opendatagov-pharma",
            target_instance_id="opendatagov-research",
            shared_datasets=["gold/clinical_trials", "gold/adverse_events", "platinum/drug_efficacy"],
            access_level="metadata_only",  # Only metadata, not raw data
            raci_approvals={
                "responsible": "data_scientist@pharma.com",
                "accountable": "data_architect@pharma.com",
                "consulted": "data_owner@pharma.com",
                "informed": "compliance_officer@pharma.com",
            },
            compliance_frameworks=["HIPAA", "GDPR", "EU AI Act"],
            valid_from=datetime.now(),
            valid_until=datetime.now() + timedelta(days=365),
            created_by="admin@pharma.com",
        )

        print(f"✅ Agreement Created: {agreement['agreement_id']}")
        print(f"   Message: {agreement['message']}")

    # ========================================================================
    # STEP 4: Verify Agreement
    # ========================================================================
    print("\n🔐 STEP 4: Verifying sharing agreement...")

    async with FederatedCatalogClient() as client:
        agreement_details = await client.get_sharing_agreement(agreement_id="pharma-research-2026")

        print(f"   Agreement ID: {agreement_details['agreement_id']}")
        print(f"   Source: {agreement_details['source_instance_id']}")
        print(f"   Target: {agreement_details['target_instance_id']}")
        print(f"   Access Level: {agreement_details['access_level']}")
        print(f"   Shared Datasets: {len(agreement_details['shared_datasets'])}")
        print(f"   Compliance: {', '.join(agreement_details['compliance_frameworks'])}")
        print(f"   Valid Until: {agreement_details['valid_until']}")
        print(f"   Revoked: {agreement_details['revoked']}")

    # ========================================================================
    # STEP 5: Query Remote Dataset Metadata
    # ========================================================================
    print("\n📊 STEP 5: Querying remote dataset metadata...")

    async with FederatedCatalogClient() as client:
        metadata = await client.query_remote_dataset(
            instance_id="opendatagov-pharma",
            dataset_id="gold/clinical_trials",
            agreement_id="pharma-research-2026",
            include_schema=True,
            include_stats=True,
            include_lineage=False,
        )

        print(f"   Dataset: {metadata['dataset_id']}")
        print(f"   Table: {metadata['namespace']}.{metadata['table_name']}")
        print(f"   Row Count: {metadata['row_count']:,}")
        print(f"   Size: {metadata['size_bytes'] / (1024**3):.2f} GB")
        print(f"   Quality Score: {metadata['quality_score']:.2%}")
        print(f"   Owner: {metadata['owner']}")
        print(f"   Tags: {', '.join(metadata['tags'])}")
        print(f"   Snapshots: {metadata['total_snapshots']}")

        if metadata["schema"]:
            print(f"\n   Schema ({len(metadata['schema'])} columns):")
            for col in metadata["schema"][:5]:  # Show first 5 columns
                nullable = "NULL" if col["nullable"] else "NOT NULL"
                print(f"      - {col['name']}: {col['type']} {nullable}")
            if len(metadata["schema"]) > 5:
                print(f"      ... and {len(metadata['schema']) - 5} more columns")

    # ========================================================================
    # STEP 6: Execute Federated Lineage Query
    # ========================================================================
    print("\n🔗 STEP 6: Executing federated lineage query...")

    async with FederatedCatalogClient() as client:
        lineage = await client.federated_lineage_query(
            dataset_id="gold/clinical_trials", max_depth=5, include_remote=True, direction="both"
        )

        print(f"   Graph Size: {lineage['node_count']} nodes, {lineage['edge_count']} edges")

        # Count remote vs local nodes
        remote_nodes = [n for n in lineage["nodes"] if n["instance_id"]]
        local_nodes = [n for n in lineage["nodes"] if not n["instance_id"]]

        print(f"   Local Nodes: {len(local_nodes)}")
        print(f"   Remote Nodes: {len(remote_nodes)}")

        # Show sample nodes
        print("\n   Sample Nodes:")
        for node in lineage["nodes"][:3]:
            location = f"remote ({node['instance_id']})" if node["instance_id"] else "local"
            print(f"      - {node['id']}: {node['label']} ({location})")

        # Count remote edges
        remote_edges = [e for e in lineage["edges"] if e["is_remote"]]
        print(f"\n   Cross-Instance Edges: {len(remote_edges)}")

    # ========================================================================
    # STEP 7: Health Check Remote Instance
    # ========================================================================
    print("\n💓 STEP 7: Health checking remote instance...")

    async with FederatedCatalogClient() as client:
        pong = await client.ping_instance(instance_id="opendatagov-research")

        print(f"   Instance: {pong['instance_id']}")
        print(f"   Status: {pong['status']}")
        print(f"   Latency: {pong['latency_ms']} ms")
        print(f"   Timestamp: {pong['timestamp']}")

    # ========================================================================
    # STEP 8: Revoke Agreement (Optional)
    # ========================================================================
    print("\n🚫 STEP 8: Revoking sharing agreement (optional)...")

    # Uncomment to actually revoke
    # async with FederatedCatalogClient() as client:
    #     await client.revoke_sharing_agreement(
    #         agreement_id="pharma-research-2026",
    #         reason="Research project completed",
    #         revoked_by="admin@pharma.com"
    #     )
    #     print("   ✅ Agreement revoked")

    print("\n   ⏭️  Skipped (uncomment to test)")

    # ========================================================================
    # Summary
    # ========================================================================
    print("\n" + "=" * 80)
    print("✅ COSMOS FEDERATION EXAMPLE COMPLETED")
    print("=" * 80)
    print("\nKey Achievements:")
    print("  ✅ Registered local instance in federation")
    print("  ✅ Discovered remote instances")
    print("  ✅ Created data sharing agreement with RACI approval")
    print("  ✅ Queried remote dataset metadata")
    print("  ✅ Executed federated lineage query")
    print("  ✅ Performed health check")
    print("\nNext Steps:")
    print("  1. Deploy Federation Service to Kubernetes")
    print("  2. Configure mTLS certificates (cert-manager)")
    print("  3. Set up OPA policies for authorization")
    print("  4. Integrate with DataHub for catalog federation")
    print("  5. Extend JanusGraph for remote lineage edges")
    print("\nDocumentation:")
    print("  - ADR-092: docs/adr/092-cosmos-federation.md")
    print("  - Guide: docs/COSMOS_FEDERATION.md")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
