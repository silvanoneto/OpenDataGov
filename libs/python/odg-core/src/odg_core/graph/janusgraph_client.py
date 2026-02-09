"""JanusGraph client for data lineage graph queries.

Provides high-level interface for querying lineage using Gremlin queries.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

try:
    from gremlin_python.driver import client as gremlin_client
    from gremlin_python.driver.driver_remote_connection import DriverRemoteConnection
    from gremlin_python.process.anonymous_traversal import traversal
    from gremlin_python.process.graph_traversal import __
except ImportError:
    gremlin_client = None
    DriverRemoteConnection = None
    traversal = None
    __ = None


@dataclass
class LineageNode:
    """Represents a node in the lineage graph."""

    id: str
    label: str  # Dataset, Pipeline, Model, Feature
    properties: dict[str, Any]

    @property
    def node_type(self) -> str:
        """Get node type (vertex label)."""
        return self.label

    @property
    def name(self) -> str:
        """Get node name."""
        return str(self.properties.get("name", ""))


@dataclass
class LineageEdge:
    """Represents an edge in the lineage graph."""

    id: str
    label: str  # DERIVED_FROM, TRAINED_ON, GENERATED_BY, etc.
    source_id: str
    target_id: str
    properties: dict[str, Any]

    @property
    def edge_type(self) -> str:
        """Get edge type (edge label)."""
        return self.label


class JanusGraphClient:
    """Client for JanusGraph lineage graph.

    Example:
        >>> from odg_core.graph import JanusGraphClient
        >>>
        >>> client = JanusGraphClient(url="ws://janusgraph:8182/gremlin")
        >>> client.connect()
        >>>
        >>> # Add lineage: pipeline generates dataset
        >>> client.add_pipeline_generates_dataset(
        ...     pipeline_id="spark_aggregate_sales",
        ...     pipeline_version=5,
        ...     dataset_id="gold/sales_aggregated",
        ...     dataset_version="snapshot_123"
        ... )
        >>>
        >>> # Query: What datasets did this pipeline generate?
        >>> datasets = client.get_pipeline_outputs("spark_aggregate_sales")
    """

    def __init__(self, url: str | None = None):
        """Initialize JanusGraph client.

        Args:
            url: JanusGraph Gremlin Server URL (ws://host:8182/gremlin)
        """
        if gremlin_client is None:
            raise ImportError("gremlinpython not installed. Install with: pip install gremlinpython")

        self.url = url or os.getenv("JANUSGRAPH_URL", "ws://janusgraph:8182/gremlin")
        self._client = None
        self._g = None
        self._connected = False

    def connect(self) -> None:
        """Connect to JanusGraph Gremlin Server."""
        try:
            self._client = gremlin_client.Client(self.url, "g")

            # Also create a traversal source for more complex queries
            remote_conn = DriverRemoteConnection(self.url, "g")
            self._g = traversal().withRemote(remote_conn)

            # Test connection
            self._get_client().submit("g.V().limit(1)").all().result()
            self._connected = True

        except Exception as e:
            raise ConnectionError(f"Failed to connect to JanusGraph at {self.url}: {e}") from e

    def disconnect(self) -> None:
        """Close connection to JanusGraph."""
        if self._client:
            self._client.close()
        self._connected = False

    def _get_client(self) -> Any:
        """Return the Gremlin client, raising if not connected.

        Returns:
            The connected Gremlin client.

        Raises:
            ConnectionError: If the client is not connected.
        """
        if self._client is None:
            raise ConnectionError("Not connected to JanusGraph. Call connect() first.")
        return self._client

    # ─── Node Management ─────────────────────────────────────

    def add_dataset(self, dataset_id: str, layer: str, version: str | None = None, **properties: Any) -> LineageNode:
        """Add or update a dataset node.

        Args:
            dataset_id: Dataset identifier (e.g., "gold/customers")
            layer: Medallion layer (bronze, silver, gold)
            version: Dataset version (Iceberg snapshot ID)
            **properties: Additional properties

        Returns:
            Created/updated node
        """
        query = """
            g.V().has('Dataset', 'dataset_id', dataset_id).fold()
            .coalesce(
                unfold(),
                addV('Dataset').property('dataset_id', dataset_id)
            )
            .property('layer', layer)
        """

        if version:
            query += ".property('version', version)"

        for key, _value in properties.items():
            query += f".property('{key}', {key}_val)"

        bindings = {
            "dataset_id": dataset_id,
            "layer": layer,
            "version": version,
            **{f"{k}_val": v for k, v in properties.items()},
        }

        result = self._get_client().submit(query, bindings).all().result()

        return LineageNode(
            id=str(result[0].id),
            label="Dataset",
            properties={"dataset_id": dataset_id, "layer": layer, "version": version, **properties},
        )

    def add_pipeline(
        self, pipeline_id: str, pipeline_version: int, pipeline_type: str = "spark", **properties: Any
    ) -> LineageNode:
        """Add or update a pipeline node.

        Args:
            pipeline_id: Pipeline identifier
            pipeline_version: Pipeline version number
            pipeline_type: Type (spark, airflow, kubeflow, duckdb, polars)
            **properties: Additional properties

        Returns:
            Created/updated node
        """
        query = """
            g.V().has('Pipeline', 'pipeline_id', pipeline_id)
            .has('version', version).fold()
            .coalesce(
                unfold(),
                addV('Pipeline')
                .property('pipeline_id', pipeline_id)
                .property('version', version)
            )
            .property('pipeline_type', pipeline_type)
        """

        bindings = {"pipeline_id": pipeline_id, "version": pipeline_version, "pipeline_type": pipeline_type}

        result = self._get_client().submit(query, bindings).all().result()

        return LineageNode(
            id=str(result[0].id),
            label="Pipeline",
            properties={"pipeline_id": pipeline_id, "version": pipeline_version, **properties},
        )

    def add_model(
        self,
        model_name: str,
        model_version: int,
        framework: str = "sklearn",
        **properties: Any,
    ) -> LineageNode:
        """Add or update a model node.

        Args:
            model_name: Model name
            model_version: Model version
            framework: ML framework (sklearn, pytorch, tensorflow)
            **properties: Additional properties

        Returns:
            Created/updated node
        """
        query = """
            g.V().has('Model', 'model_name', model_name)
            .has('version', version).fold()
            .coalesce(
                unfold(),
                addV('Model')
                .property('model_name', model_name)
                .property('version', version)
            )
            .property('framework', framework)
        """

        bindings = {"model_name": model_name, "version": model_version, "framework": framework}

        result = self._get_client().submit(query, bindings).all().result()

        return LineageNode(
            id=str(result[0].id),
            label="Model",
            properties={"model_name": model_name, "version": model_version, **properties},
        )

    def add_feature(self, feature_view: str, feature_names: list[str], **properties: Any) -> LineageNode:
        """Add or update a feature node.

        Args:
            feature_view: Feast feature view name
            feature_names: List of feature names
            **properties: Additional properties

        Returns:
            Created/updated node
        """
        query = """
            g.V().has('Feature', 'feature_view', feature_view).fold()
            .coalesce(
                unfold(),
                addV('Feature')
                .property('feature_view', feature_view)
            )
            .property('feature_names', feature_names)
        """

        bindings = {"feature_view": feature_view, "feature_names": feature_names}

        result = self._get_client().submit(query, bindings).all().result()

        return LineageNode(
            id=str(result[0].id),
            label="Feature",
            properties={"feature_view": feature_view, "feature_names": feature_names},
        )

    # ─── Edge Management ─────────────────────────────────────

    def add_edge(
        self,
        source_label: str,
        source_property: str,
        source_value: str,
        target_label: str,
        target_property: str,
        target_value: str,
        edge_label: str,
        **properties: Any,
    ) -> LineageEdge:
        """Add an edge between two nodes.

        Args:
            source_label: Source vertex label
            source_property: Source property name
            source_value: Source property value
            target_label: Target vertex label
            target_property: Target property name
            target_value: Target property value
            edge_label: Edge label
            **properties: Edge properties

        Returns:
            Created edge
        """
        query = f"""
            g.V().has('{source_label}', '{source_property}', source_val).as('source')
            .V().has('{target_label}', '{target_property}', target_val).as('target')
            .coalesce(
                __.inE('{edge_label}').where(outV().as('source')),
                addE('{edge_label}').from('source').to('target')
            )
        """

        bindings = {"source_val": source_value, "target_val": target_value}

        result = self._get_client().submit(query, bindings).all().result()

        return LineageEdge(
            id=str(result[0].id) if result else "",
            label=edge_label,
            source_id=source_value,
            target_id=target_value,
            properties=properties,
        )

    # ─── High-level Lineage Operations ──────────────────────

    def add_pipeline_generates_dataset(
        self, pipeline_id: str, pipeline_version: int, dataset_id: str, dataset_version: str | None = None
    ) -> None:
        """Record that a pipeline generated a dataset.

        Args:
            pipeline_id: Pipeline identifier
            pipeline_version: Pipeline version
            dataset_id: Dataset identifier
            dataset_version: Dataset version (snapshot ID)
        """
        # Ensure nodes exist
        self.add_pipeline(pipeline_id, pipeline_version)
        self.add_dataset(dataset_id, layer=dataset_id.split("/")[0], version=dataset_version)

        # Add edge
        query = """
            g.V().has('Pipeline', 'pipeline_id', pipeline_id)
            .has('version', pipeline_version).as('pipeline')
            .V().has('Dataset', 'dataset_id', dataset_id).as('dataset')
            .coalesce(
                __.inE('GENERATED_BY').where(outV().as('pipeline')),
                addE('GENERATED_BY').from('pipeline').to('dataset')
            )
        """

        self._get_client().submit(
            query, {"pipeline_id": pipeline_id, "pipeline_version": pipeline_version, "dataset_id": dataset_id}
        ).all().result()

    def add_model_trained_on_dataset(
        self, model_name: str, model_version: int, dataset_id: str, dataset_version: str
    ) -> None:
        """Record that a model was trained on a dataset.

        Args:
            model_name: Model name
            model_version: Model version
            dataset_id: Dataset identifier
            dataset_version: Dataset version used for training
        """
        self.add_model(model_name, model_version)
        self.add_dataset(dataset_id, layer=dataset_id.split("/")[0], version=dataset_version)

        query = """
            g.V().has('Model', 'model_name', model_name)
            .has('version', model_version).as('model')
            .V().has('Dataset', 'dataset_id', dataset_id).as('dataset')
            .coalesce(
                __.outE('TRAINED_ON').where(inV().as('dataset')),
                addE('TRAINED_ON').from('model').to('dataset')
            )
        """

        self._get_client().submit(
            query, {"model_name": model_name, "model_version": model_version, "dataset_id": dataset_id}
        ).all().result()

    def add_dataset_derived_from(
        self, target_dataset_id: str, source_dataset_id: str, transformation: str | None = None
    ) -> None:
        """Record dataset derivation (e.g., silver from bronze).

        Args:
            target_dataset_id: Target dataset (e.g., "silver/customers")
            source_dataset_id: Source dataset (e.g., "bronze/customers")
            transformation: Transformation description
        """
        target_layer = target_dataset_id.split("/")[0]
        source_layer = source_dataset_id.split("/")[0]

        self.add_dataset(target_dataset_id, layer=target_layer)
        self.add_dataset(source_dataset_id, layer=source_layer)

        query = """
            g.V().has('Dataset', 'dataset_id', target_id).as('target')
            .V().has('Dataset', 'dataset_id', source_id).as('source')
            .coalesce(
                __.outE('DERIVED_FROM').where(inV().as('source')),
                addE('DERIVED_FROM').from('target').to('source')
                    .property('transformation', transformation)
            )
        """

        self._get_client().submit(
            query,
            {
                "target_id": target_dataset_id,
                "source_id": source_dataset_id,
                "transformation": transformation or "unknown",
            },
        ).all().result()

    # ─── Lineage Queries ─────────────────────────────────────

    def get_upstream_datasets(self, dataset_id: str, max_depth: int = 10) -> list[dict[str, Any]]:
        """Get all upstream datasets (reverse lineage).

        Args:
            dataset_id: Dataset to trace
            max_depth: Maximum traversal depth

        Returns:
            List of upstream datasets
        """
        query = f"""
            g.V().has('Dataset', 'dataset_id', dataset_id)
            .repeat(out('DERIVED_FROM')).times({max_depth})
            .dedup()
            .valueMap(true)
        """

        results = self._get_client().submit(query, {"dataset_id": dataset_id}).all().result()

        return [self._vertex_to_dict(r) for r in results]

    def get_downstream_datasets(self, dataset_id: str, max_depth: int = 10) -> list[dict[str, Any]]:
        """Get all downstream datasets (forward lineage).

        Args:
            dataset_id: Dataset to trace
            max_depth: Maximum traversal depth

        Returns:
            List of downstream datasets
        """
        query = f"""
            g.V().has('Dataset', 'dataset_id', dataset_id)
            .repeat(in('DERIVED_FROM')).times({max_depth})
            .dedup()
            .valueMap(true)
        """

        results = self._get_client().submit(query, {"dataset_id": dataset_id}).all().result()

        return [self._vertex_to_dict(r) for r in results]

    def get_model_training_lineage(self, model_name: str, model_version: int) -> dict[str, Any]:
        """Get complete lineage for model training.

        Args:
            model_name: Model name
            model_version: Model version

        Returns:
            Lineage information including datasets and pipelines
        """
        query = """
            g.V().has('Model', 'model_name', model_name)
            .has('version', model_version)
            .project('model', 'training_datasets', 'upstream_pipelines')
            .by(valueMap(true))
            .by(out('TRAINED_ON').valueMap(true).fold())
            .by(out('TRAINED_ON').in('GENERATED_BY').valueMap(true).fold())
        """

        results = (
            self._get_client().submit(query, {"model_name": model_name, "model_version": model_version}).all().result()
        )

        if not results:
            return {}

        result = results[0]
        return {
            "model": self._vertex_to_dict(result.get("model", {})),
            "training_datasets": [self._vertex_to_dict(d) for d in result.get("training_datasets", [])],
            "upstream_pipelines": [self._vertex_to_dict(p) for p in result.get("upstream_pipelines", [])],
        }

    def get_pipeline_outputs(self, pipeline_id: str) -> list[dict[str, Any]]:
        """Get all datasets generated by a pipeline.

        Args:
            pipeline_id: Pipeline identifier

        Returns:
            List of output datasets
        """
        query = """
            g.V().has('Pipeline', 'pipeline_id', pipeline_id)
            .out('GENERATED_BY')
            .dedup()
            .valueMap(true)
        """

        results = self._get_client().submit(query, {"pipeline_id": pipeline_id}).all().result()

        return [self._vertex_to_dict(r) for r in results]

    def get_dataset_consumers(self, dataset_id: str) -> dict[str, list[dict[str, Any]]]:
        """Get all consumers of a dataset (models and pipelines).

        Args:
            dataset_id: Dataset identifier

        Returns:
            Dictionary with models and pipelines that consume this dataset
        """
        query = """
            g.V().has('Dataset', 'dataset_id', dataset_id)
            .project('models', 'pipelines')
            .by(in('TRAINED_ON').valueMap(true).fold())
            .by(out('GENERATED_BY').valueMap(true).fold())
        """

        results = self._get_client().submit(query, {"dataset_id": dataset_id}).all().result()

        if not results:
            return {"models": [], "pipelines": []}

        result = results[0]
        return {
            "models": [self._vertex_to_dict(m) for m in result.get("models", [])],
            "pipelines": [self._vertex_to_dict(p) for p in result.get("pipelines", [])],
        }

    def get_full_lineage_graph(self, node_id: str, node_type: str, depth: int = 3) -> dict[str, Any]:
        """Get full bidirectional lineage graph.

        Args:
            node_id: Node identifier
            node_type: Node type (Dataset, Model, Pipeline)
            depth: Traversal depth

        Returns:
            Complete lineage graph with nodes and edges
        """
        property_name = {"Dataset": "dataset_id", "Model": "model_name", "Pipeline": "pipeline_id"}.get(node_type, "id")

        query = f"""
            g.V().has('{node_type}', '{property_name}', node_id).as('start')
            .repeat(bothE().otherV().simplePath()).times({depth})
            .path()
            .by(valueMap(true))
            .by(valueMap(true))
        """

        paths = self._get_client().submit(query, {"node_id": node_id}).all().result()

        nodes = []
        edges = []

        for path in paths:
            for i, element in enumerate(path):
                if i % 2 == 0:  # Vertex
                    nodes.append(self._vertex_to_dict(element))
                else:  # Edge
                    edges.append(self._edge_to_dict(element))

        return {"nodes": self._deduplicate_nodes(nodes), "edges": edges}

    def _vertex_to_dict(self, vertex: dict[str, Any]) -> dict[str, Any]:
        """Convert Gremlin vertex to dictionary."""
        if not vertex:
            return {}

        return {
            "id": str(vertex.get("id", "")),
            "label": vertex.get("label", ""),
            **{
                k: v[0] if isinstance(v, list) and len(v) == 1 else v
                for k, v in vertex.items()
                if k not in ["id", "label"]
            },
        }

    def _edge_to_dict(self, edge: dict[str, Any]) -> dict[str, Any]:
        """Convert Gremlin edge to dictionary."""
        if not edge:
            return {}

        return {
            "id": str(edge.get("id", "")),
            "label": edge.get("label", ""),
            "source": edge.get("outV"),
            "target": edge.get("inV"),
            **{k: v for k, v in edge.items() if k not in ["id", "label", "outV", "inV"]},
        }

    def _deduplicate_nodes(self, nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Deduplicate nodes by ID."""
        seen = set()
        result = []

        for node in nodes:
            node_id = node.get("id")
            if node_id and node_id not in seen:
                seen.add(node_id)
                result.append(node)

        return result
