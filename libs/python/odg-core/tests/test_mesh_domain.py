"""Tests for mesh domain module."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from odg_core.mesh.domain import (
    Domain,
    DomainRegistry,
    DomainStatus,
    get_domain_registry,
)


def _make_domain(**overrides: object) -> Domain:
    defaults: dict[str, object] = {
        "domain_id": "finance",
        "name": "Finance Domain",
        "description": "Financial data products",
        "owner_team": "finance-data-team",
        "owner_email": "finance@test.com",
    }
    defaults.update(overrides)
    return Domain(**defaults)


# ── Domain model tests ──────────────────────────────────────────


class TestDomain:
    def test_create_domain(self) -> None:
        d = _make_domain()
        assert d.domain_id == "finance"
        assert d.status == DomainStatus.ACTIVE

    def test_default_values(self) -> None:
        d = _make_domain()
        assert d.data_products == []
        assert d.min_dq_score == 0.90
        assert d.required_dimensions == ["completeness", "accuracy", "timeliness"]
        assert d.sla_freshness_hours == 24
        assert d.sla_availability == 0.99
        assert d.tags == []

    def test_serialization_roundtrip(self) -> None:
        d = _make_domain()
        data = d.model_dump()
        d2 = Domain(**data)
        assert d2.domain_id == d.domain_id

    def test_custom_dq_score(self) -> None:
        d = _make_domain(min_dq_score=0.99)
        assert d.min_dq_score == 0.99

    def test_dq_score_bounds(self) -> None:
        with pytest.raises(ValidationError):
            _make_domain(min_dq_score=1.5)


# ── DomainStatus enum tests ────────────────────────────────────


class TestDomainStatus:
    def test_all_statuses(self) -> None:
        assert DomainStatus.ACTIVE.value == "active"
        assert DomainStatus.INACTIVE.value == "inactive"
        assert DomainStatus.DEPRECATED.value == "deprecated"


# ── DomainRegistry tests ───────────────────────────────────────


class TestDomainRegistry:
    def setup_method(self) -> None:
        self.registry = DomainRegistry()

    def test_register_domain(self) -> None:
        d = _make_domain()
        result = self.registry.register_domain(d)
        assert result.domain_id == "finance"
        assert "finance" in self.registry.domains

    def test_register_duplicate_raises(self) -> None:
        d = _make_domain()
        self.registry.register_domain(d)
        with pytest.raises(ValueError, match="already exists"):
            self.registry.register_domain(d)

    def test_get_domain(self) -> None:
        self.registry.register_domain(_make_domain())
        assert self.registry.get_domain("finance") is not None
        assert self.registry.get_domain("nonexistent") is None

    def test_list_domains_no_filter(self) -> None:
        self.registry.register_domain(_make_domain(domain_id="finance"))
        self.registry.register_domain(_make_domain(domain_id="hr"))
        assert len(self.registry.list_domains()) == 2

    def test_list_domains_filter_status(self) -> None:
        d1 = _make_domain(domain_id="finance")
        d2 = _make_domain(domain_id="hr", status=DomainStatus.INACTIVE)
        self.registry.register_domain(d1)
        self.registry.register_domain(d2)
        result = self.registry.list_domains(status=DomainStatus.ACTIVE)
        assert len(result) == 1
        assert result[0].domain_id == "finance"

    def test_list_domains_filter_tags(self) -> None:
        self.registry.register_domain(_make_domain(domain_id="finance", tags=["gdpr", "sox"]))
        self.registry.register_domain(_make_domain(domain_id="hr", tags=["gdpr"]))
        result = self.registry.list_domains(tags=["gdpr", "sox"])
        assert len(result) == 1
        assert result[0].domain_id == "finance"

    def test_update_domain(self) -> None:
        self.registry.register_domain(_make_domain())
        result = self.registry.update_domain("finance", {"name": "Updated Finance"})
        assert result.name == "Updated Finance"

    def test_update_domain_not_found(self) -> None:
        with pytest.raises(ValueError, match="not found"):
            self.registry.update_domain("nope", {"name": "X"})

    def test_add_data_product(self) -> None:
        self.registry.register_domain(_make_domain())
        result = self.registry.add_data_product("finance", "finance.revenue")
        assert "finance.revenue" in result.data_products

    def test_add_data_product_idempotent(self) -> None:
        self.registry.register_domain(_make_domain())
        self.registry.add_data_product("finance", "finance.revenue")
        result = self.registry.add_data_product("finance", "finance.revenue")
        assert result.data_products.count("finance.revenue") == 1

    def test_add_data_product_not_found(self) -> None:
        with pytest.raises(ValueError, match="not found"):
            self.registry.add_data_product("nope", "p1")

    def test_remove_data_product(self) -> None:
        self.registry.register_domain(_make_domain())
        self.registry.add_data_product("finance", "finance.revenue")
        result = self.registry.remove_data_product("finance", "finance.revenue")
        assert "finance.revenue" not in result.data_products

    def test_remove_data_product_not_present(self) -> None:
        self.registry.register_domain(_make_domain())
        result = self.registry.remove_data_product("finance", "nonexistent")
        assert result.data_products == []

    def test_remove_data_product_domain_not_found(self) -> None:
        with pytest.raises(ValueError, match="not found"):
            self.registry.remove_data_product("nope", "p1")


# ── Global singleton tests ──────────────────────────────────────


class TestGetDomainRegistry:
    def test_returns_instance(self) -> None:
        reg = get_domain_registry()
        assert isinstance(reg, DomainRegistry)

    def test_returns_same_instance(self) -> None:
        reg1 = get_domain_registry()
        reg2 = get_domain_registry()
        assert reg1 is reg2
