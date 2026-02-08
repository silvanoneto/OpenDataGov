"""Data classification to control mapping (ADR-071).

Maps DataClassification levels to required security controls.
"""

from __future__ import annotations

from odg_core.enums import DataClassification

# Controls required per classification level
CLASSIFICATION_CONTROLS: dict[DataClassification, dict[str, bool]] = {
    DataClassification.PUBLIC: {
        "rbac": False,
        "encryption_at_rest": False,
        "encryption_in_transit": True,
        "pii_masking": False,
        "differential_privacy": False,
        "mfa_required": False,
        "audit_logging": False,
    },
    DataClassification.INTERNAL: {
        "rbac": True,
        "encryption_at_rest": False,
        "encryption_in_transit": True,
        "pii_masking": False,
        "differential_privacy": False,
        "mfa_required": False,
        "audit_logging": True,
    },
    DataClassification.CONFIDENTIAL: {
        "rbac": True,
        "encryption_at_rest": True,
        "encryption_in_transit": True,
        "pii_masking": True,
        "differential_privacy": False,
        "mfa_required": False,
        "audit_logging": True,
    },
    DataClassification.RESTRICTED: {
        "rbac": True,
        "encryption_at_rest": True,
        "encryption_in_transit": True,
        "pii_masking": True,
        "differential_privacy": True,
        "mfa_required": True,
        "audit_logging": True,
    },
    DataClassification.TOP_SECRET: {
        "rbac": True,
        "encryption_at_rest": True,
        "encryption_in_transit": True,
        "pii_masking": True,
        "differential_privacy": True,
        "mfa_required": True,
        "audit_logging": True,
    },
}


def get_required_controls(classification: DataClassification) -> dict[str, bool]:
    """Get the required security controls for a classification level."""
    return CLASSIFICATION_CONTROLS.get(classification, CLASSIFICATION_CONTROLS[DataClassification.INTERNAL])
