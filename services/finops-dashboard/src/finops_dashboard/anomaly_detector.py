"""Anomaly Detector - Detects unusual cost spikes using statistical methods and ML.

Identifies cost anomalies using multiple detection methods:
- Z-score (statistical)
- IQR (Interquartile Range)
- Prophet (ML forecasting)
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Any

import numpy as np
from finops_dashboard.models import (
    AnomalyStatus,
    CloudCostRow,
    CostAnomalyRow,
)
from sqlalchemy import func, select

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class AnomalyDetector:
    """Detects cost anomalies using statistical and ML methods."""

    def __init__(self, db: AsyncSession):
        """Initialize anomaly detector.

        Args:
            db: Database session
        """
        self.db = db

        # Detection thresholds
        self.zscore_threshold = 3.0  # 3 standard deviations
        self.iqr_multiplier = 1.5  # 1.5x IQR
        self.min_confidence = 0.85  # 85% confidence minimum

    async def detect_anomalies(
        self,
        lookback_days: int = 30,
        detection_method: str = "auto",
    ) -> list[dict[str, Any]]:
        """Detect cost anomalies across all services.

        Args:
            lookback_days: Number of days to analyze
            detection_method: zscore, iqr, prophet, or auto (try all)

        Returns:
            List of detected anomalies
        """
        logger.info(f"Running anomaly detection (method: {detection_method}, lookback: {lookback_days} days)")

        # Get distinct services with costs in lookback period
        start_date = datetime.utcnow() - timedelta(days=lookback_days)

        result = await self.db.execute(
            select(
                CloudCostRow.cloud_provider,
                CloudCostRow.service,
                CloudCostRow.project,
            )
            .distinct()
            .where(CloudCostRow.time >= start_date)
        )

        services = result.all()

        anomalies = []

        for cloud_provider, service, project in services:
            # Get cost time series for this service
            time_series = await self._get_cost_time_series(cloud_provider, service, project, lookback_days)

            if len(time_series) < 7:  # Need at least 1 week of data
                continue

            # Detect anomalies using specified method
            if detection_method == "auto":
                # Try all methods and combine results
                zscore_anomalies = await self._detect_zscore(cloud_provider, service, project, time_series)
                iqr_anomalies = await self._detect_iqr(cloud_provider, service, project, time_series)

                # Merge and deduplicate
                service_anomalies = self._merge_anomalies(zscore_anomalies + iqr_anomalies)

            elif detection_method == "zscore":
                service_anomalies = await self._detect_zscore(cloud_provider, service, project, time_series)

            elif detection_method == "iqr":
                service_anomalies = await self._detect_iqr(cloud_provider, service, project, time_series)

            elif detection_method == "prophet":
                service_anomalies = await self._detect_prophet(cloud_provider, service, project, time_series)

            else:
                raise ValueError(f"Unknown detection method: {detection_method}")

            anomalies.extend(service_anomalies)

        # Save detected anomalies to database
        for anomaly in anomalies:
            await self._save_anomaly(anomaly)

        logger.info(f"Detected {len(anomalies)} cost anomalies")
        return anomalies

    async def _get_cost_time_series(
        self,
        cloud_provider: str,
        service: str,
        project: str | None,
        days: int,
    ) -> list[tuple[datetime, Decimal]]:
        """Get daily cost time series for a service.

        Args:
            cloud_provider: Cloud provider
            service: Service name
            project: Project name (or None)
            days: Number of days

        Returns:
            List of (date, cost) tuples
        """
        start_date = datetime.utcnow() - timedelta(days=days)

        query = (
            select(
                func.date_trunc("day", CloudCostRow.time).label("day"),
                func.sum(CloudCostRow.cost).label("total_cost"),
            )
            .where(
                CloudCostRow.time >= start_date,
                CloudCostRow.cloud_provider == cloud_provider,
                CloudCostRow.service == service,
            )
            .group_by("day")
            .order_by("day")
        )

        if project:
            query = query.where(CloudCostRow.project == project)

        result = await self.db.execute(query)
        time_series = [(row.day, row.total_cost) for row in result.all()]

        return time_series

    async def _detect_zscore(
        self,
        cloud_provider: str,
        service: str,
        project: str | None,
        time_series: list[tuple[datetime, Decimal]],
    ) -> list[dict[str, Any]]:
        """Detect anomalies using Z-score method.

        Flags costs that are > N standard deviations from mean.

        Args:
            cloud_provider: Cloud provider
            service: Service name
            project: Project name
            time_series: Cost time series

        Returns:
            List of anomalies
        """
        if len(time_series) < 3:
            return []

        # Convert to numpy array
        costs = np.array([float(cost) for _, cost in time_series])

        # Calculate statistics
        mean = np.mean(costs)
        std = np.std(costs)

        if std == 0:  # No variation
            return []

        anomalies = []

        # Check each data point
        for _i, (date, cost) in enumerate(time_series):
            zscore = abs((float(cost) - mean) / std)

            if zscore > self.zscore_threshold:
                # Anomaly detected
                expected_cost = Decimal(mean)
                deviation_pct = ((cost - expected_cost) / expected_cost * 100) if expected_cost > 0 else Decimal(0)

                # Calculate confidence (normalized zscore)
                confidence = min(zscore / (self.zscore_threshold * 2), 1.0)

                anomaly = {
                    "detected_at": datetime.utcnow(),
                    "cloud_provider": cloud_provider,
                    "service": service,
                    "project": project,
                    "expected_cost": expected_cost,
                    "actual_cost": cost,
                    "deviation_pct": deviation_pct,
                    "detection_method": "zscore",
                    "confidence_score": Decimal(confidence),
                    "anomaly_date": date,
                }

                anomalies.append(anomaly)

        return anomalies

    async def _detect_iqr(
        self,
        cloud_provider: str,
        service: str,
        project: str | None,
        time_series: list[tuple[datetime, Decimal]],
    ) -> list[dict[str, Any]]:
        """Detect anomalies using IQR (Interquartile Range) method.

        Flags costs outside [Q1 - 1.5*IQR, Q3 + 1.5*IQR] range.

        Args:
            cloud_provider: Cloud provider
            service: Service name
            project: Project name
            time_series: Cost time series

        Returns:
            List of anomalies
        """
        if len(time_series) < 4:
            return []

        costs = np.array([float(cost) for _, cost in time_series])

        # Calculate quartiles
        q1 = np.percentile(costs, 25)
        q3 = np.percentile(costs, 75)
        iqr = q3 - q1

        if iqr == 0:
            return []

        # Calculate bounds
        lower_bound = q1 - self.iqr_multiplier * iqr
        upper_bound = q3 + self.iqr_multiplier * iqr

        anomalies = []

        for date, cost in time_series:
            if float(cost) < lower_bound or float(cost) > upper_bound:
                # Anomaly detected
                expected_cost = Decimal((q1 + q3) / 2)  # Median
                deviation_pct = ((cost - expected_cost) / expected_cost * 100) if expected_cost > 0 else Decimal(0)

                # Calculate confidence (distance from bound)
                if float(cost) > upper_bound:
                    distance = (float(cost) - upper_bound) / iqr
                else:
                    distance = (lower_bound - float(cost)) / iqr

                confidence = min(distance / 2, 1.0)

                anomaly = {
                    "detected_at": datetime.utcnow(),
                    "cloud_provider": cloud_provider,
                    "service": service,
                    "project": project,
                    "expected_cost": expected_cost,
                    "actual_cost": cost,
                    "deviation_pct": deviation_pct,
                    "detection_method": "iqr",
                    "confidence_score": Decimal(confidence),
                    "anomaly_date": date,
                }

                anomalies.append(anomaly)

        return anomalies

    async def _detect_prophet(
        self,
        cloud_provider: str,
        service: str,
        project: str | None,
        time_series: list[tuple[datetime, Decimal]],
    ) -> list[dict[str, Any]]:
        """Detect anomalies using Prophet ML forecasting.

        Uses Facebook Prophet to forecast expected costs and flag deviations.

        Args:
            cloud_provider: Cloud provider
            service: Service name
            project: Project name
            time_series: Cost time series

        Returns:
            List of anomalies
        """
        if len(time_series) < 14:  # Need at least 2 weeks
            return []

        try:
            import pandas as pd
            from prophet import Prophet

            # Prepare data for Prophet
            df = pd.DataFrame({"ds": [date for date, _ in time_series], "y": [float(cost) for _, cost in time_series]})

            # Train model
            model = Prophet(
                daily_seasonality=False,
                weekly_seasonality=True,
                yearly_seasonality=False,
            )

            # Suppress Prophet logs
            import logging as stdlib_logging

            stdlib_logging.getLogger("prophet").setLevel(stdlib_logging.WARNING)

            model.fit(df)

            # Make predictions
            forecast = model.predict(df)

            anomalies = []

            # Check for anomalies
            for i, (date, actual_cost) in enumerate(time_series):
                predicted_cost = Decimal(forecast.loc[i, "yhat"])
                lower_bound = Decimal(forecast.loc[i, "yhat_lower"])
                upper_bound = Decimal(forecast.loc[i, "yhat_upper"])

                # Check if actual is outside prediction interval
                if actual_cost < lower_bound or actual_cost > upper_bound:
                    deviation_pct = (
                        ((actual_cost - predicted_cost) / predicted_cost * 100) if predicted_cost > 0 else Decimal(0)
                    )

                    # Calculate confidence (how far outside interval)
                    interval_width = upper_bound - lower_bound
                    distance = actual_cost - upper_bound if actual_cost > upper_bound else lower_bound - actual_cost

                    confidence = min(float(distance / interval_width) * 0.5 + 0.5, 1.0)

                    anomaly = {
                        "detected_at": datetime.utcnow(),
                        "cloud_provider": cloud_provider,
                        "service": service,
                        "project": project,
                        "expected_cost": predicted_cost,
                        "actual_cost": actual_cost,
                        "deviation_pct": deviation_pct,
                        "detection_method": "prophet",
                        "confidence_score": Decimal(confidence),
                        "anomaly_date": date,
                    }

                    anomalies.append(anomaly)

            return anomalies

        except ImportError:
            logger.warning("Prophet not installed, skipping ML-based detection")
            return []
        except Exception as e:
            logger.error(f"Error in Prophet detection: {e}")
            return []

    def _merge_anomalies(self, anomalies: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Merge anomalies from multiple detection methods, deduplicating.

        Args:
            anomalies: List of anomalies

        Returns:
            Deduplicated list with highest confidence kept
        """
        # Group by (service, project, date)
        grouped = {}

        for anomaly in anomalies:
            key = (
                anomaly["service"],
                anomaly["project"],
                anomaly["anomaly_date"],
            )

            if key not in grouped or anomaly["confidence_score"] > grouped[key]["confidence_score"]:
                grouped[key] = anomaly

        return list(grouped.values())

    async def _save_anomaly(self, anomaly: dict[str, Any]):
        """Save anomaly to database.

        Args:
            anomaly: Anomaly data
        """
        # Check if already exists
        result = await self.db.execute(
            select(CostAnomalyRow).where(
                CostAnomalyRow.cloud_provider == anomaly["cloud_provider"],
                CostAnomalyRow.service == anomaly["service"],
                CostAnomalyRow.project == anomaly.get("project"),
                func.date(CostAnomalyRow.detected_at) == anomaly["anomaly_date"].date(),
            )
        )

        existing = result.scalar_one_or_none()

        if existing:
            logger.debug(f"Anomaly already exists for {anomaly['service']} on {anomaly['anomaly_date']}")
            return

        # Create new anomaly record
        anomaly_row = CostAnomalyRow(
            detected_at=anomaly["detected_at"],
            cloud_provider=anomaly["cloud_provider"],
            service=anomaly["service"],
            project=anomaly.get("project"),
            expected_cost=anomaly["expected_cost"],
            actual_cost=anomaly["actual_cost"],
            deviation_pct=anomaly["deviation_pct"],
            detection_method=anomaly["detection_method"],
            confidence_score=anomaly["confidence_score"],
            status=AnomalyStatus.OPEN,
        )

        self.db.add(anomaly_row)
        await self.db.commit()

        # Send alert (if confidence high enough)
        if anomaly["confidence_score"] >= self.min_confidence:
            await self._send_anomaly_alert(anomaly)

    async def _send_anomaly_alert(self, anomaly: dict[str, Any]):
        """Send alert for detected anomaly.

        Args:
            anomaly: Anomaly data
        """
        # Build alert message
        message = f"""
⚠️ **Cost Anomaly Detected**

**Service:** {anomaly["cloud_provider"].upper()} {anomaly["service"]}
**Project:** {anomaly.get("project", "N/A")}
**Date:** {anomaly["anomaly_date"].strftime("%Y-%m-%d")}

**Expected Cost:** ${anomaly["expected_cost"]:,.2f}
**Actual Cost:** ${anomaly["actual_cost"]:,.2f}
**Deviation:** {anomaly["deviation_pct"]:+.1f}%

**Detection Method:** {anomaly["detection_method"].upper()}
**Confidence:** {anomaly["confidence_score"] * 100:.0f}%

**Action:** Investigate resource scaling events or configuration changes
"""

        # Send to Slack (implementation would use Slack SDK)
        logger.info(f"Would send anomaly alert: {message[:100]}...")

    async def resolve_anomaly(self, anomaly_id: int, status: AnomalyStatus, resolution_notes: str, resolved_by: str):
        """Mark anomaly as resolved or false positive.

        Args:
            anomaly_id: Anomaly ID
            status: New status (resolved or false_positive)
            resolution_notes: Notes explaining resolution
            resolved_by: User who resolved
        """
        result = await self.db.execute(select(CostAnomalyRow).where(CostAnomalyRow.anomaly_id == anomaly_id))

        anomaly = result.scalar_one()

        anomaly.status = status
        anomaly.resolution_notes = resolution_notes
        anomaly.resolved_at = datetime.utcnow()
        anomaly.resolved_by = resolved_by

        await self.db.commit()

        logger.info(f"Anomaly {anomaly_id} marked as {status} by {resolved_by}")
