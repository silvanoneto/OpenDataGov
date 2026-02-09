"""Tests for odg_core.catalog.datahub_client module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from odg_core.catalog.datahub_client import DataHubClient


@pytest.fixture()
def mock_httpx_client() -> MagicMock:
    return MagicMock()


@pytest.fixture()
def client(mock_httpx_client: MagicMock) -> DataHubClient:
    with patch("odg_core.catalog.datahub_client.httpx.Client", return_value=mock_httpx_client):
        c = DataHubClient(gms_url="http://gms:8080", frontend_url="http://frontend:9002")
    return c


# ──── register_dataset ───────────────────────────────────────


class TestRegisterDataset:
    """Tests for DataHubClient.register_dataset."""

    def test_returns_correct_urn(self, client: DataHubClient) -> None:
        # Mock the POST to succeed
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        client.client.post = MagicMock(return_value=mock_resp)  # type: ignore[method-assign]

        result = client.register_dataset(
            dataset_id="gold/finance/revenue",
            name="Revenue",
            platform="s3",
            layer="gold",
            schema=[{"name": "id", "type": "STRING"}],
        )

        assert result["urn"] == "urn:li:dataset:(urn:li:dataPlatform:s3,gold/finance/revenue,PROD)"

    def test_auto_adds_layer_tag(self, client: DataHubClient) -> None:
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        client.client.post = MagicMock(return_value=mock_resp)  # type: ignore[method-assign]

        result = client.register_dataset(
            dataset_id="silver/customers",
            name="Customers",
            platform="postgresql",
            layer="silver",
            schema=[],
            tags=[],
        )

        assert "silver_layer" in result["tags"]

    def test_does_not_duplicate_layer_tag(self, client: DataHubClient) -> None:
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        client.client.post = MagicMock(return_value=mock_resp)  # type: ignore[method-assign]

        result = client.register_dataset(
            dataset_id="gold/data",
            name="Data",
            platform="s3",
            layer="gold",
            schema=[],
            tags=["gold_layer"],
        )

        assert result["tags"].count("gold_layer") == 1

    def test_metadata_keys(self, client: DataHubClient) -> None:
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        client.client.post = MagicMock(return_value=mock_resp)  # type: ignore[method-assign]

        result = client.register_dataset(
            dataset_id="bronze/raw",
            name="Raw",
            platform="s3",
            layer="bronze",
            schema=[{"name": "col", "type": "INT"}],
            description="desc",
            owner="owner@test.com",
        )

        assert result["name"] == "Raw"
        assert result["platform"] == "s3"
        assert result["layer"] == "bronze"
        assert result["description"] == "desc"
        assert result["owner"] == "owner@test.com"
        assert "registered_at" in result


# ──── add_lineage ────────────────────────────────────────────


class TestAddLineage:
    """Tests for DataHubClient.add_lineage."""

    def test_returns_correct_structure(self, client: DataHubClient) -> None:
        result = client.add_lineage(
            downstream_urn="urn:li:dataset:downstream",
            upstream_urns=["urn:li:dataset:upstream1", "urn:li:dataset:upstream2"],
            lineage_type="transformation",
            transformation_description="DQ + dedup",
        )

        assert result["downstream"] == "urn:li:dataset:downstream"
        assert len(result["upstreams"]) == 2
        assert result["type"] == "transformation"
        assert result["description"] == "DQ + dedup"
        assert "created_at" in result


# ──── register_ml_model ──────────────────────────────────────


class TestRegisterMLModel:
    """Tests for DataHubClient.register_ml_model."""

    def test_includes_model_metadata(self, client: DataHubClient) -> None:
        result = client.register_ml_model(
            model_name="churn",
            model_version=2,
            mlflow_run_id="run123",
            training_datasets=["urn:li:dataset:gold/customers"],
            features=["f1", "f2"],
            metrics={"accuracy": 0.95},
            tags=["production"],
        )

        assert result["name"] == "churn"
        assert result["version"] == 2
        assert result["platform"] == "mlflow"
        assert result["mlflow_run_id"] == "run123"
        assert result["features"] == ["f1", "f2"]
        assert result["metrics"]["accuracy"] == 0.95
        assert "urn" in result

    def test_model_urn_format(self, client: DataHubClient) -> None:
        result = client.register_ml_model(
            model_name="fraud",
            model_version=1,
            mlflow_run_id="r1",
            training_datasets=[],
            features=[],
            metrics={},
        )

        assert result["urn"] == "urn:li:mlModel:(urn:li:dataPlatform:mlflow,fraud,1)"


# ──── register_feast_features ────────────────────────────────


class TestRegisterFeastFeatures:
    """Tests for DataHubClient.register_feast_features."""

    def test_includes_lineage(self, client: DataHubClient) -> None:
        result = client.register_feast_features(
            feature_view_name="customer_features",
            features=[{"name": "f1", "type": "FLOAT"}],
            source_dataset_urn="urn:li:dataset:gold/customers",
            materialization_interval="1h",
            tags=["online"],
        )

        assert result["name"] == "customer_features"
        assert result["platform"] == "feast"
        assert result["source_dataset"] == "urn:li:dataset:gold/customers"
        assert result["materialization_interval"] == "1h"
        assert "urn" in result

    def test_feast_urn_format(self, client: DataHubClient) -> None:
        result = client.register_feast_features(
            feature_view_name="user_features",
            features=[],
            source_dataset_urn="urn:ds",
            materialization_interval="1d",
        )

        assert result["urn"] == "urn:li:mlFeatureTable:(urn:li:dataPlatform:feast,user_features,PROD)"


# ──── add_tags ───────────────────────────────────────────────


class TestAddTags:
    """Tests for DataHubClient.add_tags."""

    def test_returns_tag_metadata(self, client: DataHubClient) -> None:
        result = client.add_tags(
            entity_urn="urn:li:dataset:test",
            tags=["gdpr", "production"],
        )

        assert result["urn"] == "urn:li:dataset:test"
        assert result["tags"] == ["gdpr", "production"]
        assert "added_at" in result


# ──── search ─────────────────────────────────────────────────


class TestSearch:
    """Tests for DataHubClient.search."""

    def test_returns_parsed_results(self, client: DataHubClient) -> None:
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "value": {
                "entities": [
                    {"urn": "urn:li:dataset:test", "name": "Test", "platform": "s3", "score": 1.0},
                ]
            }
        }
        client.client.post = MagicMock(return_value=mock_resp)  # type: ignore[method-assign]

        results = client.search("test", entity_types=["dataset"])

        assert len(results) == 1
        assert results[0]["urn"] == "urn:li:dataset:test"
        assert results[0]["name"] == "Test"
        assert results[0]["platform"] == "s3"
        assert results[0]["score"] == 1.0

    def test_handles_http_error_gracefully(self, client: DataHubClient) -> None:
        import httpx

        client.client.post = MagicMock(side_effect=httpx.HTTPError("Connection failed"))  # type: ignore[method-assign]

        results = client.search("test")

        assert results == []

    def test_search_empty_results(self, client: DataHubClient) -> None:
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"value": {"entities": []}}
        client.client.post = MagicMock(return_value=mock_resp)  # type: ignore[method-assign]

        results = client.search("nonexistent")
        assert results == []


# ──── get_lineage ────────────────────────────────────────────


class TestGetLineage:
    """Tests for DataHubClient.get_lineage."""

    def test_returns_structure(self, client: DataHubClient) -> None:
        result = client.get_lineage(
            entity_urn="urn:li:dataset:gold/revenue",
            direction="upstream",
            max_hops=5,
        )

        assert result["entity"] == "urn:li:dataset:gold/revenue"
        assert result["direction"] == "upstream"
        assert result["max_hops"] == 5
        assert "graph" in result
