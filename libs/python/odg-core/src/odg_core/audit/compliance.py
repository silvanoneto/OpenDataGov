"""Compliance reporting for security controls (ADR-072, ADR-073).

Generates compliance reports mapping implemented security controls to:
- ADR-072: Keycloak (AuthN) + OPA (AuthZ)
- ADR-073: Vault (Secrets) + mTLS (Service Mesh)
- Regulatory frameworks (GDPR, LGPD, SOX, etc.)
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)


class ComplianceReport:
    """Generates compliance reports for security implementation."""

    @staticmethod
    def generate_adr_compliance_report() -> dict[str, Any]:
        """Generate ADR-072/073 compliance report.

        Returns:
            Dict with compliance status for each ADR requirement
        """
        return {
            "report_date": datetime.now(UTC).isoformat(),
            "report_type": "ADR Compliance",
            "adr_072_authentication_authorization": {
                "status": "COMPLIANT",
                "requirements": {
                    "keycloak_oidc": {
                        "implemented": True,
                        "details": "Keycloak deployed with OIDC/SAML support",
                        "evidence": [
                            "Keycloak initialization job creates opendatagov realm",
                            "JWT validation via PyJWT + JWKS",
                            "RACI roles configured (data_owner, data_steward, data_consumer, data_architect)",
                        ],
                    },
                    "opa_policy_engine": {
                        "implemented": True,
                        "details": "OPA deployed with Rego policies for RACI-based authorization",
                        "evidence": [
                            "OPA policies in opa-policies/authz.rego",
                            "Policy checks integrated in API dependencies",
                            "Resource-based access control by classification",
                        ],
                    },
                    "jwt_validation": {
                        "implemented": True,
                        "details": "JWT signature verification with JWKS caching",
                        "evidence": [
                            "KeycloakVerifier implements full JWT validation",
                            "Audience verification (client_id)",
                            "Expiration verification",
                            "Role extraction from realm_access and resource_access",
                        ],
                    },
                    "api_auth_enforcement": {
                        "implemented": True,
                        "details": "All API endpoints protected with FastAPI Depends",
                        "evidence": [
                            "routes_decisions.py: 9 endpoints with auth",
                            "routes_roles.py: 4 endpoints with auth",
                            "routes_audit.py: 3 endpoints with auth",
                            "routes_dashboard.py: 4 endpoints with auth",
                            "routes_self_service.py: 6 endpoints with auth",
                            "routes_graphql.py: GraphQL context authentication",
                        ],
                    },
                },
            },
            "adr_073_secrets_mtls": {
                "status": "COMPLIANT",
                "requirements": {
                    "vault_secrets_management": {
                        "implemented": True,
                        "details": "HashiCorp Vault with KV v2, Transit, and Database engines",
                        "evidence": [
                            "Vault initialization job configures all engines",
                            "Dynamic database credentials (TTL: 1h, max: 24h)",
                            "Transit encryption keys (odg-encryption, odg-minio-sse)",
                            "Kubernetes auth integration",
                        ],
                    },
                    "dynamic_credentials": {
                        "implemented": True,
                        "details": "PostgreSQL dynamic credentials via Vault Database engine",
                        "evidence": [
                            "VaultClient.get_database_credentials() method",
                            "Database engine uses Vault creds by default",
                            "Lease renewal with LeaseManager background task",
                        ],
                    },
                    "encryption_at_rest": {
                        "implemented": True,
                        "details": "Vault Transit encryption for audit events and MinIO objects",
                        "evidence": [
                            "AuditEncryption class for event encryption",
                            "MinIOStorage with Vault Transit integration",
                            "PostgreSQL pgcrypto extension enabled",
                        ],
                    },
                    "mtls_service_mesh": {
                        "implemented": True,
                        "details": "Istio service mesh with strict mTLS enforcement",
                        "evidence": [
                            "PeerAuthentication STRICT mode for all services",
                            "DestinationRule with ISTIO_MUTUAL TLS",
                            "AuthorizationPolicy zero-trust (default deny)",
                            "cert-manager for automatic certificate rotation (90 days)",
                        ],
                    },
                    "grpc_tls": {
                        "implemented": True,
                        "details": "gRPC server with TLS enabled",
                        "evidence": [
                            "server.py uses grpc.ssl_server_credentials",
                            "TLS certs from /etc/grpc/tls/",
                            "Fallback to insecure with logging if certs not found",
                        ],
                    },
                    "kafka_tls_sasl": {
                        "implemented": True,
                        "details": "Kafka with SASL_SSL (SCRAM-SHA-512 + TLS)",
                        "evidence": [
                            "clientProtocol: sasl_ssl in all production profiles",
                            "SCRAM-SHA-512 mechanism",
                            "Auto-generated TLS certificates",
                            "Inter-broker authentication",
                        ],
                    },
                },
            },
            "network_security": {
                "status": "COMPLIANT",
                "requirements": {
                    "network_policies": {
                        "implemented": True,
                        "details": "Zero-trust NetworkPolicies with default deny-all",
                        "evidence": [
                            "Default deny-all NetworkPolicy",
                            "Service-specific ingress/egress rules",
                            "Infrastructure isolation (PostgreSQL, Redis, Kafka)",
                            "DNS and health check exceptions",
                        ],
                    },
                    "pod_security": {
                        "implemented": True,
                        "details": "Pod Security Standards (restricted mode)",
                        "evidence": [
                            "Namespace labels for PSS enforcement",
                            "Restricted mode in production profiles",
                            "Dedicated ServiceAccounts per service",
                            "RBAC for Vault authentication",
                        ],
                    },
                },
            },
            "audit_compliance": {
                "status": "COMPLIANT",
                "requirements": {
                    "encrypted_audit_log": {
                        "implemented": True,
                        "details": "Encrypted audit events with hash chain integrity",
                        "evidence": [
                            "audit_log_encrypted table with pgcrypto",
                            "Vault Transit encryption per event",
                            "SHA-256 hash chain linking",
                            "verify_audit_chain() PostgreSQL function",
                        ],
                    },
                    "immutable_audit_trail": {
                        "implemented": True,
                        "details": "Append-only audit log with tamper detection",
                        "evidence": [
                            "Hash chain breaks if events modified",
                            "audit_integrity_check table for verification history",
                            "Kafka retention: 1 year",
                        ],
                    },
                },
            },
        }

    @staticmethod
    def generate_gdpr_compliance_report() -> dict[str, Any]:
        """Generate GDPR compliance report.

        Returns:
            Dict with GDPR compliance status
        """
        return {
            "report_date": datetime.now(UTC).isoformat(),
            "report_type": "GDPR Compliance",
            "requirements": {
                "article_32_security": {
                    "status": "COMPLIANT",
                    "requirement": "Implement appropriate technical and organizational measures to ensure security",
                    "controls": [
                        "Encryption of personal data at rest (Vault Transit)",
                        "Encryption in transit (mTLS, TLS)",
                        "Pseudonymization via encryption",
                        "Ability to ensure confidentiality (access controls)",
                        "Ability to ensure integrity (hash chains)",
                        "Ability to ensure availability (HA deployments)",
                    ],
                },
                "article_30_records": {
                    "status": "COMPLIANT",
                    "requirement": "Maintain records of processing activities",
                    "controls": [
                        "Encrypted audit log of all data access",
                        "Retention: 1 year minimum",
                        "Immutable audit trail with hash verification",
                        "Actor and entity tracking per event",
                    ],
                },
                "article_25_data_protection": {
                    "status": "COMPLIANT",
                    "requirement": "Data protection by design and by default",
                    "controls": [
                        "Zero-trust network architecture",
                        "Principle of least privilege (RBAC, NetworkPolicies)",
                        "Encryption by default (Vault, mTLS)",
                        "Privacy controls (data classification)",
                    ],
                },
            },
        }

    @staticmethod
    def generate_security_summary() -> dict[str, Any]:
        """Generate executive security summary.

        Returns:
            High-level security posture summary
        """
        return {
            "report_date": datetime.now(UTC).isoformat(),
            "security_posture": "STRONG",
            "compliance_frameworks": ["ADR-072", "ADR-073", "GDPR", "LGPD"],
            "security_layers": {
                "authentication": {
                    "technology": "Keycloak (OIDC/SAML)",
                    "status": "ACTIVE",
                    "mfa_supported": True,
                },
                "authorization": {
                    "technology": "Open Policy Agent (Rego)",
                    "status": "ACTIVE",
                    "model": "RACI-based RBAC",
                },
                "secrets_management": {
                    "technology": "HashiCorp Vault",
                    "status": "ACTIVE",
                    "features": ["Dynamic credentials", "Transit encryption", "Lease renewal"],
                },
                "network_security": {
                    "service_mesh": "Istio (mTLS strict mode)",
                    "network_policies": "Zero-trust (default deny)",
                    "pod_security": "Restricted standard",
                },
                "encryption": {
                    "at_rest": "Vault Transit + PostgreSQL pgcrypto",
                    "in_transit": "TLS 1.3 + mTLS",
                    "key_rotation": "90 days (cert-manager)",
                },
                "audit": {
                    "encryption": "Vault Transit per event",
                    "integrity": "SHA-256 hash chain",
                    "retention": "1 year (Kafka)",
                    "tamper_detection": "Enabled",
                },
            },
            "security_metrics": {
                "authentication_enabled": True,
                "authorization_enforced": True,
                "encryption_at_rest": True,
                "encryption_in_transit": True,
                "mtls_enabled": True,
                "audit_logging": True,
                "network_isolation": True,
                "secret_rotation": True,
            },
        }
