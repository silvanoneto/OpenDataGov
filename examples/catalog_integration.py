"""Example: Automatic Metadata Catalog Integration.

This example demonstrates how OpenDataGov automatically populates DataHub
with metadata through event-driven architecture:

1. Lakehouse Agent promotes dataset (Bronze → Silver → Gold)
2. Kafka event emitted
3. Metadata Ingestion Service consumes event
4. DataHub automatically populated with dataset + lineage
"""

import asyncio

from odg_core.catalog import DataHubClient
from odg_core.catalog.events import get_emitter


async def example_lakehouse_promotion():
    """Example: Automatic metadata ingestion from lakehouse promotion."""
    print("\n=== Example 1: Lakehouse Promotion ===\n")

    # Get catalog event emitter
    emitter = get_emitter(
        kafka_bootstrap_servers="localhost:9092",
        enabled=True,
    )

    # Simulate lakehouse promotion: Bronze → Silver
    print("1. Promoting dataset from Bronze to Silver...")
    emitter.emit_lakehouse_promotion(
        dataset_id="finance/revenue",
        source_layer="bronze",
        target_layer="silver",
        schema=[
            {
                "name": "transaction_id",
                "type": "STRING",
                "description": "Unique transaction ID",
            },
            {
                "name": "amount",
                "type": "DECIMAL",
                "description": "Transaction amount",
            },
            {
                "name": "customer_id",
                "type": "STRING",
                "description": "Customer ID",
                "tags": ["pii"],  # PII detected
            },
            {
                "name": "date",
                "type": "DATE",
                "description": "Transaction date",
            },
        ],
        dq_score=0.96,
        promoted_by="data-engineer@company.com",
    )

    print("   ✓ Event emitted to Kafka topic: odg.lakehouse.promotion")
    print("   ✓ Metadata Ingestion Service will automatically:")
    print("     - Register dataset in DataHub: silver/finance/revenue")
    print("     - Add lineage: bronze/finance/revenue → silver/finance/revenue")
    print("     - Add tags: silver_layer, pii, gdpr")

    # Wait a moment for async processing
    await asyncio.sleep(2)

    # Query DataHub to verify
    print("\n2. Querying DataHub for registered dataset...")
    client = DataHubClient(gms_url="http://localhost:8080")

    results = client.search(
        query="revenue",
        entity_types=["dataset"],
        filters={"layer": "silver"},
    )

    if results:
        print(f"   ✓ Found {len(results)} datasets in DataHub")
        for result in results:
            print(f"     - {result['name']} (URN: {result['urn']})")
    else:
        print("   ⚠ No results yet (metadata ingestion may still be processing)")

    print("\n3. Getting lineage graph...")
    client.get_lineage(
        entity_urn="urn:li:dataset:(urn:li:dataPlatform:s3,silver/finance/revenue,PROD)",
        direction="upstream",
        max_hops=5,
    )

    print("   ✓ Lineage graph retrieved")
    print("     - Shows: Bronze → Silver transformation")


async def example_ml_pipeline():
    """Example: Automatic metadata ingestion from ML pipeline."""
    print("\n=== Example 2: ML Pipeline Lineage ===\n")

    emitter = get_emitter()

    # Simulate MLflow model registration
    print("1. Registering ML model in MLflow...")
    emitter.emit_mlflow_model_registered(
        model_name="customer-churn",
        model_version=3,
        mlflow_run_id="abc123def456",
        training_datasets=["gold/crm/customers"],
        features=["total_purchases", "avg_order_value", "days_since_last_purchase"],
        metrics={"accuracy": 0.92, "f1_score": 0.89, "auc": 0.94},
        tags=["production", "business_critical"],
    )

    print("   ✓ Event emitted to Kafka topic: odg.mlflow.model.registered")
    print("   ✓ Metadata Ingestion Service will automatically:")
    print("     - Register model in DataHub: customer-churn v3")
    print("     - Add lineage: gold/crm/customers → customer-churn v3")
    print("     - Record metrics: accuracy=0.92, f1=0.89")

    await asyncio.sleep(2)

    # Simulate Kubeflow pipeline completion
    print("\n2. Kubeflow pipeline completed...")
    emitter.emit_kubeflow_pipeline_completed(
        pipeline_name="train-customer-churn",
        run_id="xyz789",
        input_datasets=["gold/crm/customers", "gold/features/customer"],
        output_model="customer-churn",
        output_version=3,
    )

    print("   ✓ Event emitted to Kafka topic: odg.kubeflow.pipeline.completed")
    print("   ✓ Metadata Ingestion Service will automatically:")
    print("     - Add pipeline lineage in DataHub")
    print("     - Link input datasets → output model")

    await asyncio.sleep(2)

    # Query DataHub for ML model
    print("\n3. Querying DataHub for ML model...")
    client = DataHubClient(gms_url="http://localhost:8080")

    results = client.search(
        query="customer-churn",
        entity_types=["mlModel"],
    )

    if results:
        print(f"   ✓ Found {len(results)} models in DataHub")

    # Get full lineage: Data → Features → Model
    print("\n4. Getting full ML pipeline lineage...")
    client.get_lineage(
        entity_urn="urn:li:mlModel:(urn:li:dataPlatform:mlflow,customer-churn,3)",
        direction="upstream",
        max_hops=10,
    )

    print("   ✓ Full lineage graph:")
    print("     Bronze → Silver → Gold → Features → Model")


async def example_feast_integration():
    """Example: Automatic metadata ingestion from Feast."""
    print("\n=== Example 3: Feast Feature Store ===\n")

    emitter = get_emitter()

    # Simulate Feast feature materialization
    print("1. Materializing Feast features...")
    emitter.emit_feast_materialization(
        feature_view="customer_features",
        features=[
            {
                "name": "total_purchases",
                "type": "FLOAT",
                "description": "Total number of purchases",
            },
            {
                "name": "avg_order_value",
                "type": "FLOAT",
                "description": "Average order value",
            },
            {
                "name": "days_since_last_purchase",
                "type": "INT64",
                "description": "Days since last purchase",
            },
        ],
        source_dataset="gold/features/customer",
        materialization_interval="1h",
        tags=["online_serving", "production"],
    )

    print("   ✓ Event emitted to Kafka topic: odg.feast.materialization")
    print("   ✓ Metadata Ingestion Service will automatically:")
    print("     - Register feature view in DataHub: customer_features")
    print("     - Add lineage: gold/features/customer → customer_features")
    print("     - Add tags: online_serving, production")

    await asyncio.sleep(2)

    # Query DataHub for feature view
    print("\n2. Querying DataHub for feature view...")
    client = DataHubClient(gms_url="http://localhost:8080")

    results = client.search(
        query="customer_features",
        entity_types=["mlFeatureTable"],
    )

    if results:
        print(f"   ✓ Found {len(results)} feature views in DataHub")


async def example_end_to_end_flow():
    """Example: Complete end-to-end medallion flow with automatic metadata."""
    print("\n=== Example 4: End-to-End Medallion Flow ===\n")

    emitter = get_emitter()
    client = DataHubClient()

    # Step 1: Bronze → Silver
    print("1. Bronze → Silver promotion...")
    emitter.emit_lakehouse_promotion(
        dataset_id="finance/revenue",
        source_layer="bronze",
        target_layer="silver",
        schema=[
            {"name": "id", "type": "STRING"},
            {"name": "amount", "type": "DECIMAL"},
        ],
        dq_score=0.92,
        promoted_by="data-engineer@company.com",
    )

    await asyncio.sleep(1)

    # Step 2: Silver → Gold
    print("2. Silver → Gold promotion...")
    emitter.emit_lakehouse_promotion(
        dataset_id="finance/revenue",
        source_layer="silver",
        target_layer="gold",
        schema=[
            {"name": "id", "type": "STRING"},
            {"name": "amount", "type": "DECIMAL"},
            {"name": "customer_id", "type": "STRING"},
        ],
        dq_score=0.96,
        promoted_by="data-engineer@company.com",
    )

    await asyncio.sleep(1)

    # Step 3: Gold → Feast features
    print("3. Materializing Feast features from Gold...")
    emitter.emit_feast_materialization(
        feature_view="revenue_features",
        features=[{"name": "total_revenue", "type": "FLOAT"}],
        source_dataset="gold/finance/revenue",
        materialization_interval="1h",
    )

    await asyncio.sleep(1)

    # Step 4: Train ML model
    print("4. Training ML model with Gold data...")
    emitter.emit_mlflow_model_registered(
        model_name="revenue-forecast",
        model_version=1,
        mlflow_run_id="run123",
        training_datasets=["gold/finance/revenue"],
        features=["total_revenue"],
        metrics={"rmse": 0.15},
    )

    await asyncio.sleep(2)

    # Step 5: Query complete lineage
    print("\n5. Querying complete lineage graph...")
    client.get_lineage(
        entity_urn="urn:li:mlModel:(urn:li:dataPlatform:mlflow,revenue-forecast,1)",
        direction="upstream",
        max_hops=10,
    )

    print("   ✓ Complete lineage:")
    print("     Bronze → Silver → Gold → Feast → Model")
    print("\n   All metadata automatically registered in DataHub!")


async def main():
    """Run all examples."""
    print("╔════════════════════════════════════════════════════════════╗")
    print("║  OpenDataGov - Automatic Metadata Catalog Integration     ║")
    print("║  Event-Driven DataHub Population                          ║")
    print("╚════════════════════════════════════════════════════════════╝")

    # Run examples
    await example_lakehouse_promotion()
    await example_ml_pipeline()
    await example_feast_integration()
    await example_end_to_end_flow()

    print("\n" + "=" * 60)
    print("Examples completed!")
    print("=" * 60)
    print("\n📊 View metadata in DataHub UI:")
    print("   http://localhost:9002")
    print("\n📈 Visualize lineage graphs:")
    print("   DataHub UI → Search → Select entity → Lineage tab")


if __name__ == "__main__":
    asyncio.run(main())
