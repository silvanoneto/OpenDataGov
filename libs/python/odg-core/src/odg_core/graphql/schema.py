"""Root GraphQL schema for OpenDataGov (ADR-090)."""

import uuid

import strawberry
from sqlalchemy.ext.asyncio import AsyncSession
from strawberry.types import Info

from odg_core.graphql.resolvers import dataset as dataset_resolvers
from odg_core.graphql.resolvers import decision as decision_resolvers
from odg_core.graphql.resolvers import quality as quality_resolvers
from odg_core.graphql.resolvers.lineage import (
    resolve_dataset_lineage,
    resolve_impact_analysis,
    resolve_lineage_graph,
    resolve_model_lineage,
    resolve_pipeline_lineage,
    resolve_record_dataset_promotion,
    resolve_record_model_training,
    resolve_record_pipeline_execution,
)
from odg_core.graphql.types.dataset import DatasetGQL, LineageGraphGQL
from odg_core.graphql.types.decision import GovernanceDecisionGQL
from odg_core.graphql.types.lineage import (
    DatasetLineageGQL,
    DetailedLineageGraphGQL,
    ImpactAnalysisGQL,
    ModelLineageGQL,
    PipelineLineageGQL,
)
from odg_core.graphql.types.quality import QualityReportGQL


@strawberry.type
class Query:
    """Root query type for OpenDataGov GraphQL API."""

    @strawberry.field
    async def decision(self, info: Info, id: uuid.UUID) -> GovernanceDecisionGQL | None:
        """Get a single governance decision by ID."""
        session: AsyncSession = info.context["db_session"]
        return await decision_resolvers.get_decision(session, id)

    @strawberry.field
    async def decisions(
        self,
        info: Info,
        domain: str | None = None,
        status: str | None = None,
        limit: int = 10,
    ) -> list[GovernanceDecisionGQL]:
        """List governance decisions with optional filters."""
        session: AsyncSession = info.context["db_session"]
        return await decision_resolvers.list_decisions(session, domain, status, limit)

    @strawberry.field
    async def dataset(self, info: Info, id: uuid.UUID) -> DatasetGQL | None:
        """Get a single dataset by ID."""
        session: AsyncSession = info.context["db_session"]
        return await dataset_resolvers.get_dataset(session, id)

    @strawberry.field
    async def datasets(
        self,
        info: Info,
        domain: str | None = None,
        layer: str | None = None,
        limit: int = 10,
    ) -> list[DatasetGQL]:
        """List datasets with optional filters."""
        session: AsyncSession = info.context["db_session"]
        return await dataset_resolvers.list_datasets(session, domain, layer, limit)

    @strawberry.field
    async def lineage(
        self,
        info: Info,
        dataset_id: uuid.UUID,
        depth: int = 3,
    ) -> LineageGraphGQL | None:
        """Get lineage graph for a dataset."""
        session: AsyncSession = info.context["db_session"]
        return await dataset_resolvers.get_lineage_graph(session, dataset_id, depth)

    @strawberry.field
    async def quality_report(self, info: Info, dataset_id: str) -> QualityReportGQL | None:
        """Get latest quality report for a dataset."""
        session: AsyncSession = info.context["db_session"]
        return await quality_resolvers.get_quality_report(session, dataset_id)

    # ─── Lineage Queries (JanusGraph) ───────────────────────

    @strawberry.field
    def dataset_lineage(self, dataset_id: str, depth: int = 5) -> DatasetLineageGQL | None:
        """Get complete lineage for a dataset using JanusGraph.

        Example:
            query {
              datasetLineage(datasetId: "gold/customers") {
                upstreamDatasets { name }
                downstreamDatasets { name }
                consumingModels { name }
              }
            }
        """
        return resolve_dataset_lineage(dataset_id, depth)

    @strawberry.field
    def model_lineage(self, model_name: str, model_version: int) -> ModelLineageGQL | None:
        """Get complete lineage for a model including training datasets.

        Example:
            query {
              modelLineage(modelName: "churn_predictor", modelVersion: 5) {
                trainingDatasets { name properties }
                isReproducible
              }
            }
        """
        return resolve_model_lineage(model_name, model_version)

    @strawberry.field
    def pipeline_lineage(self, pipeline_id: str, pipeline_version: int | None = None) -> PipelineLineageGQL | None:
        """Get lineage for a pipeline execution.

        Example:
            query {
              pipelineLineage(pipelineId: "spark_aggregate_sales") {
                outputDatasets { name }
              }
            }
        """
        return resolve_pipeline_lineage(pipeline_id, pipeline_version)

    @strawberry.field
    def lineage_graph(self, node_id: str, node_type: str, depth: int = 3) -> DetailedLineageGraphGQL:
        """Get full bidirectional lineage graph for visualization.

        Example:
            query {
              lineageGraph(nodeId: "gold/customers", nodeType: "Dataset", depth: 3) {
                nodeCount
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
              impactAnalysis(datasetId: "silver/customers") {
                totalAffected
                severity
                affectedModels { name }
              }
            }
        """
        return resolve_impact_analysis(dataset_id, change_type)


@strawberry.type
class Mutation:
    """Root mutation type for OpenDataGov GraphQL API."""

    @strawberry.mutation
    def record_pipeline_execution(
        self, pipeline_id: str, pipeline_version: int, input_datasets: list[str], output_datasets: list[str]
    ) -> bool:
        """Record pipeline execution lineage."""
        return resolve_record_pipeline_execution(pipeline_id, pipeline_version, input_datasets, output_datasets)

    @strawberry.mutation
    def record_model_training(
        self,
        model_name: str,
        model_version: int,
        training_datasets: list[str],
        dataset_versions: list[str] | None = None,
    ) -> bool:
        """Record model training lineage."""
        return resolve_record_model_training(model_name, model_version, training_datasets, dataset_versions)

    @strawberry.mutation
    def record_dataset_promotion(
        self, source_dataset: str, target_dataset: str, transformation: str | None = None
    ) -> bool:
        """Record dataset promotion between layers."""
        return resolve_record_dataset_promotion(source_dataset, target_dataset, transformation)


schema = strawberry.Schema(query=Query, mutation=Mutation)
