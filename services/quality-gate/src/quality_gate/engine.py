"""Quality validation engine (ADR-050).

Loads expectation suites from YAML and evaluates datasets.
In production, integrates with Great Expectations. This implementation
provides a lightweight in-memory runner for core validation logic.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import uuid

import yaml
from odg_core.models import QualityReport
from odg_core.quality.dimensions import DAMAScorer

logger = logging.getLogger(__name__)

_CONFIG_DIR = Path(__file__).resolve().parents[4] / "config" / "expectations"


class QualityEngine:
    """Validates datasets against expectation suites and produces DQ reports."""

    def __init__(self, expectations_dir: str | Path | None = None) -> None:
        self._dir = Path(expectations_dir) if expectations_dir else _CONFIG_DIR
        self._scorer = DAMAScorer()
        self._reports: dict[uuid.UUID, QualityReport] = {}

    def _load_suite(self, suite_name: str, layer: str) -> list[dict[str, Any]]:
        """Load expectations from a YAML suite file."""
        # Try suite_name directly, then fall back to default_{layer}
        candidates = [
            self._dir / f"{suite_name}.yaml",
            self._dir / f"default_{layer}.yaml",
        ]
        for path in candidates:
            if path.exists():
                with path.open() as f:
                    data = yaml.safe_load(f)
                return data.get("expectations", []) if isinstance(data, dict) else []

        logger.warning("No expectation suite found for %s/%s", suite_name, layer)
        return []

    def validate(
        self,
        *,
        dataset_id: str,
        domain_id: str,
        layer: str,
        suite_name: str = "default",
        triggered_by: uuid.UUID | None = None,
    ) -> QualityReport:
        """Run validation and produce a quality report.

        In this lightweight implementation, all expectations are assumed to pass
        unless explicitly marked otherwise. Production deployments should
        integrate with Great Expectations for actual data validation.
        """
        expectations = self._load_suite(suite_name, layer)
        total = len(expectations)

        # Simulate validation results (all pass by default)
        results = [{"expectation_type": exp.get("expectation_type", ""), "success": True} for exp in expectations]

        passed = sum(1 for r in results if r["success"])
        failed = total - passed

        # Score across DAMA dimensions
        dimension_scores = self._scorer.score(results)
        dq_score = self._scorer.overall_score(dimension_scores)

        report = QualityReport(
            dataset_id=dataset_id,
            domain_id=domain_id,
            layer=layer,
            suite_name=f"{suite_name}_{layer}" if suite_name == "default" else suite_name,
            dq_score=dq_score,
            dimension_scores=dimension_scores,
            expectations_passed=passed,
            expectations_failed=failed,
            expectations_total=total,
            triggered_by=triggered_by,
        )

        self._reports[report.id] = report
        logger.info(
            "Quality report %s: %s/%s DQ=%.2f (%d/%d passed)",
            report.id,
            domain_id,
            dataset_id,
            dq_score,
            passed,
            total,
        )

        return report

    def get_report(self, report_id: uuid.UUID) -> QualityReport | None:
        """Retrieve a cached quality report by ID."""
        return self._reports.get(report_id)
