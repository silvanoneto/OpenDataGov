"""AI risk classification per EU AI Act (ADR-111)."""

from __future__ import annotations

from typing import Any

from odg_core.enums import AIRiskLevel

# Default criteria for risk classification
DEFAULT_HIGH_RISK_INDICATORS = frozenset(
    {
        "biometric_identification",
        "critical_infrastructure",
        "education_scoring",
        "employment_decisions",
        "essential_services",
        "law_enforcement",
        "migration_control",
    }
)

DEFAULT_LIMITED_RISK_INDICATORS = frozenset(
    {
        "chatbot",
        "emotion_recognition",
        "deepfake_generation",
        "content_generation",
    }
)


def classify_ai_risk(
    capabilities: list[str],
    *,
    high_risk_indicators: frozenset[str] = DEFAULT_HIGH_RISK_INDICATORS,
    limited_risk_indicators: frozenset[str] = DEFAULT_LIMITED_RISK_INDICATORS,
) -> AIRiskLevel:
    """Classify AI system risk level based on capabilities.

    Args:
        capabilities: List of AI system capability strings.
        high_risk_indicators: Set of capability names that indicate high risk.
        limited_risk_indicators: Set of capability names that indicate limited risk.

    Returns:
        Classified risk level.
    """
    cap_set = set(capabilities)

    if cap_set & high_risk_indicators:
        return AIRiskLevel.HIGH
    if cap_set & limited_risk_indicators:
        return AIRiskLevel.LIMITED
    return AIRiskLevel.MINIMAL


def get_required_controls(risk_level: AIRiskLevel) -> dict[str, Any]:
    """Return required controls for a given AI risk level."""
    controls: dict[str, Any] = {
        "transparency_info": True,
    }

    if risk_level == AIRiskLevel.LIMITED:
        controls["user_notification"] = True

    if risk_level == AIRiskLevel.HIGH:
        controls.update(
            {
                "risk_management_system": True,
                "data_governance": True,
                "technical_documentation": True,
                "record_keeping": True,
                "human_oversight": True,
                "accuracy_robustness": True,
                "conformity_assessment": True,
            }
        )

    return controls
