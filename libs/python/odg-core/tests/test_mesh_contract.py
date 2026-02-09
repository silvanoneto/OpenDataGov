"""Tests for mesh contract module."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from odg_core.mesh.contract import (
    ContractManager,
    ContractStatus,
    DataContract,
    SLAViolation,
    get_contract_manager,
)


def _make_contract(**overrides: object) -> DataContract:
    """Create a test contract with sensible defaults."""
    defaults: dict[str, object] = {
        "contract_id": "contract_finance_sales",
        "provider_domain": "finance",
        "consumer_domain": "sales",
        "data_product_id": "finance.revenue",
        "sla_freshness_hours": 12,
        "sla_availability": 0.99,
        "sla_quality_score": 0.95,
        "schema_version": "1.0.0",
        "alert_email": "sales@test.com",
    }
    defaults.update(overrides)
    return DataContract(**defaults)


# ── DataContract model tests ────────────────────────────────────


class TestDataContract:
    def test_create_with_required_fields(self) -> None:
        c = _make_contract()
        assert c.contract_id == "contract_finance_sales"
        assert c.provider_domain == "finance"
        assert c.consumer_domain == "sales"
        assert c.status == ContractStatus.DRAFT

    def test_default_values(self) -> None:
        c = _make_contract()
        assert c.allow_additive_changes is True
        assert c.allow_breaking_changes is False
        assert c.breaking_change_notice_days == 30
        assert c.allowed_operations == ["read"]
        assert c.monthly_query_limit is None
        assert c.violations == []
        assert c.cost_per_query == 0.0

    def test_sla_availability_bounds(self) -> None:
        c = _make_contract(sla_availability=0.0)
        assert c.sla_availability == 0.0
        c = _make_contract(sla_availability=1.0)
        assert c.sla_availability == 1.0

    def test_sla_availability_out_of_bounds(self) -> None:
        with pytest.raises(ValidationError):
            _make_contract(sla_availability=1.5)

    def test_sla_quality_score_bounds(self) -> None:
        with pytest.raises(ValidationError):
            _make_contract(sla_quality_score=-0.1)

    def test_serialization_roundtrip(self) -> None:
        c = _make_contract()
        data = c.model_dump()
        c2 = DataContract(**data)
        assert c2.contract_id == c.contract_id
        assert c2.sla_availability == c.sla_availability

    def test_json_schema_extra(self) -> None:
        schema = DataContract.model_json_schema()
        assert "properties" in schema


# ── SLAViolation model tests ────────────────────────────────────


class TestSLAViolation:
    def test_create_violation(self) -> None:
        v = SLAViolation(
            metric="freshness",
            expected=12.0,
            actual=24.0,
            severity="high",
        )
        assert v.metric == "freshness"
        assert v.expected == 12.0
        assert v.actual == 24.0
        assert v.severity == "high"
        assert v.violated_at is not None


# ── ContractManager tests ───────────────────────────────────────


class TestContractManager:
    def setup_method(self) -> None:
        self.mgr = ContractManager()

    def test_create_contract(self) -> None:
        c = _make_contract()
        result = self.mgr.create_contract(c)
        assert result.status == ContractStatus.DRAFT
        assert result.contract_id in self.mgr.contracts

    def test_create_duplicate_raises(self) -> None:
        c = _make_contract()
        self.mgr.create_contract(c)
        with pytest.raises(ValueError, match="already exists"):
            self.mgr.create_contract(c)

    def test_activate_contract(self) -> None:
        c = _make_contract()
        self.mgr.create_contract(c)
        result = self.mgr.activate_contract("contract_finance_sales")
        assert result.status == ContractStatus.ACTIVE
        assert result.activated_at is not None

    def test_activate_not_found_raises(self) -> None:
        with pytest.raises(ValueError, match="not found"):
            self.mgr.activate_contract("nonexistent")

    def test_activate_already_active_raises(self) -> None:
        c = _make_contract()
        self.mgr.create_contract(c)
        self.mgr.activate_contract("contract_finance_sales")
        with pytest.raises(ValueError, match="already active"):
            self.mgr.activate_contract("contract_finance_sales")

    def test_record_violation_non_critical(self) -> None:
        c = _make_contract()
        self.mgr.create_contract(c)
        self.mgr.activate_contract("contract_finance_sales")
        result = self.mgr.record_violation("contract_finance_sales", "freshness", 12.0, 24.0, "high")
        assert len(result.violations) == 1
        assert result.status == ContractStatus.ACTIVE

    def test_record_violation_critical_changes_status(self) -> None:
        c = _make_contract()
        self.mgr.create_contract(c)
        self.mgr.activate_contract("contract_finance_sales")
        result = self.mgr.record_violation("contract_finance_sales", "availability", 0.99, 0.50, "critical")
        assert result.status == ContractStatus.VIOLATED

    def test_record_violation_not_found(self) -> None:
        with pytest.raises(ValueError, match="not found"):
            self.mgr.record_violation("nope", "freshness", 1.0, 2.0, "low")

    def test_terminate_contract(self) -> None:
        c = _make_contract()
        self.mgr.create_contract(c)
        result = self.mgr.terminate_contract("contract_finance_sales", "No longer needed")
        assert result.status == ContractStatus.TERMINATED
        assert result.termination_reason == "No longer needed"
        assert result.terminated_at is not None

    def test_terminate_not_found(self) -> None:
        with pytest.raises(ValueError, match="not found"):
            self.mgr.terminate_contract("nope", "reason")

    def test_get_contract(self) -> None:
        c = _make_contract()
        self.mgr.create_contract(c)
        assert self.mgr.get_contract("contract_finance_sales") is not None
        assert self.mgr.get_contract("nonexistent") is None

    def test_list_contracts_no_filter(self) -> None:
        self.mgr.create_contract(_make_contract(contract_id="c1"))
        self.mgr.create_contract(_make_contract(contract_id="c2"))
        assert len(self.mgr.list_contracts()) == 2

    def test_list_contracts_filter_provider(self) -> None:
        self.mgr.create_contract(_make_contract(contract_id="c1", provider_domain="finance"))
        self.mgr.create_contract(_make_contract(contract_id="c2", provider_domain="hr"))
        result = self.mgr.list_contracts(provider_domain="finance")
        assert len(result) == 1
        assert result[0].provider_domain == "finance"

    def test_list_contracts_filter_consumer(self) -> None:
        self.mgr.create_contract(_make_contract(contract_id="c1", consumer_domain="sales"))
        self.mgr.create_contract(_make_contract(contract_id="c2", consumer_domain="marketing"))
        result = self.mgr.list_contracts(consumer_domain="sales")
        assert len(result) == 1

    def test_list_contracts_filter_status(self) -> None:
        self.mgr.create_contract(_make_contract(contract_id="c1"))
        self.mgr.create_contract(_make_contract(contract_id="c2"))
        self.mgr.activate_contract("c1")
        result = self.mgr.list_contracts(status=ContractStatus.ACTIVE)
        assert len(result) == 1
        assert result[0].contract_id == "c1"

    def test_list_contracts_filter_data_product(self) -> None:
        self.mgr.create_contract(_make_contract(contract_id="c1", data_product_id="finance.revenue"))
        self.mgr.create_contract(_make_contract(contract_id="c2", data_product_id="hr.payroll"))
        result = self.mgr.list_contracts(data_product_id="hr.payroll")
        assert len(result) == 1


# ── ContractStatus enum tests ───────────────────────────────────


class TestContractStatus:
    def test_all_statuses(self) -> None:
        assert ContractStatus.DRAFT.value == "draft"
        assert ContractStatus.ACTIVE.value == "active"
        assert ContractStatus.VIOLATED.value == "violated"
        assert ContractStatus.SUSPENDED.value == "suspended"
        assert ContractStatus.TERMINATED.value == "terminated"


# ── Global singleton tests ──────────────────────────────────────


class TestGetContractManager:
    def test_returns_instance(self) -> None:
        mgr = get_contract_manager()
        assert isinstance(mgr, ContractManager)

    def test_returns_same_instance(self) -> None:
        mgr1 = get_contract_manager()
        mgr2 = get_contract_manager()
        assert mgr1 is mgr2
