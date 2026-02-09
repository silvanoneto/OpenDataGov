"""Quality gate validation component for Kubeflow Pipelines.

Validates that training data meets minimum DQ score threshold before proceeding.
Integrates with OpenDataGov Quality Gate service.
"""

from __future__ import annotations

from kfp import dsl


@dsl.component(
    base_image="python:3.11-slim",
    packages_to_install=["httpx>=0.25.0", "odg-core>=0.1.0"],
)
def validate_training_data(
    dataset_id: str,
    min_dq_score: float = 0.95,
    quality_gate_url: str = "http://quality-gate:8003",
) -> bool:
    """Validate training data quality before training.

    This component queries the Quality Gate service to ensure the dataset
    meets the minimum DQ score threshold. Only Gold/Platinum layer datasets
    should pass this validation.

    Args:
        dataset_id: Dataset identifier (e.g., "gold/finance/revenue")
        min_dq_score: Minimum DQ score required (default: 0.95 for Gold layer)
        quality_gate_url: URL of Quality Gate service

    Returns:
        bool: True if validation passed

    Raises:
        ValueError: If DQ score is below threshold
        RuntimeError: If Quality Gate service is unavailable

    Example:
        >>> validate_task = validate_training_data(
        ...     dataset_id="gold/customer/churn",
        ...     min_dq_score=0.95
        ... )
    """
    import httpx

    # Query Quality Gate for DQ report
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.get(f"{quality_gate_url}/api/v1/quality/reports/{dataset_id}")
            response.raise_for_status()
            report = response.json()
    except httpx.HTTPError as e:
        raise RuntimeError(f"Failed to fetch DQ report from Quality Gate: {e}") from e

    # Extract overall DQ score
    overall_score = report.get("overall_score", 0.0)
    dimensions = report.get("dimensions", {})

    print(f"Dataset: {dataset_id}")
    print(f"Overall DQ Score: {overall_score:.3f}")
    print(f"Required Minimum: {min_dq_score:.3f}")
    print("\nDimension Scores:")
    for dim, score in dimensions.items():
        print(f"  {dim}: {score:.3f}")

    # Validate against threshold
    if overall_score < min_dq_score:
        raise ValueError(
            f"DQ score {overall_score:.3f} < {min_dq_score:.3f} "
            f"(Gold layer threshold). Dataset not ready for training.\n"
            f"Failed dimensions: {[k for k, v in dimensions.items() if v < min_dq_score]}"
        )

    print(f"\n✓ Validation passed: DQ score {overall_score:.3f} >= {min_dq_score:.3f}")
    return True


@dsl.component(
    base_image="python:3.11-slim",
    packages_to_install=["httpx>=0.25.0"],
)
def check_feature_freshness(
    feature_view: str,
    max_staleness_hours: int = 24,
    feast_url: str = "http://feast:8000",
) -> bool:
    """Check feature freshness for online serving (Phase 5: Feast integration).

    Args:
        feature_view: Name of Feast feature view
        max_staleness_hours: Maximum allowed staleness in hours
        feast_url: URL of Feast serving service

    Returns:
        bool: True if features are fresh

    Raises:
        ValueError: If features are stale
    """
    from datetime import datetime, timedelta

    import httpx

    # Query Feast for feature metadata
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(f"{feast_url}/api/v1/features/{feature_view}/metadata")
            response.raise_for_status()
            metadata = response.json()
    except httpx.HTTPError as e:
        raise RuntimeError(f"Failed to fetch feature metadata: {e}") from e

    # Check last update time
    last_update = datetime.fromisoformat(metadata["last_update"])
    staleness = datetime.now() - last_update
    max_staleness = timedelta(hours=max_staleness_hours)

    print(f"Feature View: {feature_view}")
    print(f"Last Update: {last_update}")
    print(f"Staleness: {staleness}")
    print(f"Max Allowed: {max_staleness}")

    if staleness > max_staleness:
        raise ValueError(
            f"Feature view {feature_view} is stale by {staleness} (max: {max_staleness})"
        )

    print(f"✓ Features are fresh: staleness {staleness} <= {max_staleness}")
    return True
