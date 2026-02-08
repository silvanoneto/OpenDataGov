"""Quarterly SLA review logic (ADR-052)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from odg_core.models import QualitySLA


def needs_review(sla: QualitySLA) -> bool:
    """Check if a quality SLA is due for review."""
    if sla.last_reviewed_at is None:
        return True
    next_review = sla.last_reviewed_at + timedelta(days=sla.review_interval_days)
    return datetime.now(UTC) >= next_review


def filter_due_for_review(slas: list[QualitySLA]) -> list[QualitySLA]:
    """Filter SLAs that are due for review."""
    return [sla for sla in slas if needs_review(sla)]
