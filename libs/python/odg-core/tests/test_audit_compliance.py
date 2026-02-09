"""Tests for audit compliance module."""

from __future__ import annotations

from odg_core.audit.compliance import ComplianceReport


class TestComplianceReportADR:
    def test_generate_adr_compliance_report_structure(self) -> None:
        report = ComplianceReport.generate_adr_compliance_report()
        assert "report_date" in report
        assert report["report_type"] == "ADR Compliance"

    def test_adr_072_section_exists(self) -> None:
        report = ComplianceReport.generate_adr_compliance_report()
        adr072 = report["adr_072_authentication_authorization"]
        assert adr072["status"] == "COMPLIANT"
        assert "requirements" in adr072

    def test_adr_072_keycloak_oidc(self) -> None:
        report = ComplianceReport.generate_adr_compliance_report()
        reqs = report["adr_072_authentication_authorization"]["requirements"]
        assert reqs["keycloak_oidc"]["implemented"] is True
        assert len(reqs["keycloak_oidc"]["evidence"]) > 0

    def test_adr_072_opa_policy(self) -> None:
        report = ComplianceReport.generate_adr_compliance_report()
        reqs = report["adr_072_authentication_authorization"]["requirements"]
        assert reqs["opa_policy_engine"]["implemented"] is True

    def test_adr_072_jwt_validation(self) -> None:
        report = ComplianceReport.generate_adr_compliance_report()
        reqs = report["adr_072_authentication_authorization"]["requirements"]
        assert reqs["jwt_validation"]["implemented"] is True

    def test_adr_072_api_auth(self) -> None:
        report = ComplianceReport.generate_adr_compliance_report()
        reqs = report["adr_072_authentication_authorization"]["requirements"]
        assert reqs["api_auth_enforcement"]["implemented"] is True

    def test_adr_073_section_exists(self) -> None:
        report = ComplianceReport.generate_adr_compliance_report()
        adr073 = report["adr_073_secrets_mtls"]
        assert adr073["status"] == "COMPLIANT"

    def test_adr_073_vault_secrets(self) -> None:
        report = ComplianceReport.generate_adr_compliance_report()
        reqs = report["adr_073_secrets_mtls"]["requirements"]
        assert reqs["vault_secrets_management"]["implemented"] is True

    def test_adr_073_dynamic_credentials(self) -> None:
        report = ComplianceReport.generate_adr_compliance_report()
        reqs = report["adr_073_secrets_mtls"]["requirements"]
        assert reqs["dynamic_credentials"]["implemented"] is True

    def test_adr_073_encryption_at_rest(self) -> None:
        report = ComplianceReport.generate_adr_compliance_report()
        reqs = report["adr_073_secrets_mtls"]["requirements"]
        assert reqs["encryption_at_rest"]["implemented"] is True

    def test_adr_073_mtls(self) -> None:
        report = ComplianceReport.generate_adr_compliance_report()
        reqs = report["adr_073_secrets_mtls"]["requirements"]
        assert reqs["mtls_service_mesh"]["implemented"] is True

    def test_adr_073_grpc_tls(self) -> None:
        report = ComplianceReport.generate_adr_compliance_report()
        reqs = report["adr_073_secrets_mtls"]["requirements"]
        assert reqs["grpc_tls"]["implemented"] is True

    def test_adr_073_kafka_tls(self) -> None:
        report = ComplianceReport.generate_adr_compliance_report()
        reqs = report["adr_073_secrets_mtls"]["requirements"]
        assert reqs["kafka_tls_sasl"]["implemented"] is True

    def test_network_security(self) -> None:
        report = ComplianceReport.generate_adr_compliance_report()
        net = report["network_security"]
        assert net["status"] == "COMPLIANT"
        assert net["requirements"]["network_policies"]["implemented"] is True
        assert net["requirements"]["pod_security"]["implemented"] is True

    def test_audit_compliance_section(self) -> None:
        report = ComplianceReport.generate_adr_compliance_report()
        audit = report["audit_compliance"]
        assert audit["status"] == "COMPLIANT"
        assert audit["requirements"]["encrypted_audit_log"]["implemented"] is True
        assert audit["requirements"]["immutable_audit_trail"]["implemented"] is True


class TestComplianceReportGDPR:
    def test_generate_gdpr_report_structure(self) -> None:
        report = ComplianceReport.generate_gdpr_compliance_report()
        assert report["report_type"] == "GDPR Compliance"
        assert "requirements" in report

    def test_gdpr_article_32(self) -> None:
        report = ComplianceReport.generate_gdpr_compliance_report()
        art32 = report["requirements"]["article_32_security"]
        assert art32["status"] == "COMPLIANT"
        assert len(art32["controls"]) > 0

    def test_gdpr_article_30(self) -> None:
        report = ComplianceReport.generate_gdpr_compliance_report()
        art30 = report["requirements"]["article_30_records"]
        assert art30["status"] == "COMPLIANT"

    def test_gdpr_article_25(self) -> None:
        report = ComplianceReport.generate_gdpr_compliance_report()
        art25 = report["requirements"]["article_25_data_protection"]
        assert art25["status"] == "COMPLIANT"


class TestComplianceReportSecuritySummary:
    def test_generate_security_summary(self) -> None:
        report = ComplianceReport.generate_security_summary()
        assert report["security_posture"] == "STRONG"

    def test_security_summary_frameworks(self) -> None:
        report = ComplianceReport.generate_security_summary()
        assert "GDPR" in report["compliance_frameworks"]
        assert "LGPD" in report["compliance_frameworks"]

    def test_security_summary_layers(self) -> None:
        report = ComplianceReport.generate_security_summary()
        layers = report["security_layers"]
        assert layers["authentication"]["technology"] == "Keycloak (OIDC/SAML)"
        assert layers["authorization"]["model"] == "RACI-based RBAC"
        assert layers["secrets_management"]["status"] == "ACTIVE"

    def test_security_summary_metrics_all_true(self) -> None:
        report = ComplianceReport.generate_security_summary()
        metrics = report["security_metrics"]
        for key, value in metrics.items():
            assert value is True, f"{key} should be True"
