"""OpenDataGov SDK resource modules."""

from __future__ import annotations

from odg_sdk.resources.access import AccessRequest, AccessRequestResource
from odg_sdk.resources.datasets import Dataset, DatasetResource
from odg_sdk.resources.decisions import Decision, DecisionApprover, DecisionResource
from odg_sdk.resources.quality import QualityReport, QualityResource

__all__ = [
    "AccessRequest",
    "AccessRequestResource",
    "Dataset",
    "DatasetResource",
    "Decision",
    "DecisionApprover",
    "DecisionResource",
    "QualityReport",
    "QualityResource",
]
