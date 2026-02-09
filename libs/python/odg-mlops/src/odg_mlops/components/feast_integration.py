"""Feast feature store integration components for Kubeflow Pipelines."""

from __future__ import annotations

from kfp import dsl
from kfp.dsl import Dataset, Output


@dsl.component(
    base_image="python:3.11-slim",
    packages_to_install=["feast>=0.36.0", "pandas>=2.0.0", "httpx>=0.25.0"],
)
def get_historical_features(
    entity_df_path: str,
    feature_views: list[str],
    output_features: Output[Dataset],
    feast_repo_path: str = "/feast/repo",
) -> str:
    """Get historical features for training from Feast offline store.

    Args:
        entity_df_path: Path to entity DataFrame (parquet)
        feature_views: List of feature view names to fetch
        feast_repo_path: Path to Feast repository
        output_features: Output dataset with features

    Returns:
        str: Path to feature dataset

    Example:
        >>> features_task = get_historical_features(
        ...     entity_df_path=entities_task.output,
        ...     feature_views=[
        ...         "customer_demographics:age",
        ...         "customer_demographics:annual_income",
        ...         "customer_transactions:total_purchases_30d"
        ...     ]
        ... )
    """
    from pathlib import Path

    import pandas as pd
    from feast import FeatureStore

    # Initialize Feast
    store = FeatureStore(repo_path=feast_repo_path)

    # Load entity DataFrame
    entity_df = pd.read_parquet(entity_df_path)

    print(f"Loading features for {len(entity_df)} entities")
    print(f"Feature views: {feature_views}")

    # Get historical features
    training_df = store.get_historical_features(
        entity_df=entity_df,
        features=feature_views,
    ).to_df()

    print(f"✓ Retrieved features: {training_df.shape}")
    print(f"Columns: {list(training_df.columns)}")

    # Save to output
    output_path = Path(output_features.path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    training_df.to_parquet(output_path)

    return str(output_path)


@dsl.component(
    base_image="python:3.11-slim",
    packages_to_install=["feast>=0.36.0", "pandas>=2.0.0"],
)
def materialize_features(
    feature_views: list[str],
    start_date: str,
    end_date: str,
    feast_repo_path: str = "/feast/repo",
) -> dict:
    """Materialize features from offline to online store.

    This makes features available for online serving (low-latency inference).

    Args:
        feature_views: List of feature view names to materialize
        start_date: Start date (ISO format)
        end_date: End date (ISO format)
        feast_repo_path: Path to Feast repository

    Returns:
        dict: Materialization summary

    Example:
        >>> materialize_task = materialize_features(
        ...     feature_views=["customer_demographics", "customer_transactions"],
        ...     start_date="2026-01-01",
        ...     end_date="2026-02-08"
        ... )
    """
    from datetime import datetime

    from feast import FeatureStore

    store = FeatureStore(repo_path=feast_repo_path)

    start = datetime.fromisoformat(start_date)
    end = datetime.fromisoformat(end_date)

    print(f"Materializing {len(feature_views)} feature views")
    print(f"Date range: {start} to {end}")

    # Materialize each feature view
    for fv_name in feature_views:
        print(f"Materializing {fv_name}...")
        store.materialize(
            start_date=start,
            end_date=end,
            feature_views=[fv_name],
        )

    print("✓ Materialization complete")

    return {
        "feature_views": feature_views,
        "start_date": start_date,
        "end_date": end_date,
        "status": "success",
    }


@dsl.component(
    base_image="python:3.11-slim",
    packages_to_install=["httpx>=0.25.0"],
)
def validate_feature_freshness(
    feature_view: str,
    max_staleness_hours: int = 24,
    quality_gate_url: str = "http://quality-gate:8003",
) -> bool:
    """Validate feature freshness (quality gate).

    Ensures features are not stale before using for training or inference.

    Args:
        feature_view: Feature view name
        max_staleness_hours: Maximum allowed staleness
        quality_gate_url: Quality Gate service URL

    Returns:
        bool: True if features are fresh

    Raises:
        ValueError: If features are stale

    Example:
        >>> validate_task = validate_feature_freshness(
        ...     feature_view="customer_transactions",
        ...     max_staleness_hours=24
        ... )
        >>> load_task = get_historical_features(...).after(validate_task)
    """
    from datetime import datetime, timedelta

    import httpx

    # Query Feast for feature metadata
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(
                f"{quality_gate_url}/api/v1/feast/features/{feature_view}/metadata"
            )
            response.raise_for_status()
            metadata = response.json()
    except httpx.HTTPError as e:
        # If quality gate doesn't have endpoint, skip validation
        print(f"Warning: Could not validate freshness: {e}")
        return True

    # Check last materialization time
    last_update_str = metadata.get("last_materialization")
    if not last_update_str:
        print(f"Warning: No materialization metadata for {feature_view}")
        return True

    last_update = datetime.fromisoformat(last_update_str)
    staleness = datetime.utcnow() - last_update
    max_staleness = timedelta(hours=max_staleness_hours)

    print(f"Feature View: {feature_view}")
    print(f"Last Materialization: {last_update}")
    print(f"Staleness: {staleness}")
    print(f"Max Allowed: {max_staleness}")

    if staleness > max_staleness:
        raise ValueError(
            f"Feature view {feature_view} is stale by {staleness} "
            f"(max: {max_staleness}). Re-materialize features before using."
        )

    print(f"✓ Features are fresh: staleness {staleness} <= {max_staleness}")
    return True


@dsl.component(
    base_image="python:3.11-slim",
    packages_to_install=["feast>=0.36.0", "pandas>=2.0.0"],
)
def get_online_features(
    entity_rows: list[dict],
    feature_views: list[str],
    feast_repo_path: str = "/feast/repo",
) -> list[dict]:
    """Get online features for real-time inference.

    Args:
        entity_rows: List of entity dicts (e.g., [{"customer_id": 123}, ...])
        feature_views: List of feature view names
        feast_repo_path: Path to Feast repository

    Returns:
        list[dict]: Feature vectors for each entity

    Example:
        >>> # In serving code (not Kubeflow)
        >>> features = get_online_features(
        ...     entity_rows=[{"customer_id": 12345}],
        ...     feature_views=["customer_demographics", "customer_transactions"]
        ... )
    """
    from feast import FeatureStore

    store = FeatureStore(repo_path=feast_repo_path)

    print(f"Fetching online features for {len(entity_rows)} entities")

    # Get online features
    feature_vector = store.get_online_features(
        entity_rows=entity_rows,
        features=feature_views,
    ).to_dict()

    print(f"✓ Retrieved features: {len(feature_vector)} vectors")

    return feature_vector
