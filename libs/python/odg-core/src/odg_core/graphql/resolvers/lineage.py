"""GraphQL resolvers for lineage queries using JanusGraph."""

from __future__ import annotations

from typing import Any, cast

import strawberry

from odg_core.graph import JanusGraphClient
from odg_core.graphql.types.lineage import (
    DatasetLineageGQL,
    DetailedLineageGraphGQL,
    ImpactAnalysisGQL,
    LineageEdgeGQL,
    LineageNodeGQL,
    ModelLineageGQL,
    PipelineLineageGQL,
)


def _node_dict_to_gql(node: dict[str, Any]) -> LineageNodeGQL:
    """Convert node dictionary to GraphQL type."""
    return LineageNodeGQL(
        id=node.get("id", ""),
        label=node.get("label", ""),
        properties=cast(strawberry.scalars.JSON, node),
    )


def _edge_dict_to_gql(edge: dict[str, Any]) -> LineageEdgeGQL:
    """Convert edge dictionary to GraphQL type."""
    return LineageEdgeGQL(
        id=edge.get("id", ""),
        label=edge.get("label", ""),
        source=str(edge.get("source", "")),
        target=str(edge.get("target", "")),
        properties=cast(strawberry.scalars.JSON, edge),
    )


# ─── Plain resolver functions (not decorated) ─────────────────────────


def resolve_dataset_lineage(dataset_id: str, depth: int = 5) -> DatasetLineageGQL | None:
    """Get complete lineage for a dataset.

    Args:
        dataset_id: Dataset identifier (e.g., "gold/customers")
        depth: Maximum traversal depth

    Returns:
        Dataset lineage information
    """
    client = JanusGraphClient()
    client.connect()

    try:
        upstream = client.get_upstream_datasets(dataset_id, max_depth=depth)
        downstream = client.get_downstream_datasets(dataset_id, max_depth=depth)
        consumers = client.get_dataset_consumers(dataset_id)
        pipelines = consumers.get("pipelines", [])
        models = consumers.get("models", [])

        return DatasetLineageGQL(
            dataset_id=dataset_id,
            layer=dataset_id.split("/")[0] if "/" in dataset_id else "unknown",
            version=None,
            upstream_datasets=[_node_dict_to_gql(n) for n in upstream],
            downstream_datasets=[_node_dict_to_gql(n) for n in downstream],
            generating_pipelines=[_node_dict_to_gql(p) for p in pipelines],
            consuming_models=[_node_dict_to_gql(m) for m in models],
        )

    finally:
        client.disconnect()


def resolve_model_lineage(model_name: str, model_version: int) -> ModelLineageGQL | None:
    """Get complete lineage for a model.

    Args:
        model_name: Model name
        model_version: Model version

    Returns:
        Model lineage information
    """
    client = JanusGraphClient()
    client.connect()

    try:
        lineage = client.get_model_training_lineage(model_name, model_version)

        if not lineage:
            return None

        training_datasets = lineage.get("training_datasets", [])
        upstream_pipelines = lineage.get("upstream_pipelines", [])
        snapshots = [d.get("version", "") for d in training_datasets if d.get("version")]

        return ModelLineageGQL(
            model_name=model_name,
            model_version=model_version,
            framework=lineage.get("model", {}).get("framework"),
            training_datasets=[_node_dict_to_gql(d) for d in training_datasets],
            upstream_pipelines=[_node_dict_to_gql(p) for p in upstream_pipelines],
            dataset_snapshots=snapshots,
        )

    finally:
        client.disconnect()


def resolve_pipeline_lineage(pipeline_id: str, pipeline_version: int | None = None) -> PipelineLineageGQL | None:
    """Get lineage for a pipeline.

    Args:
        pipeline_id: Pipeline identifier
        pipeline_version: Pipeline version (optional, uses latest if not provided)

    Returns:
        Pipeline lineage information
    """
    client = JanusGraphClient()
    client.connect()

    try:
        outputs = client.get_pipeline_outputs(pipeline_id)

        return PipelineLineageGQL(
            pipeline_id=pipeline_id,
            pipeline_version=pipeline_version or 0,
            pipeline_type="unknown",  # TODO: Get from graph
            input_datasets=[],
            output_datasets=[_node_dict_to_gql(d) for d in outputs],
            downstream_models=[],
        )

    finally:
        client.disconnect()


def resolve_lineage_graph(node_id: str, node_type: str, depth: int = 3) -> DetailedLineageGraphGQL:
    """Get full bidirectional lineage graph.

    Args:
        node_id: Node identifier
        node_type: Node type (Dataset, Model, Pipeline)
        depth: Traversal depth

    Returns:
        Complete lineage graph
    """
    client = JanusGraphClient()
    client.connect()

    try:
        graph = client.get_full_lineage_graph(node_id, node_type, depth)

        return DetailedLineageGraphGQL(
            nodes=[_node_dict_to_gql(n) for n in graph.get("nodes", [])],
            edges=[_edge_dict_to_gql(e) for e in graph.get("edges", [])],
        )

    finally:
        client.disconnect()


def resolve_impact_analysis(dataset_id: str, change_type: str = "schema") -> ImpactAnalysisGQL:
    """Analyze impact of changing a dataset.

    Args:
        dataset_id: Dataset to analyze
        change_type: Type of change (schema, data, removal)

    Returns:
        Impact analysis results
    """
    client = JanusGraphClient()
    client.connect()

    try:
        downstream = client.get_downstream_datasets(dataset_id, max_depth=10)
        consumers = client.get_dataset_consumers(dataset_id)

        target_node = LineageNodeGQL(
            id=dataset_id,
            label="Dataset",
            properties=cast(strawberry.scalars.JSON, {"dataset_id": dataset_id}),
        )

        return ImpactAnalysisGQL(
            target_node=target_node,
            affected_datasets=[_node_dict_to_gql(d) for d in downstream],
            affected_models=[_node_dict_to_gql(m) for m in consumers.get("models", [])],
            affected_pipelines=[_node_dict_to_gql(p) for p in consumers.get("pipelines", [])],
        )

    finally:
        client.disconnect()


def resolve_record_pipeline_execution(
    pipeline_id: str, pipeline_version: int, input_datasets: list[str], output_datasets: list[str]
) -> bool:
    """Record a pipeline execution in the lineage graph.

    Args:
        pipeline_id: Pipeline identifier
        pipeline_version: Pipeline version
        input_datasets: List of input dataset IDs
        output_datasets: List of output dataset IDs

    Returns:
        Success status
    """
    client = JanusGraphClient()
    client.connect()

    try:
        client.add_pipeline(pipeline_id, pipeline_version)

        for output_id in output_datasets:
            client.add_pipeline_generates_dataset(
                pipeline_id=pipeline_id, pipeline_version=pipeline_version, dataset_id=output_id
            )

        # TODO: Record inputs (requires CONSUMES edge)

        return True

    except Exception as e:
        print(f"Error recording pipeline execution: {e}")
        return False

    finally:
        client.disconnect()


def resolve_record_model_training(
    model_name: str,
    model_version: int,
    training_datasets: list[str],
    dataset_versions: list[str] | None = None,
) -> bool:
    """Record model training lineage.

    Args:
        model_name: Model name
        model_version: Model version
        training_datasets: List of dataset IDs used for training
        dataset_versions: List of dataset snapshot IDs (for reproducibility)

    Returns:
        Success status
    """
    client = JanusGraphClient()
    client.connect()

    try:
        client.add_model(model_name, model_version)

        for i, dataset_id in enumerate(training_datasets):
            dataset_version = None
            if dataset_versions and i < len(dataset_versions):
                dataset_version = dataset_versions[i]

            client.add_model_trained_on_dataset(
                model_name=model_name,
                model_version=model_version,
                dataset_id=dataset_id,
                dataset_version=dataset_version or "",
            )

        return True

    except Exception as e:
        print(f"Error recording model training: {e}")
        return False

    finally:
        client.disconnect()


def resolve_record_dataset_promotion(
    source_dataset: str, target_dataset: str, transformation: str | None = None
) -> bool:
    """Record dataset promotion between layers.

    Args:
        source_dataset: Source dataset ID (e.g., "bronze/customers")
        target_dataset: Target dataset ID (e.g., "silver/customers")
        transformation: Description of transformation applied

    Returns:
        Success status
    """
    client = JanusGraphClient()
    client.connect()

    try:
        client.add_dataset_derived_from(
            target_dataset_id=target_dataset, source_dataset_id=source_dataset, transformation=transformation
        )

        return True

    except Exception as e:
        print(f"Error recording dataset promotion: {e}")
        return False

    finally:
        client.disconnect()


# ─── Strawberry types (delegate to plain functions) ────────────────────


@strawberry.type
class LineageQuery:
    """GraphQL queries for data lineage."""

    @strawberry.field
    def dataset_lineage(self, dataset_id: str, depth: int = 5) -> DatasetLineageGQL | None:
        """Get complete lineage for a dataset.

        Example:
            query {
              datasetLineage(datasetId: "gold/customers", depth: 5) {
                datasetId
                layer
                upstreamDatasets { name nodeType }
                downstreamDatasets { name nodeType }
                consumingModels { name properties }
              }
            }
        """
        return resolve_dataset_lineage(dataset_id, depth)

    @strawberry.field
    def model_lineage(self, model_name: str, model_version: int) -> ModelLineageGQL | None:
        """Get complete lineage for a model.

        Example:
            query {
              modelLineage(modelName: "churn_predictor", modelVersion: 5) {
                modelName
                modelVersion
                trainingDatasets { name properties }
                upstreamPipelines { name }
                isReproducible
              }
            }
        """
        return resolve_model_lineage(model_name, model_version)

    @strawberry.field
    def pipeline_lineage(self, pipeline_id: str, pipeline_version: int | None = None) -> PipelineLineageGQL | None:
        """Get lineage for a pipeline.

        Example:
            query {
              pipelineLineage(pipelineId: "spark_aggregate_sales", pipelineVersion: 5) {
                pipelineId
                pipelineType
                outputDatasets { name }
                downstreamModels { name }
              }
            }
        """
        return resolve_pipeline_lineage(pipeline_id, pipeline_version)

    @strawberry.field
    def lineage_graph(self, node_id: str, node_type: str, depth: int = 3) -> DetailedLineageGraphGQL:
        """Get full bidirectional lineage graph.

        Example:
            query {
              lineageGraph(
                nodeId: "gold/customers",
                nodeType: "Dataset",
                depth: 3
              ) {
                nodeCount
                edgeCount
                nodes { id label name }
                edges { label source target }
              }
            }
        """
        return resolve_lineage_graph(node_id, node_type, depth)

    @strawberry.field
    def impact_analysis(self, dataset_id: str, change_type: str = "schema") -> ImpactAnalysisGQL:
        """Analyze impact of changing a dataset.

        Example:
            query {
              impactAnalysis(datasetId: "silver/customers", changeType: "schema") {
                totalAffected
                severity
                affectedModels { name }
                affectedPipelines { name }
              }
            }
        """
        return resolve_impact_analysis(dataset_id, change_type)


@strawberry.type
class LineageMutation:
    """GraphQL mutations for lineage management."""

    @strawberry.mutation
    def record_pipeline_execution(
        self, pipeline_id: str, pipeline_version: int, input_datasets: list[str], output_datasets: list[str]
    ) -> bool:
        """Record a pipeline execution in the lineage graph.

        Example:
            mutation {
              recordPipelineExecution(
                pipelineId: "spark_aggregate_sales",
                pipelineVersion: 5,
                inputDatasets: ["bronze/sales", "bronze/products"],
                outputDatasets: ["silver/sales_aggregated"]
              )
            }
        """
        return resolve_record_pipeline_execution(pipeline_id, pipeline_version, input_datasets, output_datasets)

    @strawberry.mutation
    def record_model_training(
        self,
        model_name: str,
        model_version: int,
        training_datasets: list[str],
        dataset_versions: list[str] | None = None,
    ) -> bool:
        """Record model training lineage.

        Example:
            mutation {
              recordModelTraining(
                modelName: "churn_predictor",
                modelVersion: 5,
                trainingDatasets: ["gold/customers", "gold/transactions"],
                datasetVersions: ["snapshot_abc123", "snapshot_def456"]
              )
            }
        """
        return resolve_record_model_training(model_name, model_version, training_datasets, dataset_versions)

    @strawberry.mutation
    def record_dataset_promotion(
        self, source_dataset: str, target_dataset: str, transformation: str | None = None
    ) -> bool:
        """Record dataset promotion between layers.

        Example:
            mutation {
              recordDatasetPromotion(
                sourceDataset: "bronze/customers",
                targetDataset: "silver/customers",
                transformation: "data quality validation + deduplication"
              )
            }
        """
        return resolve_record_dataset_promotion(source_dataset, target_dataset, transformation)
