"""Tests for odg_core.feast.materialization_tracker module."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

from odg_core.feast.materialization_tracker import MaterializationTracker, track_feast_materialization

# ──── helpers ───────────────────────────────────────────────────


def _make_feature_view(
    name: str = "customer_features",
    entities: list[str] | None = None,
    feature_names: list[str] | None = None,
    ttl: str | None = "3600s",
    batch_source: str | None = "BigQuerySource",
) -> MagicMock:
    """Create a mock FeatureView with the attributes used by _compute_feature_view_hash."""
    fv = MagicMock()
    fv.name = name
    fv.entities = entities or ["customer_id"]
    features = []
    for fn in feature_names or ["total_purchases", "avg_order_value"]:
        feat = MagicMock()
        feat.name = fn
        features.append(feat)
    fv.features = features
    fv.ttl = ttl
    fv.batch_source = batch_source
    return fv


# ──── MaterializationTracker.__init__ ───────────────────────────


class TestMaterializationTrackerInit:
    """Tests for MaterializationTracker initialization."""

    def test_init_stores_feature_store(self) -> None:
        mock_store = MagicMock()
        tracker = MaterializationTracker(mock_store)

        assert tracker.store is mock_store


# ──── _compute_feature_view_hash ────────────────────────────────


class TestComputeFeatureViewHash:
    """Tests for MaterializationTracker._compute_feature_view_hash."""

    def test_compute_feature_view_hash_returns_12_chars(self) -> None:
        mock_store = MagicMock()
        tracker = MaterializationTracker(mock_store)

        fv = _make_feature_view()
        result = tracker._compute_feature_view_hash(fv)

        assert len(result) == 12

    def test_compute_feature_view_hash_deterministic(self) -> None:
        mock_store = MagicMock()
        tracker = MaterializationTracker(mock_store)

        fv1 = _make_feature_view(name="fv", entities=["e1"], feature_names=["f1"])
        fv2 = _make_feature_view(name="fv", entities=["e1"], feature_names=["f1"])

        hash1 = tracker._compute_feature_view_hash(fv1)
        hash2 = tracker._compute_feature_view_hash(fv2)

        assert hash1 == hash2

    def test_compute_feature_view_hash_different_views_different_hash(self) -> None:
        mock_store = MagicMock()
        tracker = MaterializationTracker(mock_store)

        fv1 = _make_feature_view(name="view_a", feature_names=["f1"])
        fv2 = _make_feature_view(name="view_b", feature_names=["f2"])

        hash1 = tracker._compute_feature_view_hash(fv1)
        hash2 = tracker._compute_feature_view_hash(fv2)

        assert hash1 != hash2

    def test_compute_feature_view_hash_matches_expected(self) -> None:
        mock_store = MagicMock()
        tracker = MaterializationTracker(mock_store)

        fv = _make_feature_view(
            name="test_fv",
            entities=["user_id"],
            feature_names=["clicks", "impressions"],
            ttl="7200s",
            batch_source="FileSource",
        )

        result = tracker._compute_feature_view_hash(fv)

        # Reproduce the expected hash manually
        fv_structure = {
            "name": "test_fv",
            "entities": sorted(["user_id"]),
            "features": sorted(["clicks", "impressions"]),
            "ttl": "7200s",
            "source": "FileSource",
        }
        fv_json = json.dumps(fv_structure, sort_keys=True)
        expected = hashlib.sha256(fv_json.encode()).hexdigest()[:12]

        assert result == expected


# ──── validate_feature_freshness ────────────────────────────────


class TestValidateFeatureFreshness:
    """Tests for MaterializationTracker.validate_feature_freshness."""

    def test_validate_feature_freshness_no_history(self) -> None:
        mock_store = MagicMock()
        tracker = MaterializationTracker(mock_store)

        with patch.object(tracker, "get_materialization_history", return_value=[]):
            result = tracker.validate_feature_freshness("customer_features")

        assert result["is_fresh"] is False
        assert "No materialization history" in result["reason"]
        assert result["feature_view"] == "customer_features"

    def test_validate_feature_freshness_fresh(self) -> None:
        mock_store = MagicMock()
        tracker = MaterializationTracker(mock_store)

        recent_time = datetime.now(UTC) - timedelta(hours=1)
        history = [{"materialization_time": recent_time.isoformat()}]

        with patch.object(tracker, "get_materialization_history", return_value=history):
            result = tracker.validate_feature_freshness("customer_features", max_age_hours=24)

        assert result["is_fresh"] is True
        assert result["age_hours"] < 24
        assert result["feature_view"] == "customer_features"

    def test_validate_feature_freshness_stale(self) -> None:
        mock_store = MagicMock()
        tracker = MaterializationTracker(mock_store)

        old_time = datetime.now(UTC) - timedelta(hours=48)
        history = [{"materialization_time": old_time.isoformat()}]

        with patch.object(tracker, "get_materialization_history", return_value=history):
            result = tracker.validate_feature_freshness("customer_features", max_age_hours=24)

        assert result["is_fresh"] is False
        assert result["age_hours"] > 24


# ──── get_materialization_history ───────────────────────────────


class TestGetMaterializationHistory:
    """Tests for MaterializationTracker.get_materialization_history."""

    def test_get_materialization_history_returns_empty_on_error(self) -> None:
        mock_store = MagicMock()
        tracker = MaterializationTracker(mock_store)

        # Without a database, get_materialization_history should catch the exception
        # and return an empty list
        result = tracker.get_materialization_history("customer_features")
        assert result == []


# ──── track_feast_materialization ───────────────────────────────


class TestTrackFeastMaterialization:
    """Tests for track_feast_materialization convenience function."""

    def test_track_feast_materialization_factory(self) -> None:
        mock_store = MagicMock()

        with patch.object(
            MaterializationTracker, "track_materialization", return_value={"run_id": "abc"}
        ) as mock_track:
            result = track_feast_materialization(
                feature_store=mock_store,
                feature_view_name="customer_features",
                source_pipeline_id="spark_job",
            )

        mock_track.assert_called_once_with(
            "customer_features",
            source_pipeline_id="spark_job",
        )
        assert result == {"run_id": "abc"}


# ──── _persist_materialization ──────────────────────────────────


class TestPersistMaterialization:
    """Tests for MaterializationTracker._persist_materialization."""

    def test_persist_materialization_swallows_errors(self) -> None:
        mock_store = MagicMock()
        tracker = MaterializationTracker(mock_store)

        # Without a database, _persist_materialization should silently fail
        # Should NOT raise
        tracker._persist_materialization(
            {
                "run_id": "test-run",
                "feature_view": "test_fv",
                "feature_names": ["f1"],
                "source_pipeline_id": None,
                "source_pipeline_version": None,
                "source_dataset_id": None,
                "source_dataset_version": None,
                "start_date": None,
                "end_date": None,
                "materialization_time": datetime.now(UTC).isoformat(),
                "feature_view_hash": "abc123def456",
            }
        )
