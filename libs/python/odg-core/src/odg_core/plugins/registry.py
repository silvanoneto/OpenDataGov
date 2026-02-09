"""Plugin registry for OpenDataGov extensibility (ADR-131).

Centralizes registration and discovery of all plugin types:
- Quality Checks (BaseCheck)
- Governance Rules (BaseRule)
- Catalog Connectors (BaseConnector)
- Privacy Mechanisms (BasePrivacy)
- Storage Backends (BaseStorage)
- AI Experts (BaseExpert)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, ClassVar, TypeVar

if TYPE_CHECKING:
    from odg_core.expert import BaseExpert
    from odg_core.governance.base_rule import BaseRule
    from odg_core.metadata.base_connector import BaseConnector
    from odg_core.privacy.base_privacy import BasePrivacy
    from odg_core.quality.base_check import BaseCheck
    from odg_core.storage.base_storage import BaseStorage

logger = logging.getLogger(__name__)

T = TypeVar("T")


class PluginRegistry:
    """Global registry for all OpenDataGov plugins.

    Provides centralized plugin management with type safety.
    Supports auto-discovery and dynamic registration.

    Example:
        # Register a check
        PluginRegistry.register_check("completeness", CompletenessCheck)

        # Get a check
        check_class = PluginRegistry.get_check("completeness")
        check = check_class(threshold=0.95)

        # List all checks
        all_checks = PluginRegistry.list_checks()
    """

    # Plugin storage by type
    _checks: ClassVar[dict[str, type[BaseCheck]]] = {}
    _rules: ClassVar[dict[str, type[BaseRule]]] = {}
    _connectors: ClassVar[dict[str, type[BaseConnector]]] = {}
    _privacy: ClassVar[dict[str, type[BasePrivacy]]] = {}
    _storage: ClassVar[dict[str, type[BaseStorage]]] = {}
    _experts: ClassVar[dict[str, type[BaseExpert]]] = {}

    # ──── Quality Checks ────────────────────────────────────────

    @classmethod
    def register_check(cls, name: str, check_class: type[BaseCheck]) -> None:
        """Register a quality check plugin.

        Args:
            name: Unique check identifier
            check_class: BaseCheck subclass
        """
        if name in cls._checks:
            logger.warning("Overwriting existing check: %s", name)
        cls._checks[name] = check_class
        logger.info("Registered quality check: %s", name)

    @classmethod
    def get_check(cls, name: str) -> type[BaseCheck] | None:
        """Get a quality check by name."""
        return cls._checks.get(name)

    @classmethod
    def list_checks(cls) -> dict[str, type[BaseCheck]]:
        """List all registered quality checks."""
        return cls._checks.copy()

    # ──── Governance Rules ──────────────────────────────────────

    @classmethod
    def register_rule(cls, name: str, rule_class: type[BaseRule]) -> None:
        """Register a governance rule plugin."""
        if name in cls._rules:
            logger.warning("Overwriting existing rule: %s", name)
        cls._rules[name] = rule_class
        logger.info("Registered governance rule: %s", name)

    @classmethod
    def get_rule(cls, name: str) -> type[BaseRule] | None:
        """Get a governance rule by name."""
        return cls._rules.get(name)

    @classmethod
    def list_rules(cls) -> dict[str, type[BaseRule]]:
        """List all registered governance rules."""
        return cls._rules.copy()

    # ──── Catalog Connectors ────────────────────────────────────

    @classmethod
    def register_connector(cls, name: str, connector_class: type[BaseConnector]) -> None:
        """Register a catalog connector plugin."""
        if name in cls._connectors:
            logger.warning("Overwriting existing connector: %s", name)
        cls._connectors[name] = connector_class
        logger.info("Registered catalog connector: %s", name)

    @classmethod
    def get_connector(cls, name: str) -> type[BaseConnector] | None:
        """Get a catalog connector by name."""
        return cls._connectors.get(name)

    @classmethod
    def list_connectors(cls) -> dict[str, type[BaseConnector]]:
        """List all registered catalog connectors."""
        return cls._connectors.copy()

    # ──── Privacy Mechanisms ────────────────────────────────────

    @classmethod
    def register_privacy(cls, name: str, privacy_class: type[BasePrivacy]) -> None:
        """Register a privacy mechanism plugin."""
        if name in cls._privacy:
            logger.warning("Overwriting existing privacy mechanism: %s", name)
        cls._privacy[name] = privacy_class
        logger.info("Registered privacy mechanism: %s", name)

    @classmethod
    def get_privacy(cls, name: str) -> type[BasePrivacy] | None:
        """Get a privacy mechanism by name."""
        return cls._privacy.get(name)

    @classmethod
    def list_privacy(cls) -> dict[str, type[BasePrivacy]]:
        """List all registered privacy mechanisms."""
        return cls._privacy.copy()

    # ──── Storage Backends ──────────────────────────────────────

    @classmethod
    def register_storage(cls, name: str, storage_class: type[BaseStorage]) -> None:
        """Register a storage backend plugin."""
        if name in cls._storage:
            logger.warning("Overwriting existing storage backend: %s", name)
        cls._storage[name] = storage_class
        logger.info("Registered storage backend: %s", name)

    @classmethod
    def get_storage(cls, name: str) -> type[BaseStorage] | None:
        """Get a storage backend by name."""
        return cls._storage.get(name)

    @classmethod
    def list_storage(cls) -> dict[str, type[BaseStorage]]:
        """List all registered storage backends."""
        return cls._storage.copy()

    # ──── AI Experts ────────────────────────────────────────────

    @classmethod
    def register_expert(cls, name: str, expert_class: type[BaseExpert]) -> None:
        """Register an AI expert plugin."""
        if name in cls._experts:
            logger.warning("Overwriting existing expert: %s", name)
        cls._experts[name] = expert_class
        logger.info("Registered AI expert: %s", name)

    @classmethod
    def get_expert(cls, name: str) -> type[BaseExpert] | None:
        """Get an AI expert by name."""
        return cls._experts.get(name)

    @classmethod
    def list_experts(cls) -> dict[str, type[BaseExpert]]:
        """List all registered AI experts."""
        return cls._experts.copy()

    # ──── Utility Methods ───────────────────────────────────────

    @classmethod
    def clear_all(cls) -> None:
        """Clear all registered plugins (useful for testing)."""
        cls._checks.clear()
        cls._rules.clear()
        cls._connectors.clear()
        cls._privacy.clear()
        cls._storage.clear()
        cls._experts.clear()
        logger.info("Cleared all plugin registrations")

    @classmethod
    def get_stats(cls) -> dict[str, int]:
        """Get registration statistics."""
        return {
            "checks": len(cls._checks),
            "rules": len(cls._rules),
            "connectors": len(cls._connectors),
            "privacy": len(cls._privacy),
            "storage": len(cls._storage),
            "experts": len(cls._experts),
            "total": (
                len(cls._checks)
                + len(cls._rules)
                + len(cls._connectors)
                + len(cls._privacy)
                + len(cls._storage)
                + len(cls._experts)
            ),
        }
