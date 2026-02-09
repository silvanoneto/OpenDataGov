"""Tests for mesh data product module."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from odg_core.mesh.data_product import (
    DataProduct,
    DataProductCatalog,
    DataProductSLA,
    DataProductSpec,
    DataProductStatus,
    DataProductTier,
    get_product_catalog,
)


def _make_sla(**overrides: object) -> DataProductSLA:
    defaults: dict[str, object] = {
        "freshness_hours": 12,
        "availability": 0.99,
        "completeness": 0.95,
        "accuracy": 0.95,
    }
    defaults.update(overrides)
    return DataProductSLA(**defaults)


def _make_product(**overrides: object) -> DataProduct:
    defaults: dict[str, object] = {
        "product_id": "finance.revenue",
        "name": "Revenue",
        "description": "Revenue data",
        "domain_id": "finance",
        "owner_email": "owner@test.com",
        "storage_location": "s3://bucket/finance/revenue",
        "data_schema": [{"name": "amount", "type": "float", "description": "Revenue"}],
        "current_dq_score": 0.97,
        "sla": _make_sla(),
    }
    defaults.update(overrides)
    return DataProduct(**defaults)


# ── DataProductSLA tests ────────────────────────────────────────


class TestDataProductSLA:
    def test_create_sla(self) -> None:
        sla = _make_sla()
        assert sla.freshness_hours == 12
        assert sla.availability == 0.99
        assert sla.response_time_ms == 1000

    def test_availability_bounds(self) -> None:
        with pytest.raises(ValidationError):
            _make_sla(availability=1.5)

    def test_completeness_bounds(self) -> None:
        with pytest.raises(ValidationError):
            _make_sla(completeness=-0.1)


# ── DataProductSpec tests ───────────────────────────────────────


class TestDataProductSpec:
    def test_create_spec(self) -> None:
        spec = DataProductSpec(
            product_id="finance.revenue",
            name="Revenue",
            description="Revenue data",
            domain_id="finance",
            data_schema=[{"name": "amount", "type": "float", "description": "Revenue"}],
            sla=_make_sla(),
        )
        assert spec.tier == DataProductTier.SILVER
        assert spec.public is False
        assert spec.allowed_consumers == []


# ── DataProduct model tests ─────────────────────────────────────


class TestDataProduct:
    def test_create_product(self) -> None:
        p = _make_product()
        assert p.product_id == "finance.revenue"
        assert p.status == DataProductStatus.PUBLISHED
        assert p.version == "1.0.0"

    def test_default_values(self) -> None:
        p = _make_product()
        assert p.tags == []
        assert p.lineage_upstream == []
        assert p.lineage_downstream == []
        assert p.total_consumers == 0
        assert p.monthly_queries == 0

    def test_dq_score_bounds(self) -> None:
        with pytest.raises(ValidationError):
            _make_product(current_dq_score=1.5)

    def test_serialization_roundtrip(self) -> None:
        p = _make_product()
        data = p.model_dump()
        p2 = DataProduct(**data)
        assert p2.product_id == p.product_id


# ── DataProductTier enum tests ──────────────────────────────────


class TestDataProductTier:
    def test_all_tiers(self) -> None:
        assert DataProductTier.BRONZE.value == "bronze"
        assert DataProductTier.SILVER.value == "silver"
        assert DataProductTier.GOLD.value == "gold"
        assert DataProductTier.PLATINUM.value == "platinum"


# ── DataProductStatus enum tests ────────────────────────────────


class TestDataProductStatus:
    def test_all_statuses(self) -> None:
        assert DataProductStatus.DRAFT.value == "draft"
        assert DataProductStatus.PUBLISHED.value == "published"
        assert DataProductStatus.DEPRECATED.value == "deprecated"
        assert DataProductStatus.RETIRED.value == "retired"


# ── DataProductCatalog tests ────────────────────────────────────


class TestDataProductCatalog:
    def setup_method(self) -> None:
        self.catalog = DataProductCatalog()

    def test_publish_product(self) -> None:
        p = _make_product()
        result = self.catalog.publish_product(p)
        assert result.status == DataProductStatus.PUBLISHED
        assert result.product_id in self.catalog.products

    def test_publish_duplicate_raises(self) -> None:
        p = _make_product()
        self.catalog.publish_product(p)
        with pytest.raises(ValueError, match="already exists"):
            self.catalog.publish_product(p)

    def test_get_product(self) -> None:
        p = _make_product()
        self.catalog.publish_product(p)
        assert self.catalog.get_product("finance.revenue") is not None
        assert self.catalog.get_product("nonexistent") is None

    def test_list_products_no_filter(self) -> None:
        self.catalog.publish_product(_make_product(product_id="p1"))
        self.catalog.publish_product(_make_product(product_id="p2"))
        assert len(self.catalog.list_products()) == 2

    def test_list_products_filter_domain(self) -> None:
        self.catalog.publish_product(_make_product(product_id="p1", domain_id="finance"))
        self.catalog.publish_product(_make_product(product_id="p2", domain_id="hr"))
        result = self.catalog.list_products(domain_id="finance")
        assert len(result) == 1

    def test_list_products_filter_tier(self) -> None:
        self.catalog.publish_product(_make_product(product_id="p1", tier=DataProductTier.GOLD))
        self.catalog.publish_product(_make_product(product_id="p2", tier=DataProductTier.SILVER))
        result = self.catalog.list_products(tier=DataProductTier.GOLD)
        assert len(result) == 1

    def test_list_products_filter_public(self) -> None:
        self.catalog.publish_product(_make_product(product_id="p1", public=True))
        self.catalog.publish_product(_make_product(product_id="p2", public=False))
        result = self.catalog.list_products(public=True)
        assert len(result) == 1

    def test_list_products_filter_tags(self) -> None:
        self.catalog.publish_product(_make_product(product_id="p1", tags=["gdpr", "pii"]))
        self.catalog.publish_product(_make_product(product_id="p2", tags=["gdpr"]))
        result = self.catalog.list_products(tags=["gdpr", "pii"])
        assert len(result) == 1

    def test_update_product(self) -> None:
        self.catalog.publish_product(_make_product())
        result = self.catalog.update_product("finance.revenue", {"version": "2.0.0"})
        assert result.version == "2.0.0"

    def test_update_product_not_found(self) -> None:
        with pytest.raises(ValueError, match="not found"):
            self.catalog.update_product("nope", {"version": "2.0.0"})

    def test_deprecate_product(self) -> None:
        self.catalog.publish_product(_make_product())
        result = self.catalog.deprecate_product("finance.revenue", "Replaced by v2")
        assert result.status == DataProductStatus.DEPRECATED

    def test_deprecate_not_found(self) -> None:
        with pytest.raises(ValueError, match="not found"):
            self.catalog.deprecate_product("nope", "reason")


# ── Global singleton tests ──────────────────────────────────────


class TestGetProductCatalog:
    def test_returns_instance(self) -> None:
        cat = get_product_catalog()
        assert isinstance(cat, DataProductCatalog)

    def test_returns_same_instance(self) -> None:
        cat1 = get_product_catalog()
        cat2 = get_product_catalog()
        assert cat1 is cat2
