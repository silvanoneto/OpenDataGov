"""Tests for plugin system (ADR-131)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Generator

import pytest

from odg_core.governance.base_rule import BaseRule, RuleEvaluation
from odg_core.metadata.base_connector import BaseConnector, DatasetMetadata, MetadataExtract
from odg_core.plugins.registry import PluginRegistry
from odg_core.privacy.base_privacy import BasePrivacy, PrivacyConfig, PrivacyResult
from odg_core.quality.base_check import BaseCheck, CheckResult, DAMADimension, Severity
from odg_core.storage.base_storage import BaseStorage

# ──── Example Plugin Implementations ────────────────────────────


class DummyCheck(BaseCheck):
    """Dummy check for testing."""

    async def validate(self, data: Any) -> CheckResult:
        return CheckResult(passed=True, score=1.0)

    def get_dimension(self) -> DAMADimension:
        return DAMADimension.COMPLETENESS

    def get_severity(self) -> Severity:
        return Severity.INFO


class DummyRule(BaseRule):
    """Dummy rule for testing."""

    async def evaluate(self, context: dict[str, Any]) -> RuleEvaluation:
        return RuleEvaluation(matched=True, actions=["test_action"])

    def get_conditions(self) -> list[str]:
        return ["test_condition"]

    def get_actions(self) -> list[str]:
        return ["test_action"]


class DummyConnector(BaseConnector):
    """Dummy connector for testing."""

    async def extract(self) -> MetadataExtract:
        return MetadataExtract()

    async def transform(self, raw: MetadataExtract) -> list[DatasetMetadata]:
        return []

    async def load(self, metadata: list[DatasetMetadata]) -> None:
        pass

    def get_source_type(self) -> str:
        return "dummy"


class DummyPrivacy(BasePrivacy):
    """Dummy privacy mechanism for testing."""

    async def apply(self, data: Any, config: PrivacyConfig) -> PrivacyResult:
        return PrivacyResult(transformed_data=data, privacy_loss=0.0)

    async def audit(self) -> dict[str, Any]:
        return {}

    def get_mechanism_type(self) -> str:
        return "dummy"


class DummyStorage(BaseStorage):
    """Dummy storage backend for testing."""

    async def read(self, path: str) -> bytes:
        return b"test"

    async def write(self, path: str, data: bytes) -> None:
        pass

    async def list(self, prefix: str = "") -> list[str]:
        return []

    async def delete(self, path: str) -> None:
        pass

    def get_storage_type(self) -> str:
        return "dummy"


# ──── Tests ──────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def clear_registry() -> Generator[None]:
    """Clear registry before each test."""
    PluginRegistry.clear_all()
    yield
    PluginRegistry.clear_all()


def test_register_and_get_check() -> None:
    """Test registering and retrieving a quality check."""
    PluginRegistry.register_check("dummy", DummyCheck)

    check_class = PluginRegistry.get_check("dummy")
    assert check_class is DummyCheck

    # Verify we can instantiate it
    check = check_class()
    assert isinstance(check, BaseCheck)


def test_register_and_get_rule() -> None:
    """Test registering and retrieving a governance rule."""
    PluginRegistry.register_rule("dummy", DummyRule)

    rule_class = PluginRegistry.get_rule("dummy")
    assert rule_class is DummyRule

    rule = rule_class()
    assert isinstance(rule, BaseRule)


def test_register_and_get_connector() -> None:
    """Test registering and retrieving a catalog connector."""
    PluginRegistry.register_connector("dummy", DummyConnector)

    connector_class = PluginRegistry.get_connector("dummy")
    assert connector_class is DummyConnector

    connector = connector_class()
    assert isinstance(connector, BaseConnector)


def test_register_and_get_privacy() -> None:
    """Test registering and retrieving a privacy mechanism."""
    PluginRegistry.register_privacy("dummy", DummyPrivacy)

    privacy_class = PluginRegistry.get_privacy("dummy")
    assert privacy_class is DummyPrivacy

    privacy = privacy_class()
    assert isinstance(privacy, BasePrivacy)


def test_register_and_get_storage() -> None:
    """Test registering and retrieving a storage backend."""
    PluginRegistry.register_storage("dummy", DummyStorage)

    storage_class = PluginRegistry.get_storage("dummy")
    assert storage_class is DummyStorage

    storage = storage_class()
    assert isinstance(storage, BaseStorage)


def test_list_plugins() -> None:
    """Test listing all plugins of each type."""
    PluginRegistry.register_check("check1", DummyCheck)
    PluginRegistry.register_check("check2", DummyCheck)
    PluginRegistry.register_rule("rule1", DummyRule)

    checks = PluginRegistry.list_checks()
    assert len(checks) == 2
    assert "check1" in checks
    assert "check2" in checks

    rules = PluginRegistry.list_rules()
    assert len(rules) == 1
    assert "rule1" in rules


def test_get_nonexistent_plugin() -> None:
    """Test getting a non-existent plugin returns None."""
    assert PluginRegistry.get_check("nonexistent") is None
    assert PluginRegistry.get_rule("nonexistent") is None
    assert PluginRegistry.get_connector("nonexistent") is None


def test_get_stats() -> None:
    """Test getting registry statistics."""
    PluginRegistry.register_check("check1", DummyCheck)
    PluginRegistry.register_rule("rule1", DummyRule)
    PluginRegistry.register_connector("conn1", DummyConnector)

    stats = PluginRegistry.get_stats()
    assert stats["checks"] == 1
    assert stats["rules"] == 1
    assert stats["connectors"] == 1
    assert stats["total"] == 3


@pytest.mark.asyncio
async def test_dummy_check_works() -> None:
    """Test that dummy check can be executed."""
    check = DummyCheck()
    result = await check.validate(None)
    assert result.passed is True
    assert result.score == 1.0
    assert check.get_dimension() == DAMADimension.COMPLETENESS


@pytest.mark.asyncio
async def test_dummy_rule_works() -> None:
    """Test that dummy rule can be evaluated."""
    rule = DummyRule()
    result = await rule.evaluate({})
    assert result.matched is True
    assert "test_action" in result.actions
