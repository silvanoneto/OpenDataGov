"""Tests for the compliance module (ADR-110, ADR-111, ADR-112, ADR-113)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pytest

from odg_core.compliance.ai_risk import (
    DEFAULT_HIGH_RISK_INDICATORS,
    DEFAULT_LIMITED_RISK_INDICATORS,
    classify_ai_risk,
    get_required_controls,
)
from odg_core.compliance.dama import DAMA_KNOWLEDGE_AREAS, DAMAChecker
from odg_core.compliance.dama_coverage import (
    DAMACoverageReport,
    KnowledgeAreaCoverage,
    build_default_coverage,
)
from odg_core.compliance.eu_ai_act import EUAIActChecker
from odg_core.compliance.gdpr import GDPRChecker
from odg_core.compliance.iso_42001 import ISO42001Checker
from odg_core.compliance.lgpd import LGPDChecker
from odg_core.compliance.model_card import ModelCard, ModelCardEthics, ModelCardMetrics
from odg_core.compliance.nist_ai_rmf import NISTAIRMFChecker
from odg_core.compliance.protocols import (
    ComplianceChecker,
    ComplianceFinding,
    ComplianceResult,
)
from odg_core.compliance.registry import ComplianceRegistry, create_default_registry
from odg_core.compliance.sox import SOXChecker
from odg_core.enums import AIRiskLevel, ComplianceFramework, DAMADimension

# ---------------------------------------------------------------------------
# ai_risk.py
# ---------------------------------------------------------------------------


class TestClassifyAIRisk:
    def test_high_risk_biometric(self) -> None:
        result = classify_ai_risk(["biometric_identification"])
        assert result == AIRiskLevel.HIGH

    def test_high_risk_critical_infrastructure(self) -> None:
        result = classify_ai_risk(["critical_infrastructure"])
        assert result == AIRiskLevel.HIGH

    def test_high_risk_education_scoring(self) -> None:
        result = classify_ai_risk(["education_scoring"])
        assert result == AIRiskLevel.HIGH

    def test_high_risk_employment_decisions(self) -> None:
        result = classify_ai_risk(["employment_decisions"])
        assert result == AIRiskLevel.HIGH

    def test_high_risk_essential_services(self) -> None:
        result = classify_ai_risk(["essential_services"])
        assert result == AIRiskLevel.HIGH

    def test_high_risk_law_enforcement(self) -> None:
        result = classify_ai_risk(["law_enforcement"])
        assert result == AIRiskLevel.HIGH

    def test_high_risk_migration_control(self) -> None:
        result = classify_ai_risk(["migration_control"])
        assert result == AIRiskLevel.HIGH

    def test_limited_risk_chatbot(self) -> None:
        result = classify_ai_risk(["chatbot"])
        assert result == AIRiskLevel.LIMITED

    def test_limited_risk_emotion_recognition(self) -> None:
        result = classify_ai_risk(["emotion_recognition"])
        assert result == AIRiskLevel.LIMITED

    def test_limited_risk_deepfake(self) -> None:
        result = classify_ai_risk(["deepfake_generation"])
        assert result == AIRiskLevel.LIMITED

    def test_limited_risk_content_generation(self) -> None:
        result = classify_ai_risk(["content_generation"])
        assert result == AIRiskLevel.LIMITED

    def test_minimal_risk_empty_capabilities(self) -> None:
        result = classify_ai_risk([])
        assert result == AIRiskLevel.MINIMAL

    def test_minimal_risk_unrecognised_capability(self) -> None:
        result = classify_ai_risk(["recommendation_engine"])
        assert result == AIRiskLevel.MINIMAL

    def test_high_takes_precedence_over_limited(self) -> None:
        result = classify_ai_risk(["chatbot", "law_enforcement"])
        assert result == AIRiskLevel.HIGH

    def test_custom_high_risk_indicators(self) -> None:
        result = classify_ai_risk(
            ["custom_capability"],
            high_risk_indicators=frozenset({"custom_capability"}),
        )
        assert result == AIRiskLevel.HIGH

    def test_custom_limited_risk_indicators(self) -> None:
        result = classify_ai_risk(
            ["custom_limited"],
            high_risk_indicators=frozenset(),
            limited_risk_indicators=frozenset({"custom_limited"}),
        )
        assert result == AIRiskLevel.LIMITED

    def test_default_indicators_are_frozensets(self) -> None:
        assert isinstance(DEFAULT_HIGH_RISK_INDICATORS, frozenset)
        assert isinstance(DEFAULT_LIMITED_RISK_INDICATORS, frozenset)
        assert len(DEFAULT_HIGH_RISK_INDICATORS) == 7
        assert len(DEFAULT_LIMITED_RISK_INDICATORS) == 4


class TestGetRequiredControls:
    def test_minimal_risk_controls(self) -> None:
        controls = get_required_controls(AIRiskLevel.MINIMAL)
        assert controls == {"transparency_info": True}

    def test_limited_risk_controls(self) -> None:
        controls = get_required_controls(AIRiskLevel.LIMITED)
        assert controls["transparency_info"] is True
        assert controls["user_notification"] is True
        assert len(controls) == 2

    def test_high_risk_controls(self) -> None:
        controls = get_required_controls(AIRiskLevel.HIGH)
        assert controls["transparency_info"] is True
        assert controls["risk_management_system"] is True
        assert controls["data_governance"] is True
        assert controls["technical_documentation"] is True
        assert controls["record_keeping"] is True
        assert controls["human_oversight"] is True
        assert controls["accuracy_robustness"] is True
        assert controls["conformity_assessment"] is True
        assert len(controls) == 8


# ---------------------------------------------------------------------------
# protocols.py
# ---------------------------------------------------------------------------


class TestComplianceFinding:
    def test_construction(self) -> None:
        finding = ComplianceFinding(
            rule_id="TEST-1",
            severity="high",
            description="test desc",
            recommendation="fix it",
        )
        assert finding.rule_id == "TEST-1"
        assert finding.severity == "high"
        assert finding.description == "test desc"
        assert finding.recommendation == "fix it"


class TestComplianceResult:
    def test_construction_minimal(self) -> None:
        result = ComplianceResult(
            framework=ComplianceFramework.GDPR,
            passed=True,
            score=1.0,
        )
        assert result.framework == ComplianceFramework.GDPR
        assert result.passed is True
        assert result.score == 1.0
        assert result.findings == []
        assert result.metadata == {}

    def test_construction_with_findings(self) -> None:
        finding = ComplianceFinding(
            rule_id="R1",
            severity="low",
            description="d",
            recommendation="r",
        )
        result = ComplianceResult(
            framework=ComplianceFramework.SOX,
            passed=False,
            score=0.5,
            findings=[finding],
            metadata={"key": "val"},
        )
        assert len(result.findings) == 1
        assert result.metadata["key"] == "val"

    def test_score_bounds(self) -> None:
        with pytest.raises(ValueError):
            ComplianceResult(
                framework=ComplianceFramework.GDPR,
                passed=True,
                score=1.5,
            )
        with pytest.raises(ValueError):
            ComplianceResult(
                framework=ComplianceFramework.GDPR,
                passed=True,
                score=-0.1,
            )


class TestComplianceCheckerProtocol:
    def test_gdpr_checker_satisfies_protocol(self) -> None:
        assert isinstance(GDPRChecker(), ComplianceChecker)

    def test_lgpd_checker_satisfies_protocol(self) -> None:
        assert isinstance(LGPDChecker(), ComplianceChecker)

    def test_sox_checker_satisfies_protocol(self) -> None:
        assert isinstance(SOXChecker(), ComplianceChecker)

    def test_eu_ai_act_checker_satisfies_protocol(self) -> None:
        assert isinstance(EUAIActChecker(), ComplianceChecker)

    def test_nist_checker_satisfies_protocol(self) -> None:
        assert isinstance(NISTAIRMFChecker(), ComplianceChecker)

    def test_iso42001_checker_satisfies_protocol(self) -> None:
        assert isinstance(ISO42001Checker(), ComplianceChecker)

    def test_dama_checker_satisfies_protocol(self) -> None:
        assert isinstance(DAMAChecker(), ComplianceChecker)


# ---------------------------------------------------------------------------
# gdpr.py
# ---------------------------------------------------------------------------


class TestGDPRChecker:
    def test_framework_property(self) -> None:
        assert GDPRChecker().framework == ComplianceFramework.GDPR

    def test_fully_compliant(self) -> None:
        context: dict[str, Any] = {
            "has_lawful_basis": True,
            "supports_data_portability": True,
            "has_dpia": True,
            "transfers_outside_eu": False,
        }
        result = GDPRChecker().check(context)
        assert result.passed is True
        assert result.score == 1.0
        assert result.findings == []
        assert result.framework == ComplianceFramework.GDPR

    def test_no_lawful_basis(self) -> None:
        context: dict[str, Any] = {
            "has_lawful_basis": False,
            "supports_data_portability": True,
            "has_dpia": True,
        }
        result = GDPRChecker().check(context)
        assert result.passed is False
        assert any(f.rule_id == "GDPR-6" for f in result.findings)
        assert any(f.severity == "critical" for f in result.findings)

    def test_no_data_portability(self) -> None:
        context: dict[str, Any] = {
            "has_lawful_basis": True,
            "supports_data_portability": False,
            "has_dpia": True,
        }
        result = GDPRChecker().check(context)
        assert result.passed is True  # no critical findings
        assert any(f.rule_id == "GDPR-20" for f in result.findings)

    def test_no_dpia(self) -> None:
        context: dict[str, Any] = {
            "has_lawful_basis": True,
            "supports_data_portability": True,
            "has_dpia": False,
        }
        result = GDPRChecker().check(context)
        assert result.passed is True
        assert any(f.rule_id == "GDPR-35" for f in result.findings)

    def test_cross_border_transfer_without_adequacy(self) -> None:
        context: dict[str, Any] = {
            "has_lawful_basis": True,
            "supports_data_portability": True,
            "has_dpia": True,
            "transfers_outside_eu": True,
            "has_adequacy_decision": False,
        }
        result = GDPRChecker().check(context)
        assert result.passed is False
        assert any(f.rule_id == "GDPR-45" for f in result.findings)

    def test_cross_border_transfer_with_adequacy(self) -> None:
        context: dict[str, Any] = {
            "has_lawful_basis": True,
            "supports_data_portability": True,
            "has_dpia": True,
            "transfers_outside_eu": True,
            "has_adequacy_decision": True,
        }
        result = GDPRChecker().check(context)
        assert result.passed is True
        assert result.score == 1.0

    def test_all_failures(self) -> None:
        context: dict[str, Any] = {
            "transfers_outside_eu": True,
        }
        result = GDPRChecker().check(context)
        assert result.passed is False
        assert result.score == 0.0
        assert len(result.findings) == 4

    def test_empty_context(self) -> None:
        result = GDPRChecker().check({})
        assert result.passed is False
        # No cross-border transfer finding since transfers_outside_eu is falsy
        assert len(result.findings) == 3
        assert result.score == 0.25

    def test_score_computation(self) -> None:
        # 2 out of 4 rules fail
        context: dict[str, Any] = {
            "has_lawful_basis": True,
            "supports_data_portability": True,
            "has_dpia": False,
            "transfers_outside_eu": True,
            "has_adequacy_decision": False,
        }
        result = GDPRChecker().check(context)
        assert result.score == 0.5


# ---------------------------------------------------------------------------
# lgpd.py
# ---------------------------------------------------------------------------


class TestLGPDChecker:
    def test_framework_property(self) -> None:
        assert LGPDChecker().framework == ComplianceFramework.LGPD

    def test_fully_compliant(self) -> None:
        context: dict[str, Any] = {
            "has_legal_basis": True,
            "supports_data_subject_rights": True,
            "has_dpo": True,
            "has_security_measures": True,
        }
        result = LGPDChecker().check(context)
        assert result.passed is True
        assert result.score == 1.0
        assert result.findings == []

    def test_no_legal_basis(self) -> None:
        context: dict[str, Any] = {
            "has_legal_basis": False,
            "supports_data_subject_rights": True,
            "has_dpo": True,
            "has_security_measures": True,
        }
        result = LGPDChecker().check(context)
        assert result.passed is False
        assert any(f.rule_id == "LGPD-7" for f in result.findings)
        assert any(f.severity == "critical" for f in result.findings)

    def test_no_data_subject_rights(self) -> None:
        context: dict[str, Any] = {
            "has_legal_basis": True,
            "supports_data_subject_rights": False,
            "has_dpo": True,
            "has_security_measures": True,
        }
        result = LGPDChecker().check(context)
        assert result.passed is True
        assert any(f.rule_id == "LGPD-18" for f in result.findings)

    def test_no_dpo(self) -> None:
        context: dict[str, Any] = {
            "has_legal_basis": True,
            "supports_data_subject_rights": True,
            "has_dpo": False,
            "has_security_measures": True,
        }
        result = LGPDChecker().check(context)
        assert result.passed is True
        assert any(f.rule_id == "LGPD-41" for f in result.findings)

    def test_no_security_measures(self) -> None:
        context: dict[str, Any] = {
            "has_legal_basis": True,
            "supports_data_subject_rights": True,
            "has_dpo": True,
            "has_security_measures": False,
        }
        result = LGPDChecker().check(context)
        assert result.passed is True
        assert any(f.rule_id == "LGPD-46" for f in result.findings)

    def test_all_failures(self) -> None:
        result = LGPDChecker().check({})
        assert result.passed is False
        assert result.score == 0.0
        assert len(result.findings) == 4

    def test_score_partial(self) -> None:
        context: dict[str, Any] = {
            "has_legal_basis": True,
            "supports_data_subject_rights": True,
        }
        result = LGPDChecker().check(context)
        assert result.passed is True  # no critical
        assert result.score == 0.5


# ---------------------------------------------------------------------------
# sox.py
# ---------------------------------------------------------------------------


class TestSOXChecker:
    def test_framework_property(self) -> None:
        assert SOXChecker().framework == ComplianceFramework.SOX

    def test_fully_compliant(self) -> None:
        context: dict[str, Any] = {
            "has_audit_trail": True,
            "has_access_controls": True,
            "has_change_management": True,
            "has_data_retention_policy": True,
        }
        result = SOXChecker().check(context)
        assert result.passed is True
        assert result.score == 1.0
        assert result.findings == []

    def test_no_audit_trail(self) -> None:
        context: dict[str, Any] = {
            "has_audit_trail": False,
            "has_access_controls": True,
            "has_change_management": True,
            "has_data_retention_policy": True,
        }
        result = SOXChecker().check(context)
        assert result.passed is False
        assert any(f.rule_id == "SOX-302" for f in result.findings)
        assert any(f.severity == "critical" for f in result.findings)

    def test_no_access_controls(self) -> None:
        context: dict[str, Any] = {
            "has_audit_trail": True,
            "has_access_controls": False,
            "has_change_management": True,
            "has_data_retention_policy": True,
        }
        result = SOXChecker().check(context)
        assert result.passed is False
        assert any(f.rule_id == "SOX-404-ACCESS" for f in result.findings)

    def test_no_change_management(self) -> None:
        context: dict[str, Any] = {
            "has_audit_trail": True,
            "has_access_controls": True,
            "has_change_management": False,
            "has_data_retention_policy": True,
        }
        result = SOXChecker().check(context)
        assert result.passed is True  # not critical
        assert any(f.rule_id == "SOX-404-CHANGE" for f in result.findings)

    def test_no_data_retention(self) -> None:
        context: dict[str, Any] = {
            "has_audit_trail": True,
            "has_access_controls": True,
            "has_change_management": True,
            "has_data_retention_policy": False,
        }
        result = SOXChecker().check(context)
        assert result.passed is True
        assert any(f.rule_id == "SOX-802" for f in result.findings)

    def test_all_failures(self) -> None:
        result = SOXChecker().check({})
        assert result.passed is False
        assert result.score == 0.0
        assert len(result.findings) == 4

    def test_score_partial(self) -> None:
        context: dict[str, Any] = {
            "has_audit_trail": True,
            "has_access_controls": True,
        }
        result = SOXChecker().check(context)
        assert result.passed is True  # no critical
        assert result.score == 0.5


# ---------------------------------------------------------------------------
# eu_ai_act.py
# ---------------------------------------------------------------------------


class TestEUAIActChecker:
    def test_framework_property(self) -> None:
        assert EUAIActChecker().framework == ComplianceFramework.EU_AI_ACT

    def test_minimal_risk_fully_compliant(self) -> None:
        context: dict[str, Any] = {"ai_risk_level": "minimal"}
        result = EUAIActChecker().check(context)
        assert result.passed is True
        assert result.score == 1.0
        assert result.findings == []
        assert result.metadata == {"risk_level": "minimal"}

    def test_minimal_risk_default(self) -> None:
        result = EUAIActChecker().check({})
        assert result.passed is True
        assert result.score == 1.0
        assert result.metadata["risk_level"] == "minimal"

    def test_limited_risk_with_transparency(self) -> None:
        context: dict[str, Any] = {
            "ai_risk_level": "limited",
            "has_transparency_info": True,
        }
        result = EUAIActChecker().check(context)
        assert result.passed is True
        assert result.score == 1.0

    def test_limited_risk_without_transparency(self) -> None:
        context: dict[str, Any] = {
            "ai_risk_level": "limited",
            "has_transparency_info": False,
        }
        result = EUAIActChecker().check(context)
        assert result.passed is True  # no critical
        assert any(f.rule_id == "AI-ACT-52" for f in result.findings)
        assert result.score == 0.0  # 0 passed / 1 total

    def test_high_risk_fully_compliant(self) -> None:
        context: dict[str, Any] = {
            "ai_risk_level": "high",
            "has_risk_management_system": True,
            "has_data_governance": True,
            "has_human_oversight": True,
            "has_transparency_info": True,
        }
        result = EUAIActChecker().check(context)
        assert result.passed is True
        assert result.score == 1.0
        assert result.metadata["risk_level"] == "high"

    def test_high_risk_no_risk_management(self) -> None:
        context: dict[str, Any] = {
            "ai_risk_level": "high",
            "has_data_governance": True,
            "has_human_oversight": True,
            "has_transparency_info": True,
        }
        result = EUAIActChecker().check(context)
        assert result.passed is False
        assert any(f.rule_id == "AI-ACT-9" for f in result.findings)

    def test_high_risk_no_data_governance(self) -> None:
        context: dict[str, Any] = {
            "ai_risk_level": "high",
            "has_risk_management_system": True,
            "has_human_oversight": True,
            "has_transparency_info": True,
        }
        result = EUAIActChecker().check(context)
        assert result.passed is False
        assert any(f.rule_id == "AI-ACT-10" for f in result.findings)

    def test_high_risk_no_human_oversight(self) -> None:
        context: dict[str, Any] = {
            "ai_risk_level": "high",
            "has_risk_management_system": True,
            "has_data_governance": True,
            "has_transparency_info": True,
        }
        result = EUAIActChecker().check(context)
        assert result.passed is True  # human oversight finding is "high", not critical
        assert any(f.rule_id == "AI-ACT-14" for f in result.findings)

    def test_high_risk_no_transparency(self) -> None:
        context: dict[str, Any] = {
            "ai_risk_level": "high",
            "has_risk_management_system": True,
            "has_data_governance": True,
            "has_human_oversight": True,
            "has_transparency_info": False,
        }
        result = EUAIActChecker().check(context)
        assert result.passed is True  # medium severity
        assert any(f.rule_id == "AI-ACT-52" for f in result.findings)

    def test_high_risk_all_failures(self) -> None:
        context: dict[str, Any] = {"ai_risk_level": "high"}
        result = EUAIActChecker().check(context)
        assert result.passed is False
        assert result.score == 0.0
        assert len(result.findings) == 4

    def test_high_risk_score_with_one_finding(self) -> None:
        context: dict[str, Any] = {
            "ai_risk_level": "high",
            "has_risk_management_system": True,
            "has_data_governance": True,
            "has_human_oversight": True,
        }
        result = EUAIActChecker().check(context)
        assert result.score == 0.75  # 3 out of 4


# ---------------------------------------------------------------------------
# nist_ai_rmf.py
# ---------------------------------------------------------------------------


class TestNISTAIRMFChecker:
    def test_framework_property(self) -> None:
        assert NISTAIRMFChecker().framework == ComplianceFramework.NIST_AI_RMF

    def test_fully_compliant(self) -> None:
        context: dict[str, Any] = {
            "has_ai_governance_policy": True,
            "has_ai_risk_mapping": True,
            "has_ai_metrics": True,
            "has_ai_incident_response": True,
        }
        result = NISTAIRMFChecker().check(context)
        assert result.passed is True
        assert result.score == 1.0
        assert result.findings == []

    def test_no_governance_policy(self) -> None:
        context: dict[str, Any] = {
            "has_ai_risk_mapping": True,
            "has_ai_metrics": True,
            "has_ai_incident_response": True,
        }
        result = NISTAIRMFChecker().check(context)
        assert any(f.rule_id == "NIST-GOVERN-1" for f in result.findings)
        assert result.score == 0.75

    def test_no_risk_mapping(self) -> None:
        context: dict[str, Any] = {
            "has_ai_governance_policy": True,
            "has_ai_metrics": True,
            "has_ai_incident_response": True,
        }
        result = NISTAIRMFChecker().check(context)
        assert any(f.rule_id == "NIST-MAP-1" for f in result.findings)

    def test_no_metrics(self) -> None:
        context: dict[str, Any] = {
            "has_ai_governance_policy": True,
            "has_ai_risk_mapping": True,
            "has_ai_incident_response": True,
        }
        result = NISTAIRMFChecker().check(context)
        assert any(f.rule_id == "NIST-MEASURE-1" for f in result.findings)

    def test_no_incident_response(self) -> None:
        context: dict[str, Any] = {
            "has_ai_governance_policy": True,
            "has_ai_risk_mapping": True,
            "has_ai_metrics": True,
        }
        result = NISTAIRMFChecker().check(context)
        assert any(f.rule_id == "NIST-MANAGE-1" for f in result.findings)

    def test_all_failures(self) -> None:
        result = NISTAIRMFChecker().check({})
        assert result.passed is False
        assert result.score == 0.0
        assert len(result.findings) == 4

    def test_pass_threshold_exactly_half(self) -> None:
        # 2 out of 4 => score 0.5, passed threshold is >= 0.5
        context: dict[str, Any] = {
            "has_ai_governance_policy": True,
            "has_ai_risk_mapping": True,
        }
        result = NISTAIRMFChecker().check(context)
        assert result.score == 0.5
        assert result.passed is True

    def test_pass_threshold_below_half(self) -> None:
        context: dict[str, Any] = {
            "has_ai_governance_policy": True,
        }
        result = NISTAIRMFChecker().check(context)
        assert result.score == 0.25
        assert result.passed is False


# ---------------------------------------------------------------------------
# iso_42001.py
# ---------------------------------------------------------------------------


class TestISO42001Checker:
    def test_framework_property(self) -> None:
        assert ISO42001Checker().framework == ComplianceFramework.ISO_42001

    def test_fully_compliant(self) -> None:
        context: dict[str, Any] = {
            "has_ai_scope_definition": True,
            "has_ai_leadership_commitment": True,
            "has_ai_risk_assessment": True,
            "has_ai_lifecycle_management": True,
            "has_ai_monitoring": True,
        }
        result = ISO42001Checker().check(context)
        assert result.passed is True
        assert result.score == 1.0
        assert result.findings == []

    def test_no_scope_definition(self) -> None:
        context: dict[str, Any] = {
            "has_ai_leadership_commitment": True,
            "has_ai_risk_assessment": True,
            "has_ai_lifecycle_management": True,
            "has_ai_monitoring": True,
        }
        result = ISO42001Checker().check(context)
        assert any(f.rule_id == "ISO42001-4" for f in result.findings)

    def test_no_leadership(self) -> None:
        context: dict[str, Any] = {
            "has_ai_scope_definition": True,
            "has_ai_risk_assessment": True,
            "has_ai_lifecycle_management": True,
            "has_ai_monitoring": True,
        }
        result = ISO42001Checker().check(context)
        assert any(f.rule_id == "ISO42001-5" for f in result.findings)

    def test_no_risk_assessment(self) -> None:
        context: dict[str, Any] = {
            "has_ai_scope_definition": True,
            "has_ai_leadership_commitment": True,
            "has_ai_lifecycle_management": True,
            "has_ai_monitoring": True,
        }
        result = ISO42001Checker().check(context)
        assert any(f.rule_id == "ISO42001-6" for f in result.findings)

    def test_no_lifecycle_management(self) -> None:
        context: dict[str, Any] = {
            "has_ai_scope_definition": True,
            "has_ai_leadership_commitment": True,
            "has_ai_risk_assessment": True,
            "has_ai_monitoring": True,
        }
        result = ISO42001Checker().check(context)
        assert any(f.rule_id == "ISO42001-8" for f in result.findings)

    def test_no_monitoring(self) -> None:
        context: dict[str, Any] = {
            "has_ai_scope_definition": True,
            "has_ai_leadership_commitment": True,
            "has_ai_risk_assessment": True,
            "has_ai_lifecycle_management": True,
        }
        result = ISO42001Checker().check(context)
        assert any(f.rule_id == "ISO42001-9" for f in result.findings)

    def test_all_failures(self) -> None:
        result = ISO42001Checker().check({})
        assert result.passed is False
        assert result.score == 0.0
        assert len(result.findings) == 5

    def test_pass_threshold_at_60_percent(self) -> None:
        # 3 out of 5 => 0.6, threshold >= 0.6
        context: dict[str, Any] = {
            "has_ai_scope_definition": True,
            "has_ai_leadership_commitment": True,
            "has_ai_risk_assessment": True,
        }
        result = ISO42001Checker().check(context)
        assert result.score == 0.6
        assert result.passed is True

    def test_pass_threshold_below_60_percent(self) -> None:
        # 2 out of 5 => 0.4
        context: dict[str, Any] = {
            "has_ai_scope_definition": True,
            "has_ai_leadership_commitment": True,
        }
        result = ISO42001Checker().check(context)
        assert result.score == 0.4
        assert result.passed is False


# ---------------------------------------------------------------------------
# dama.py
# ---------------------------------------------------------------------------


class TestDAMAChecker:
    def test_framework_property(self) -> None:
        assert DAMAChecker().framework == ComplianceFramework.DAMA_DMBOK

    def test_fully_compliant(self) -> None:
        context: dict[str, Any] = {
            "implemented_areas": list(DAMA_KNOWLEDGE_AREAS.keys()),
            "quality_dimensions": [dim.value for dim in DAMADimension],
        }
        result = DAMAChecker().check(context)
        assert result.passed is True
        assert result.score == 1.0
        assert result.findings == []

    def test_no_areas_implemented(self) -> None:
        result = DAMAChecker().check({})
        assert result.passed is False
        assert result.score == 0.0
        total_expected = len(DAMA_KNOWLEDGE_AREAS) + len(DAMADimension)
        assert len(result.findings) == total_expected

    def test_partial_areas(self) -> None:
        context: dict[str, Any] = {
            "implemented_areas": ["data_governance", "data_quality"],
            "quality_dimensions": [dim.value for dim in DAMADimension],
        }
        result = DAMAChecker().check(context)
        # 9 missing areas out of 11 + 0 missing dimensions out of 6 = 9 findings
        missing_areas = len(DAMA_KNOWLEDGE_AREAS) - 2
        assert len(result.findings) == missing_areas

    def test_critical_areas_severity(self) -> None:
        # data_governance, data_quality, data_security should be "high" severity
        context: dict[str, Any] = {
            "implemented_areas": [],
            "quality_dimensions": [dim.value for dim in DAMADimension],
        }
        result = DAMAChecker().check(context)
        high_severity_ids = {f.rule_id for f in result.findings if f.severity == "high"}
        assert "DAMA-DATA_GOVERNANCE" in high_severity_ids
        assert "DAMA-DATA_QUALITY" in high_severity_ids
        assert "DAMA-DATA_SECURITY" in high_severity_ids

    def test_non_critical_areas_are_medium(self) -> None:
        context: dict[str, Any] = {
            "implemented_areas": ["data_governance", "data_quality", "data_security"],
            "quality_dimensions": [dim.value for dim in DAMADimension],
        }
        result = DAMAChecker().check(context)
        for finding in result.findings:
            assert finding.severity == "medium"

    def test_missing_quality_dimensions(self) -> None:
        context: dict[str, Any] = {
            "implemented_areas": list(DAMA_KNOWLEDGE_AREAS.keys()),
            "quality_dimensions": [],
        }
        result = DAMAChecker().check(context)
        assert len(result.findings) == len(DAMADimension)
        for finding in result.findings:
            assert finding.rule_id.startswith("DAMA-DQ-")

    def test_pass_threshold_70_percent(self) -> None:
        total = len(DAMA_KNOWLEDGE_AREAS) + len(DAMADimension)
        # We need at least 70% passing to pass
        # 70% of 17 = 11.9, so need 12 passing (5 findings max)
        needed_passing = int(total * 0.7) + 1
        needed_areas = min(needed_passing, len(DAMA_KNOWLEDGE_AREAS))
        areas = list(DAMA_KNOWLEDGE_AREAS.keys())[:needed_areas]
        remaining = needed_passing - needed_areas
        dims = [dim.value for dim in list(DAMADimension)[:remaining]]

        context: dict[str, Any] = {
            "implemented_areas": areas,
            "quality_dimensions": dims,
        }
        result = DAMAChecker().check(context)
        assert result.score >= 0.7
        assert result.passed is True

    def test_knowledge_areas_constant(self) -> None:
        assert len(DAMA_KNOWLEDGE_AREAS) == 11
        assert "data_governance" in DAMA_KNOWLEDGE_AREAS
        assert "document_management" in DAMA_KNOWLEDGE_AREAS

    def test_finding_recommendations_include_description(self) -> None:
        context: dict[str, Any] = {
            "implemented_areas": [],
            "quality_dimensions": [dim.value for dim in DAMADimension],
        }
        result = DAMAChecker().check(context)
        for finding in result.findings:
            assert finding.recommendation.startswith("Implement: ")


# ---------------------------------------------------------------------------
# dama_coverage.py
# ---------------------------------------------------------------------------


class TestKnowledgeAreaCoverage:
    def test_defaults(self) -> None:
        kac = KnowledgeAreaCoverage(area="Test", description="Test area")
        assert kac.components == []
        assert kac.adrs == []
        assert kac.coverage_level == "none"

    def test_full_construction(self) -> None:
        kac = KnowledgeAreaCoverage(
            area="Test",
            description="Test area",
            components=["comp1", "comp2"],
            adrs=["ADR-001"],
            coverage_level="full",
        )
        assert kac.area == "Test"
        assert len(kac.components) == 2
        assert len(kac.adrs) == 1
        assert kac.coverage_level == "full"


class TestDAMACoverageReport:
    def test_empty_report(self) -> None:
        report = DAMACoverageReport()
        assert report.areas == []
        assert report.overall_coverage == 0.0

    def test_compute_coverage_empty(self) -> None:
        report = DAMACoverageReport()
        result = report.compute_coverage()
        assert result == 0.0

    def test_compute_coverage_all_full(self) -> None:
        areas = [KnowledgeAreaCoverage(area=f"Area{i}", description="d", coverage_level="full") for i in range(3)]
        report = DAMACoverageReport(areas=areas)
        result = report.compute_coverage()
        assert result == 1.0
        assert report.overall_coverage == 1.0

    def test_compute_coverage_all_none(self) -> None:
        areas = [KnowledgeAreaCoverage(area=f"Area{i}", description="d", coverage_level="none") for i in range(3)]
        report = DAMACoverageReport(areas=areas)
        result = report.compute_coverage()
        assert result == 0.0

    def test_compute_coverage_mixed(self) -> None:
        areas = [
            KnowledgeAreaCoverage(area="A", description="d", coverage_level="full"),
            KnowledgeAreaCoverage(area="B", description="d", coverage_level="partial"),
            KnowledgeAreaCoverage(area="C", description="d", coverage_level="none"),
        ]
        report = DAMACoverageReport(areas=areas)
        result = report.compute_coverage()
        assert result == pytest.approx(0.5, abs=1e-6)

    def test_compute_coverage_all_partial(self) -> None:
        areas = [KnowledgeAreaCoverage(area=f"Area{i}", description="d", coverage_level="partial") for i in range(4)]
        report = DAMACoverageReport(areas=areas)
        result = report.compute_coverage()
        assert result == 0.5

    def test_compute_coverage_unknown_level_treated_as_zero(self) -> None:
        areas = [
            KnowledgeAreaCoverage(area="A", description="d", coverage_level="unknown"),
        ]
        report = DAMACoverageReport(areas=areas)
        result = report.compute_coverage()
        assert result == 0.0


class TestBuildDefaultCoverage:
    def test_returns_report(self) -> None:
        report = build_default_coverage()
        assert isinstance(report, DAMACoverageReport)

    def test_has_11_areas(self) -> None:
        report = build_default_coverage()
        assert len(report.areas) == 11

    def test_coverage_computed(self) -> None:
        report = build_default_coverage()
        assert report.overall_coverage > 0.0

    def test_document_management_is_none(self) -> None:
        report = build_default_coverage()
        doc_mgmt = [a for a in report.areas if a.area == "Document & Content Management"]
        assert len(doc_mgmt) == 1
        assert doc_mgmt[0].coverage_level == "none"
        assert doc_mgmt[0].components == []

    def test_reference_data_is_partial(self) -> None:
        report = build_default_coverage()
        ref_data = [a for a in report.areas if a.area == "Reference & Master Data"]
        assert len(ref_data) == 1
        assert ref_data[0].coverage_level == "partial"

    def test_data_governance_is_full(self) -> None:
        report = build_default_coverage()
        dg = [a for a in report.areas if a.area == "Data Governance"]
        assert len(dg) == 1
        assert dg[0].coverage_level == "full"

    def test_overall_coverage_value(self) -> None:
        report = build_default_coverage()
        # 9 full (1.0 each) + 1 partial (0.5) + 1 none (0.0) = 9.5 / 11
        expected = 9.5 / 11
        assert report.overall_coverage == pytest.approx(expected, abs=1e-6)


# ---------------------------------------------------------------------------
# model_card.py
# ---------------------------------------------------------------------------


class TestModelCardMetrics:
    def test_construction(self) -> None:
        m = ModelCardMetrics(metric_name="accuracy", value=0.95)
        assert m.metric_name == "accuracy"
        assert m.value == 0.95
        assert m.dataset == ""
        assert m.description == ""

    def test_with_all_fields(self) -> None:
        m = ModelCardMetrics(
            metric_name="f1",
            value=0.88,
            dataset="validation-set",
            description="F1 macro",
        )
        assert m.dataset == "validation-set"
        assert m.description == "F1 macro"


class TestModelCardEthics:
    def test_defaults(self) -> None:
        e = ModelCardEthics()
        assert e.intended_use == ""
        assert e.out_of_scope_use == ""
        assert e.known_biases == []
        assert e.mitigation_strategies == []

    def test_full_construction(self) -> None:
        e = ModelCardEthics(
            intended_use="classification",
            out_of_scope_use="medical diagnosis",
            known_biases=["gender", "age"],
            mitigation_strategies=["re-sampling"],
        )
        assert e.intended_use == "classification"
        assert len(e.known_biases) == 2
        assert len(e.mitigation_strategies) == 1


class TestModelCard:
    def test_minimal_construction(self) -> None:
        card = ModelCard(
            model_name="test-model",
            model_version="1.0",
            owner="team-a",
        )
        assert card.model_name == "test-model"
        assert card.model_version == "1.0"
        assert card.owner == "team-a"
        assert card.description == ""
        assert card.risk_level == AIRiskLevel.MINIMAL
        assert card.expert_capability == ""
        assert card.model_type == ""
        assert card.training_data_description == ""
        assert card.evaluation_data_description == ""
        assert card.metrics == []
        assert card.limitations == []
        assert card.regulatory_requirements == []
        assert card.approved_by == ""
        assert card.last_reviewed_at is None

    def test_full_construction(self) -> None:
        ethics = ModelCardEthics(
            intended_use="credit scoring",
            known_biases=["income-bias"],
        )
        metrics = [
            ModelCardMetrics(metric_name="accuracy", value=0.92, dataset="test"),
        ]
        card = ModelCard(
            model_name="credit-scorer",
            model_version="2.1",
            owner="risk-team",
            description="Credit risk prediction model",
            risk_level=AIRiskLevel.HIGH,
            expert_capability="data_analysis",
            model_type="gradient_boosting",
            training_data_description="3 years of loan data",
            evaluation_data_description="hold-out set",
            metrics=metrics,
            ethics=ethics,
            limitations=["Cannot handle new markets"],
            regulatory_requirements=["EU AI Act Art. 9"],
            approved_by="chief-data-officer",
        )
        assert card.risk_level == AIRiskLevel.HIGH
        assert len(card.metrics) == 1
        assert card.ethics.intended_use == "credit scoring"
        assert len(card.limitations) == 1
        assert len(card.regulatory_requirements) == 1

    def test_created_at_is_set(self) -> None:
        card = ModelCard(
            model_name="m",
            model_version="1",
            owner="o",
        )
        assert isinstance(card.created_at, datetime)

    def test_ethics_default_is_instance(self) -> None:
        card = ModelCard(
            model_name="m",
            model_version="1",
            owner="o",
        )
        assert isinstance(card.ethics, ModelCardEthics)


# ---------------------------------------------------------------------------
# registry.py
# ---------------------------------------------------------------------------


class TestComplianceRegistry:
    def test_register_and_check(self) -> None:
        registry = ComplianceRegistry()
        registry.register(GDPRChecker())
        result = registry.check(
            ComplianceFramework.GDPR,
            {"has_lawful_basis": True, "supports_data_portability": True, "has_dpia": True},
        )
        assert result.framework == ComplianceFramework.GDPR
        assert result.passed is True

    def test_check_unregistered_framework_raises(self) -> None:
        registry = ComplianceRegistry()
        with pytest.raises(ValueError, match="No checker registered for"):
            registry.check(ComplianceFramework.GDPR, {})

    def test_registered_frameworks(self) -> None:
        registry = ComplianceRegistry()
        registry.register(GDPRChecker())
        registry.register(SOXChecker())
        frameworks = registry.registered_frameworks
        assert ComplianceFramework.GDPR in frameworks
        assert ComplianceFramework.SOX in frameworks
        assert len(frameworks) == 2

    def test_registered_frameworks_empty(self) -> None:
        registry = ComplianceRegistry()
        assert registry.registered_frameworks == []

    def test_check_all_empty(self) -> None:
        registry = ComplianceRegistry()
        results = registry.check_all({})
        assert results == {}

    def test_check_all(self) -> None:
        registry = ComplianceRegistry()
        registry.register(GDPRChecker())
        registry.register(SOXChecker())
        results = registry.check_all({})
        assert ComplianceFramework.GDPR in results
        assert ComplianceFramework.SOX in results
        assert len(results) == 2

    def test_register_replaces_existing(self) -> None:
        registry = ComplianceRegistry()
        registry.register(GDPRChecker())
        registry.register(GDPRChecker())
        assert len(registry.registered_frameworks) == 1


class TestCreateDefaultRegistry:
    def test_creates_registry(self) -> None:
        registry = create_default_registry()
        assert isinstance(registry, ComplianceRegistry)

    def test_all_frameworks_registered(self) -> None:
        registry = create_default_registry()
        frameworks = registry.registered_frameworks
        assert ComplianceFramework.LGPD in frameworks
        assert ComplianceFramework.GDPR in frameworks
        assert ComplianceFramework.EU_AI_ACT in frameworks
        assert ComplianceFramework.NIST_AI_RMF in frameworks
        assert ComplianceFramework.ISO_42001 in frameworks
        assert ComplianceFramework.SOX in frameworks
        assert ComplianceFramework.DAMA_DMBOK in frameworks
        assert len(frameworks) == 7

    def test_can_run_all_checks(self) -> None:
        registry = create_default_registry()
        results = registry.check_all({})
        assert len(results) == 7
        for fw, result in results.items():
            assert result.framework == fw

    def test_each_framework_individually(self) -> None:
        registry = create_default_registry()
        for fw in ComplianceFramework:
            result = registry.check(fw, {})
            assert result.framework == fw


# ---------------------------------------------------------------------------
# __init__.py — re-exports
# ---------------------------------------------------------------------------


class TestComplianceInit:
    def test_registry_import(self) -> None:
        from odg_core.compliance import ComplianceRegistry as CompReg

        assert CompReg is ComplianceRegistry

    def test_create_default_registry_import(self) -> None:
        from odg_core.compliance import create_default_registry as cdr

        assert cdr is create_default_registry
