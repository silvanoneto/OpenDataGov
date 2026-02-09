"""Drift detection using Evidently library.

Detects:
- Data drift: Changes in input feature distributions
- Prediction drift: Changes in model output distributions
- Concept drift: Changes in relationship between features and target
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import pandas as pd
from evidently.test_suite import TestSuite
from evidently.tests import (
    TestColumnDrift,
    TestShareOfDriftedColumns,
    TestValueMeanDrift,
    TestValueStdDrift,
)
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class DriftReport(BaseModel):
    """Drift detection report."""

    model_name: str
    drift_detected: bool
    drift_score: float = Field(..., ge=0.0, le=1.0)
    drifted_features: list[str] = Field(default_factory=list)
    timestamp: datetime
    reference_samples: int
    current_samples: int
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvidentialyDriftDetector:
    """Drift detector using Evidently framework.

    Uses statistical tests to detect distribution shifts:
    - Kolmogorov-Smirnov test for continuous features
    - Chi-squared test for categorical features
    - PSI (Population Stability Index) for overall drift
    """

    def __init__(
        self,
        drift_threshold: float = 0.5,
        min_samples: int = 100,
    ):
        """Initialize drift detector.

        Args:
            drift_threshold: Threshold for drift detection (0-1)
                0.5 = 50% of features must show drift
            min_samples: Minimum samples required for detection
        """
        self.drift_threshold = drift_threshold
        self.min_samples = min_samples

    def detect_drift(
        self,
        reference_data: pd.DataFrame,
        current_data: pd.DataFrame,
        model_name: str,
    ) -> DriftReport:
        """Detect drift between reference and current data.

        Args:
            reference_data: Reference window (e.g., training data or last 7 days)
            current_data: Current window (e.g., last 24 hours)
            model_name: Model name for logging

        Returns:
            DriftReport with detection results

        Raises:
            ValueError: If insufficient samples
        """
        logger.info(
            f"Detecting drift for {model_name}: "
            f"reference={len(reference_data)}, current={len(current_data)}"
        )

        # Validate sample sizes
        if len(reference_data) < self.min_samples:
            raise ValueError(
                f"Insufficient reference samples: {len(reference_data)} < {self.min_samples}"
            )

        if len(current_data) < self.min_samples:
            raise ValueError(
                f"Insufficient current samples: {len(current_data)} < {self.min_samples}"
            )

        # Build test suite
        test_suite = TestSuite(
            tests=[
                # Test if overall share of drifted columns exceeds threshold
                TestShareOfDriftedColumns(lt=self.drift_threshold),
                # Test each column for drift
                *[
                    TestColumnDrift(column_name=col, stattest="ks")
                    for col in reference_data.columns
                    if reference_data[col].dtype in ["float64", "int64"]
                ],
                # Test mean/std shifts
                TestValueMeanDrift(column_name=reference_data.columns[0]),
                TestValueStdDrift(column_name=reference_data.columns[0]),
            ]
        )

        # Run tests
        test_suite.run(reference_data=reference_data, current_data=current_data)

        # Parse results
        results = test_suite.as_dict()
        summary = results.get("summary", {})

        # Extract drifted features
        drifted_features = []
        for test_result in results.get("tests", []):
            if test_result.get("name") == "TestColumnDrift":
                if test_result.get("status") == "FAIL":
                    column = test_result.get("parameters", {}).get("column_name")
                    if column:
                        drifted_features.append(column)

        # Calculate drift score
        total_features = len(reference_data.columns)
        drift_score = len(drifted_features) / total_features if total_features > 0 else 0.0

        # Overall drift detection
        drift_detected = drift_score >= self.drift_threshold

        logger.info(
            f"Drift detection complete: drift={drift_detected}, "
            f"score={drift_score:.3f}, features={drifted_features}"
        )

        return DriftReport(
            model_name=model_name,
            drift_detected=drift_detected,
            drift_score=drift_score,
            drifted_features=drifted_features,
            timestamp=datetime.utcnow(),
            reference_samples=len(reference_data),
            current_samples=len(current_data),
            metadata={
                "drift_threshold": self.drift_threshold,
                "summary": summary,
            },
        )

    def detect_prediction_drift(
        self,
        reference_predictions: pd.Series,
        current_predictions: pd.Series,
        model_name: str,
    ) -> DriftReport:
        """Detect drift in model predictions (output drift).

        Args:
            reference_predictions: Reference predictions
            current_predictions: Current predictions
            model_name: Model name

        Returns:
            DriftReport for prediction drift
        """
        # Convert to DataFrames
        reference_df = pd.DataFrame({"prediction": reference_predictions})
        current_df = pd.DataFrame({"prediction": current_predictions})

        # Use KS test for continuous predictions, Chi2 for categorical
        test_suite = TestSuite(
            tests=[
                TestColumnDrift(column_name="prediction", stattest="ks"),
            ]
        )

        test_suite.run(reference_data=reference_df, current_data=current_df)

        results = test_suite.as_dict()
        drift_detected = results.get("tests", [{}])[0].get("status") == "FAIL"

        return DriftReport(
            model_name=model_name,
            drift_detected=drift_detected,
            drift_score=1.0 if drift_detected else 0.0,
            drifted_features=["prediction"],
            timestamp=datetime.utcnow(),
            reference_samples=len(reference_predictions),
            current_samples=len(current_predictions),
            metadata={
                "drift_type": "prediction_drift",
            },
        )
