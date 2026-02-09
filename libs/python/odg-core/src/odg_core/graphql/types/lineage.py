"""GraphQL types for data lineage queries."""

import strawberry


@strawberry.type
class LineageNodeGQL:
    """A node in the lineage graph."""

    id: str
    label: str  # Dataset, Pipeline, Model, Feature
    properties: strawberry.scalars.JSON

    @strawberry.field
    def node_type(self) -> str:
        """Get the type of this node."""
        return self.label

    @strawberry.field
    def name(self) -> str:
        """Get the name of this node."""
        props: dict[str, str] = self.properties if isinstance(self.properties, dict) else {}
        return (
            props.get("dataset_id")
            or props.get("model_name")
            or props.get("pipeline_id")
            or props.get("feature_view")
            or ""
        )


@strawberry.type
class LineageEdgeGQL:
    """An edge in the lineage graph."""

    id: str
    label: str  # DERIVED_FROM, TRAINED_ON, GENERATED_BY, etc.
    source: str
    target: str
    properties: strawberry.scalars.JSON | None = None

    @strawberry.field
    def edge_type(self) -> str:
        """Get the type of this edge."""
        return self.label


@strawberry.type
class DetailedLineageGraphGQL:
    """A lineage graph with nodes and edges."""

    nodes: list[LineageNodeGQL]
    edges: list[LineageEdgeGQL]

    @strawberry.field
    def node_count(self) -> int:
        """Total number of nodes in the graph."""
        return len(self.nodes)

    @strawberry.field
    def edge_count(self) -> int:
        """Total number of edges in the graph."""
        return len(self.edges)


@strawberry.type
class DatasetLineageGQL:
    """Lineage information for a dataset."""

    dataset_id: str
    layer: str
    version: str | None = None

    upstream_datasets: list[LineageNodeGQL]
    downstream_datasets: list[LineageNodeGQL]
    generating_pipelines: list[LineageNodeGQL]
    consuming_models: list[LineageNodeGQL]

    @strawberry.field
    def upstream_count(self) -> int:
        """Number of upstream datasets."""
        return len(self.upstream_datasets)

    @strawberry.field
    def downstream_count(self) -> int:
        """Number of downstream datasets."""
        return len(self.downstream_datasets)


@strawberry.type
class ModelLineageGQL:
    """Lineage information for a model."""

    model_name: str
    model_version: int
    framework: str | None = None

    training_datasets: list[LineageNodeGQL]
    upstream_pipelines: list[LineageNodeGQL]
    dataset_snapshots: list[str]

    @strawberry.field
    def is_reproducible(self) -> bool:
        """Check if model training is reproducible (has snapshot IDs)."""
        return len(self.dataset_snapshots) > 0


@strawberry.type
class PipelineLineageGQL:
    """Lineage information for a pipeline."""

    pipeline_id: str
    pipeline_version: int
    pipeline_type: str

    input_datasets: list[LineageNodeGQL]
    output_datasets: list[LineageNodeGQL]
    downstream_models: list[LineageNodeGQL]


@strawberry.type
class ImpactAnalysisGQL:
    """Impact analysis results."""

    target_node: LineageNodeGQL
    affected_datasets: list[LineageNodeGQL]
    affected_models: list[LineageNodeGQL]
    affected_pipelines: list[LineageNodeGQL]

    @strawberry.field
    def total_affected(self) -> int:
        """Total number of affected nodes."""
        return len(self.affected_datasets) + len(self.affected_models) + len(self.affected_pipelines)

    @strawberry.field
    def severity(self) -> str:
        """Assess impact severity."""
        total = len(self.affected_datasets) + len(self.affected_models) + len(self.affected_pipelines)
        if total == 0:
            return "NONE"
        elif total <= 5:
            return "LOW"
        elif total <= 20:
            return "MEDIUM"
        else:
            return "HIGH"
