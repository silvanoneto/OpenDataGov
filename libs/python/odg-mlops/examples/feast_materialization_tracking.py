#!/usr/bin/env python3
"""Example: Tracking Feast materialization with lineage to source pipelines.

This example demonstrates how to track feature materialization jobs and link
them back to the Spark/Flink pipelines that generated the source data.
"""

from datetime import datetime, timedelta

from feast import FeatureStore
from odg_core.feast import MaterializationTracker, track_feast_materialization


def example_basic_tracking():
    """Basic example: Track materialization with pipeline lineage."""
    print("=== Example 1: Basic Materialization Tracking ===\n")

    # Initialize Feast FeatureStore
    store = FeatureStore(repo_path="./feature_repo")

    # Materialize features for the last 7 days
    end_date = datetime.now()
    start_date = end_date - timedelta(days=7)

    store.materialize(start_date=start_date, end_date=end_date, feature_views=["customer_features"])

    # Track what was materialized with source lineage
    metadata = track_feast_materialization(
        feature_store=store,
        feature_view_name="customer_features",
        source_pipeline_id="spark_aggregate_customers",  # Which pipeline generated the data
        source_pipeline_version=5,  # Version of the pipeline
        source_dataset_id="gold/customers",  # Source dataset
        start_date=start_date,
        end_date=end_date,
    )

    print("Materialization tracked:")
    print(f"  Run ID: {metadata['run_id']}")
    print(f"  Feature View: {metadata['feature_view']}")
    print(f"  Features: {', '.join(metadata['feature_names'])}")
    pipeline_id = metadata["source_pipeline_id"]
    pipeline_ver = metadata["source_pipeline_version"]
    print(f"  Source Pipeline: {pipeline_id} v{pipeline_ver}")
    dataset_id = metadata["source_dataset_id"]
    dataset_ver = metadata["source_dataset_version"]
    print(f"  Source Dataset: {dataset_id} @ {dataset_ver}")
    print()


def example_with_iceberg_snapshot():
    """Example: Track materialization with explicit Iceberg snapshot."""
    print("=== Example 2: Track with Iceberg Snapshot ===\n")

    from odg_core.storage.iceberg_catalog import IcebergCatalog

    store = FeatureStore(repo_path="./feature_repo")
    iceberg = IcebergCatalog()

    # Get current snapshot of source dataset
    source_snapshot = iceberg.get_snapshot_id("gold", "orders")

    # Materialize features
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)

    store.materialize(start_date=start_date, end_date=end_date, feature_views=["order_features"])

    # Track with explicit snapshot ID
    metadata = track_feast_materialization(
        feature_store=store,
        feature_view_name="order_features",
        source_pipeline_id="duckdb_aggregate_orders",
        source_pipeline_version=3,
        source_dataset_id="gold/orders",
        source_dataset_version=source_snapshot,  # Explicit snapshot!
        start_date=start_date,
        end_date=end_date,
    )

    print("Materialization tracked with Iceberg snapshot:")
    print(f"  Feature View: {metadata['feature_view']}")
    print(f"  Source Dataset: {metadata['source_dataset_id']}")
    print(f"  Iceberg Snapshot: {metadata['source_dataset_version']}")
    print()


def example_materialization_history():
    """Example: Query materialization history."""
    print("=== Example 3: Query Materialization History ===\n")

    store = FeatureStore(repo_path="./feature_repo")
    tracker = MaterializationTracker(store)

    # Get last 5 materializations
    history = tracker.get_materialization_history("customer_features", limit=5)

    print(f"Last {len(history)} materializations of 'customer_features':\n")
    for i, record in enumerate(history, 1):
        print(f"{i}. Run ID: {record['run_id']}")
        print(f"   Time: {record['materialization_time']}")
        src_id = record.get("source_pipeline_id", "unknown")
        src_ver = record.get("source_pipeline_version", "?")
        print(f"   Source: {src_id} v{src_ver}")
        ds_id = record.get("source_dataset_id", "unknown")
        ds_ver = record.get("source_dataset_version", "?")
        print(f"   Dataset: {ds_id} @ {ds_ver}")
        print()


def example_feature_freshness_validation():
    """Example: Validate feature freshness before model training."""
    print("=== Example 4: Feature Freshness Validation ===\n")

    store = FeatureStore(repo_path="./feature_repo")
    tracker = MaterializationTracker(store)

    # Before training a model, validate that features are fresh
    validation = tracker.validate_feature_freshness(
        feature_view_name="customer_features",
        max_age_hours=24,  # Features must be < 24 hours old
    )

    if validation["is_fresh"]:
        print(f"✅ Features are FRESH (age: {validation['age_hours']:.1f} hours)")
        print(f"   Last materialization: {validation['last_materialization_time']}")
        pipe_id = validation.get("source_pipeline_id")
        pipe_ver = validation.get("source_pipeline_version")
        print(f"   Source pipeline: {pipe_id} v{pipe_ver}")
        print("\n   Safe to proceed with model training!")
    else:
        print("❌ Features are STALE!")
        print(f"   Reason: {validation.get('reason', 'too old')}")
        age = validation.get("age_hours", "N/A")
        max_age = validation["max_age_hours"]
        print(f"   Age: {age} hours (max: {max_age} hours)")
        print("\n   ⚠️  Re-materialize features before training!")

    print()


def example_integration_with_spark_job():
    """Example: Integrate tracking with Spark job that generates features."""
    print("=== Example 5: Integration with Spark Job ===\n")

    from odg_core.spark.job_versioning import VersionedSparkJob

    # Step 1: Run versioned Spark job that generates features
    print("Step 1: Running Spark job to generate feature data...")

    job = VersionedSparkJob(
        job_name="aggregate_customer_features",
        job_file="jobs/aggregate_customer_features.py",
        input_datasets=["silver/transactions", "silver/customers"],
        output_datasets=["gold/customer_features_source"],
        git_commit="abc123def456",
    )

    job_version = job.register_version()
    print(f"  Spark job version: {job_version}")

    # Simulate Spark execution
    # spark = SparkSession.builder.appName("aggregate_features").getOrCreate()
    # run_id = str(uuid.uuid4())
    # job.track_execution(spark, run_id)
    # ... Spark transformations ...
    # job.emit_lineage()

    print("  ✅ Spark job completed\n")

    # Step 2: Materialize features to Feast
    print("Step 2: Materializing features to Feast...")

    store = FeatureStore(repo_path="./feature_repo")

    end_date = datetime.now()
    start_date = end_date - timedelta(days=1)

    store.materialize(start_date=start_date, end_date=end_date, feature_views=["customer_features"])

    print("  ✅ Features materialized\n")

    # Step 3: Track materialization with lineage to Spark job
    print("Step 3: Tracking materialization lineage...")

    metadata = track_feast_materialization(
        feature_store=store,
        feature_view_name="customer_features",
        source_pipeline_id=job.job_name,  # Link to Spark job!
        source_pipeline_version=job_version,
        source_dataset_id="gold/customer_features_source",
        start_date=start_date,
        end_date=end_date,
    )

    print("  ✅ Lineage tracked:")
    print(f"     Feast FeatureView: {metadata['feature_view']}")
    spark_id = metadata["source_pipeline_id"]
    spark_ver = metadata["source_pipeline_version"]
    print(f"     <- Generated by Spark job: {spark_id} v{spark_ver}")
    src_ds_id = metadata["source_dataset_id"]
    src_ds_ver = metadata["source_dataset_version"]
    print(f"     <- From dataset: {src_ds_id} @ {src_ds_ver}")
    print()

    print("Complete lineage chain:")
    print("  silver/transactions + silver/customers")
    print("    ↓ (Spark job: aggregate_customer_features v5)")
    print("  gold/customer_features_source")
    print("    ↓ (Feast materialization)")
    print("  Feast Online Store (customer_features)")
    print()


def example_debugging_feature_issues():
    """Example: Debug feature issues by tracing back to source."""
    print("=== Example 6: Debugging Feature Issues ===\n")

    store = FeatureStore(repo_path="./feature_repo")
    tracker = MaterializationTracker(store)

    # Scenario: Model performance degraded, need to investigate features
    print("Scenario: Model performance dropped on 2026-02-05")
    print("Question: Which pipeline version generated the features?\n")

    # Get materialization history
    history = tracker.get_materialization_history("customer_features", limit=10)

    # Find materialization around the problem date
    problem_date = datetime(2026, 2, 5)

    for record in history:
        mat_time = datetime.fromisoformat(record["materialization_time"])
        if abs((mat_time - problem_date).days) <= 1:
            print(f"Found materialization on {record['materialization_time']}:")
            r_pipe_id = record.get("source_pipeline_id")
            r_pipe_ver = record.get("source_pipeline_version")
            print(f"  Source Pipeline: {r_pipe_id} v{r_pipe_ver}")
            print(f"  Source Dataset: {record.get('source_dataset_id')}")
            print(f"  Iceberg Snapshot: {record.get('source_dataset_version')}")
            print()
            print(
                "Action: Check if pipeline v{} introduced a bug".format(
                    record.get("source_pipeline_version")
                )
            )
            print("        Compare with previous version using Iceberg time-travel")
            break


if __name__ == "__main__":
    print("=" * 80)
    print("Feast Materialization Tracking Examples")
    print("=" * 80)
    print()

    try:
        example_basic_tracking()
        example_with_iceberg_snapshot()
        example_materialization_history()
        example_feature_freshness_validation()
        example_integration_with_spark_job()
        example_debugging_feature_issues()

        print("=" * 80)
        print("All examples completed successfully!")
        print("=" * 80)

    except Exception as e:
        print(f"\n❌ Error running examples: {e}")
        import traceback

        traceback.print_exc()
