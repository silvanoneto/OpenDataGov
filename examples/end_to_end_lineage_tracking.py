#!/usr/bin/env python3
"""End-to-end example: Complete lineage tracking workflow.

This example demonstrates the full lifecycle of data versioning and lineage
tracking in OpenDataGov, from data ingestion to model training.

Workflow:
1. Ingest data from external API → Bronze layer
2. Process data with versioned Spark pipeline → Silver layer
3. Aggregate data with versioned DuckDB query → Gold layer
4. Materialize features with Feast
5. Train ML model with lineage tracking
6. Query lineage via GraphQL
"""

import uuid
from datetime import datetime, timedelta

# ═══════════════════════════════════════════════════════════
# STEP 1: Data Ingestion from External API
# ═══════════════════════════════════════════════════════════

print("=" * 80)
print("STEP 1: Ingesting data from external API")
print("=" * 80)

from odg_core.connectors import ConnectorConfig, RESTConnector

# Configure API connector
config = ConnectorConfig(
    connector_type="rest_api",
    source_name="github_repos",
    auth_type="bearer",
    credentials={"token": "ghp_example_token"},
    target_database="bronze",
    target_table="github_repositories",
)

connector = RESTConnector(
    config=config,
    base_url="https://api.github.com",
    endpoint="/orgs/apache/repos",
    pagination_type="link_header",
    records_per_page=100,
)

# Ingest data
print("→ Connecting to GitHub API...")
connector.connect()

print("→ Ingesting Apache repositories...")
result = connector.ingest(limit=500)

print("✅ Ingestion complete:")
print(f"   Records ingested: {result.records_ingested}")
print(f"   Records failed: {result.records_failed}")
print(f"   Success rate: {result.success_rate:.1%}")
print(f"   Duration: {result.duration_seconds:.2f}s")
print()

# ═══════════════════════════════════════════════════════════
# STEP 2: Process data with versioned Spark pipeline
# ═══════════════════════════════════════════════════════════

print("=" * 80)
print("STEP 2: Processing data with versioned Spark pipeline")
print("=" * 80)

from odg_core.spark.job_versioning import VersionedSparkJob
from pyspark.sql import SparkSession

# Create Spark session
spark = (
    SparkSession.builder.appName("process_github_repos")
    .config("spark.sql.extensions", "org.apache.iceberg.spark.extensions.IcebergSparkExtensions")
    .getOrCreate()
)

# Define versioned Spark job
spark_job = VersionedSparkJob(
    job_name="process_github_repos",
    job_file=__file__,
    input_datasets=["bronze/github_repositories"],
    output_datasets=["silver/github_repositories"],
    git_commit="abc123def456",
)

# Register version
job_version = spark_job.register_version()
print(f"→ Spark job version: {job_version}")

# Execute transformation
run_id = str(uuid.uuid4())
print(f"→ Run ID: {run_id}")

spark_job.track_execution(spark, run_id)

# Read from Bronze (CouchDB or PostgreSQL)
print("→ Reading from Bronze layer...")
df_bronze = (
    spark.read.format("jdbc")
    .option("url", "jdbc:postgresql://postgres:5432/odg")
    .option("dbtable", "bronze.github_repositories")
    .load()
)

# Transform: filter, deduplicate, add metadata
print("→ Applying transformations...")
from pyspark.sql import functions as f

df_silver = (
    df_bronze.filter(f.col("stargazers_count") > 100)
    .dropDuplicates(["id"])
    .withColumn("processed_at", f.current_timestamp())
    .withColumn("layer", f.lit("silver"))
)

# Write to Silver (Iceberg)
print("→ Writing to Silver layer (Iceberg)...")
df_silver.write.format("iceberg").mode("overwrite").save("lakehouse.silver.github_repositories")

# Emit lineage
spark_job.emit_lineage()

print("✅ Spark pipeline complete!")
print()

# Record lineage in JanusGraph
from odg_core.graph import JanusGraphClient
from odg_core.storage.iceberg_catalog import IcebergCatalog

graph_client = JanusGraphClient()
graph_client.connect()

iceberg = IcebergCatalog()
silver_snapshot = iceberg.get_snapshot_id("silver", "github_repositories")

print("→ Recording lineage in graph...")
graph_client.add_pipeline_generates_dataset(
    pipeline_id="process_github_repos",
    pipeline_version=job_version,
    dataset_id="silver/github_repositories",
    dataset_version=silver_snapshot,
)

print(f"✅ Lineage recorded (snapshot: {silver_snapshot})")
print()

# ═══════════════════════════════════════════════════════════
# STEP 3: Aggregate data with versioned DuckDB query
# ═══════════════════════════════════════════════════════════

print("=" * 80)
print("STEP 3: Aggregating data with versioned DuckDB query")
print("=" * 80)

import duckdb
from odg_core.duckdb.versioned_query import create_versioned_query

# Define aggregation query
sql_query = """
    SELECT
        language,
        COUNT(*) as repo_count,
        AVG(stargazers_count) as avg_stars,
        SUM(forks_count) as total_forks,
        MAX(updated_at) as latest_update
    FROM github_repositories
    WHERE language IS NOT NULL
    GROUP BY language
    ORDER BY avg_stars DESC
"""

# Create versioned DuckDB job
duckdb_job = create_versioned_query(
    job_name="aggregate_repos_by_language",
    sql_query=sql_query,
    input_tables=["github_repositories"],
    output_table="repo_language_stats",
)

# Register version
duckdb_version = duckdb_job.register_version()
print(f"→ DuckDB query version: {duckdb_version}")

# Execute query
conn = duckdb.connect()

# Load data from Silver layer (Iceberg)
conn.execute("""
    INSTALL iceberg;
    LOAD iceberg;
""")

print("→ Executing aggregation query...")
result_df = duckdb_job.execute(conn, namespace="gold")

print("✅ Aggregation complete:")
print(f"   Languages analyzed: {len(result_df)}")
print(f"   Top language: {result_df.iloc[0]['language']} ({result_df.iloc[0]['avg_stars']:.0f} avg stars)")
print()

# Record lineage
gold_snapshot = iceberg.get_snapshot_id("gold", "repo_language_stats")

graph_client.add_pipeline_generates_dataset(
    pipeline_id="aggregate_repos_by_language",
    pipeline_version=duckdb_version,
    dataset_id="gold/repo_language_stats",
    dataset_version=gold_snapshot,
)

graph_client.add_dataset_derived_from(
    target_dataset_id="gold/repo_language_stats",
    source_dataset_id="silver/github_repositories",
    transformation="Language aggregation with stats",
)

print(f"✅ Lineage recorded (snapshot: {gold_snapshot})")
print()

# ═══════════════════════════════════════════════════════════
# STEP 4: Materialize features with Feast
# ═══════════════════════════════════════════════════════════

print("=" * 80)
print("STEP 4: Materializing features with Feast")
print("=" * 80)

from feast import FeatureStore
from odg_core.feast import track_feast_materialization

# Initialize Feast
store = FeatureStore(repo_path="./feature_repo")

# Materialize features (last 7 days)
end_date = datetime.now()
start_date = end_date - timedelta(days=7)

print("→ Materializing repo_stats features...")
store.materialize(start_date=start_date, end_date=end_date, feature_views=["repo_stats"])

# Track materialization with lineage
metadata = track_feast_materialization(
    feature_store=store,
    feature_view_name="repo_stats",
    source_pipeline_id="aggregate_repos_by_language",
    source_pipeline_version=duckdb_version,
    source_dataset_id="gold/repo_language_stats",
    source_dataset_version=gold_snapshot,
    start_date=start_date,
    end_date=end_date,
)

print("✅ Features materialized:")
print(f"   Feature view: {metadata['feature_view']}")
print(f"   Features: {', '.join(metadata['feature_names'])}")
print(f"   Source dataset: {metadata['source_dataset_id']} @ {metadata['source_dataset_version']}")
print()

# ═══════════════════════════════════════════════════════════
# STEP 5: Train ML model with lineage tracking
# ═══════════════════════════════════════════════════════════

print("=" * 80)
print("STEP 5: Training ML model with lineage tracking")
print("=" * 80)

import mlflow
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split

# Get features from Feast
print("→ Retrieving features from Feast...")
# (simplified - in production would use actual feature retrieval)
features_df = result_df[["language", "avg_stars", "total_forks"]]
features_df["is_popular"] = features_df["avg_stars"] > 1000

X = features_df[["avg_stars", "total_forks"]]
y = features_df["is_popular"]

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2)

# Train model
print("→ Training RandomForest model...")
model = RandomForestClassifier(n_estimators=100, random_state=42)
model.fit(X_train, y_train)

accuracy = model.score(X_test, y_test)
print(f"   Model accuracy: {accuracy:.2%}")

# Log to MLflow
mlflow.set_tracking_uri("http://mlflow:5000")

with mlflow.start_run(run_name="repo_popularity_v1"):
    mlflow.log_param("n_estimators", 100)
    mlflow.log_metric("accuracy", accuracy)
    mlflow.sklearn.log_model(model, "model")

print("✅ Model logged to MLflow")

# Record lineage in graph
graph_client.add_model_trained_on_dataset(
    model_name="repo_popularity_predictor",
    model_version=1,
    dataset_id="gold/repo_language_stats",
    dataset_version=gold_snapshot,  # CRITICAL: Iceberg snapshot for reproducibility!
)

print("✅ Model lineage recorded in graph")
print()

# ═══════════════════════════════════════════════════════════
# STEP 6: Query lineage via GraphQL
# ═══════════════════════════════════════════════════════════

print("=" * 80)
print("STEP 6: Querying lineage via GraphQL")
print("=" * 80)

import requests

graphql_url = "http://governance-engine:8000/graphql"

# Query 1: Model lineage
print("→ Query 1: Model lineage")
query1 = """
query {
  modelLineage(modelName: "repo_popularity_predictor", modelVersion: 1) {
    modelName
    modelVersion
    isReproducible
    trainingDatasets {
      name
      properties
    }
    datasetSnapshots
  }
}
"""

response = requests.post(graphql_url, json={"query": query1})
lineage = response.json()["data"]["modelLineage"]

print(f"   Model: {lineage['modelName']} v{lineage['modelVersion']}")
print(f"   Reproducible: {lineage['isReproducible']}")
print(f"   Training datasets: {[d['name'] for d in lineage['trainingDatasets']]}")
print(f"   Snapshots: {lineage['datasetSnapshots']}")
print()

# Query 2: Dataset lineage
print("→ Query 2: Dataset lineage")
query2 = """
query {
  datasetLineage(datasetId: "gold/repo_language_stats", depth: 5) {
    datasetId
    layer
    upstreamCount
    upstreamDatasets {
      name
    }
    consumingModels {
      name
    }
  }
}
"""

response = requests.post(graphql_url, json={"query": query2})
dataset_lineage = response.json()["data"]["datasetLineage"]

print(f"   Dataset: {dataset_lineage['datasetId']}")
print(f"   Layer: {dataset_lineage['layer']}")
print(f"   Upstream datasets: {[d['name'] for d in dataset_lineage['upstreamDatasets']]}")
print(f"   Consuming models: {[m['name'] for m in dataset_lineage['consumingModels']]}")
print()

# Query 3: Impact analysis
print("→ Query 3: Impact analysis")
query3 = """
query {
  impactAnalysis(datasetId: "silver/github_repositories", changeType: "schema") {
    totalAffected
    severity
    affectedDatasets {
      name
    }
    affectedModels {
      name
    }
  }
}
"""

response = requests.post(graphql_url, json={"query": query3})
impact = response.json()["data"]["impactAnalysis"]

print("   Target: silver/github_repositories")
print(f"   Total affected: {impact['totalAffected']}")
print(f"   Severity: {impact['severity']}")
print(f"   Affected datasets: {[d['name'] for d in impact['affectedDatasets']]}")
print(f"   Affected models: {[m['name'] for m in impact['affectedModels']]}")
print()

# ═══════════════════════════════════════════════════════════
# STEP 7: Time-travel to reproduce model
# ═══════════════════════════════════════════════════════════

print("=" * 80)
print("STEP 7: Reproducing model with time-travel")
print("=" * 80)

# Simulate: 6 months later, need to reproduce the model
print("→ Scenario: Need to reproduce model from 6 months ago")

# Get exact snapshot used for training
print(f"→ Original training snapshot: {gold_snapshot}")

# Time-travel to that snapshot
print("→ Using Iceberg time-travel to retrieve exact training data...")
historical_data = iceberg.time_travel("gold", "repo_language_stats", gold_snapshot)

print("✅ Retrieved historical data:")
print(f"   Rows: {len(historical_data)}")
print(f"   Columns: {list(historical_data.columns)}")

# Retrain with exact same data
print("→ Retraining model with historical data...")
X_historical = historical_data[["avg_stars", "total_forks"]]
y_historical = historical_data["is_popular"]

X_train_h, X_test_h, y_train_h, y_test_h = train_test_split(X_historical, y_historical, test_size=0.2, random_state=42)

model_reproduced = RandomForestClassifier(n_estimators=100, random_state=42)
model_reproduced.fit(X_train_h, y_train_h)

accuracy_reproduced = model_reproduced.score(X_test_h, y_test_h)

print("✅ Model reproduced!")
print(f"   Original accuracy: {accuracy:.2%}")
print(f"   Reproduced accuracy: {accuracy_reproduced:.2%}")
print(f"   Match: {abs(accuracy - accuracy_reproduced) < 0.01}")
print()

# Cleanup
graph_client.disconnect()
spark.stop()

print("=" * 80)
print("COMPLETE END-TO-END LINEAGE WORKFLOW FINISHED!")
print("=" * 80)
print()
print("Summary:")
print("✅ Data ingested from external API")
print("✅ Processed through versioned Spark pipeline")
print("✅ Aggregated with versioned DuckDB query")
print("✅ Features materialized with Feast tracking")
print("✅ Model trained with full lineage")
print("✅ Lineage queried via GraphQL")
print("✅ Model reproduced using Iceberg time-travel")
print()
print("🎉 All data is versioned, tracked, and reproducible!")
