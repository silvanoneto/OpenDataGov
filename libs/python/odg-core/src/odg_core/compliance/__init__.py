"""Pluggable compliance framework (ADR-110, ADR-111, ADR-112, ADR-113)."""

from odg_core.compliance.registry import ComplianceRegistry, create_default_registry

__all__ = ["ComplianceRegistry", "create_default_registry"]
