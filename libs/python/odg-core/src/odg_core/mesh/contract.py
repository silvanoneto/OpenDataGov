"""Data Contract model for Data Mesh.

A Data Contract is an agreement between:
- Provider: Domain publishing a data product
- Consumer: Domain consuming the data product

Contract defines:
- SLA commitments (freshness, availability, quality)
- Schema guarantees (no breaking changes without notice)
- Access permissions
- Usage quotas
- Monitoring and alerts
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class ContractStatus(StrEnum):
    """Data contract status."""

    DRAFT = "draft"  # Being negotiated
    ACTIVE = "active"  # In effect
    VIOLATED = "violated"  # SLA violation detected
    SUSPENDED = "suspended"  # Temporarily suspended
    TERMINATED = "terminated"  # Contract ended


class SLAViolation(BaseModel):
    """SLA violation record."""

    violated_at: datetime = Field(default_factory=datetime.now)
    metric: str = Field(..., description="Violated metric (freshness, availability, etc.)")
    expected: float = Field(..., description="Expected value")
    actual: float = Field(..., description="Actual value")
    severity: str = Field(..., description="Violation severity (low/medium/high/critical)")


class DataContract(BaseModel):
    """Data contract between provider and consumer domains.

    Defines the agreement for data product consumption with:
    - SLA commitments
    - Schema stability guarantees
    - Access control
    - Usage quotas
    - Monitoring
    """

    contract_id: str = Field(..., description="Unique contract ID")

    # Parties
    provider_domain: str = Field(..., description="Provider domain ID")
    consumer_domain: str = Field(..., description="Consumer domain ID")
    data_product_id: str = Field(..., description="Data product being consumed")

    # SLA commitments
    sla_freshness_hours: int = Field(..., description="Max data age in hours")
    sla_availability: float = Field(..., ge=0.0, le=1.0, description="Min availability %")
    sla_quality_score: float = Field(..., ge=0.0, le=1.0, description="Min DQ score")
    sla_response_time_ms: int = Field(default=1000, description="Max query response time")

    # Schema guarantees
    schema_version: str = Field(..., description="Contracted schema version")
    allow_additive_changes: bool = Field(default=True, description="Allow new optional fields")
    allow_breaking_changes: bool = Field(default=False, description="Allow breaking changes (requires re-negotiation)")
    breaking_change_notice_days: int = Field(default=30, description="Notice period for breaking changes")

    # Access control
    allowed_operations: list[str] = Field(
        default_factory=lambda: ["read"], description="Allowed operations (read, write)"
    )
    row_level_filter: str | None = Field(None, description="SQL filter for row-level security")
    column_level_access: list[str] | None = Field(None, description="Allowed columns (None = all columns)")

    # Usage quotas
    monthly_query_limit: int | None = Field(None, description="Max queries per month (None = unlimited)")
    daily_row_limit: int | None = Field(None, description="Max rows per day (None = unlimited)")
    current_monthly_queries: int = Field(default=0, description="Current month query count")

    # Monitoring
    monitor_sla: bool = Field(default=True, description="Enable SLA monitoring")
    alert_email: str = Field(..., description="Email for SLA violation alerts")
    violations: list[SLAViolation] = Field(default_factory=list, description="SLA violation history")

    # Metadata
    status: ContractStatus = Field(default=ContractStatus.DRAFT)
    created_at: datetime = Field(default_factory=datetime.now)
    activated_at: datetime | None = None
    terminated_at: datetime | None = None
    termination_reason: str | None = None

    # Business terms
    cost_per_query: float = Field(default=0.0, description="Cost per query (FinOps)")
    billing_account: str | None = Field(None, description="Billing account ID")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "contract_id": "contract_finance_sales_revenue",
                "provider_domain": "finance",
                "consumer_domain": "sales",
                "data_product_id": "finance.revenue",
                "sla_freshness_hours": 12,
                "sla_availability": 0.99,
                "sla_quality_score": 0.95,
                "schema_version": "1.0.0",
                "allow_additive_changes": True,
                "allow_breaking_changes": False,
                "monthly_query_limit": 10000,
                "alert_email": "sales-data@company.com",
                "status": "active",
            }
        }
    )


class ContractManager:
    """Manager for data contracts."""

    def __init__(self) -> None:
        """Initialize contract manager."""
        self.contracts: dict[str, DataContract] = {}

    def create_contract(self, contract: DataContract) -> DataContract:
        """Create a new data contract.

        Args:
            contract: Contract to create

        Returns:
            Created contract

        Raises:
            ValueError: If contract already exists
        """
        if contract.contract_id in self.contracts:
            raise ValueError(f"Contract {contract.contract_id} already exists")

        contract.status = ContractStatus.DRAFT
        contract.created_at = datetime.now()
        self.contracts[contract.contract_id] = contract

        return contract

    def activate_contract(self, contract_id: str) -> DataContract:
        """Activate a contract (both parties agreed).

        Args:
            contract_id: Contract identifier

        Returns:
            Activated contract

        Raises:
            ValueError: If contract not found or already active
        """
        contract = self.contracts.get(contract_id)
        if not contract:
            raise ValueError(f"Contract {contract_id} not found")

        if contract.status == ContractStatus.ACTIVE:
            raise ValueError(f"Contract {contract_id} already active")

        contract.status = ContractStatus.ACTIVE
        contract.activated_at = datetime.now()

        return contract

    def record_violation(
        self,
        contract_id: str,
        metric: str,
        expected: float,
        actual: float,
        severity: str,
    ) -> DataContract:
        """Record an SLA violation.

        Args:
            contract_id: Contract identifier
            metric: Violated metric
            expected: Expected value
            actual: Actual value
            severity: Violation severity

        Returns:
            Updated contract

        Raises:
            ValueError: If contract not found
        """
        contract = self.contracts.get(contract_id)
        if not contract:
            raise ValueError(f"Contract {contract_id} not found")

        violation = SLAViolation(
            metric=metric,
            expected=expected,
            actual=actual,
            severity=severity,
        )

        contract.violations.append(violation)

        # Mark contract as violated if critical
        if severity == "critical":
            contract.status = ContractStatus.VIOLATED

        return contract

    def terminate_contract(self, contract_id: str, reason: str) -> DataContract:
        """Terminate a contract.

        Args:
            contract_id: Contract identifier
            reason: Termination reason

        Returns:
            Terminated contract

        Raises:
            ValueError: If contract not found
        """
        contract = self.contracts.get(contract_id)
        if not contract:
            raise ValueError(f"Contract {contract_id} not found")

        contract.status = ContractStatus.TERMINATED
        contract.terminated_at = datetime.now()
        contract.termination_reason = reason

        return contract

    def get_contract(self, contract_id: str) -> DataContract | None:
        """Get contract by ID.

        Args:
            contract_id: Contract identifier

        Returns:
            Contract or None
        """
        return self.contracts.get(contract_id)

    def list_contracts(
        self,
        provider_domain: str | None = None,
        consumer_domain: str | None = None,
        data_product_id: str | None = None,
        status: ContractStatus | None = None,
    ) -> list[DataContract]:
        """List contracts with filters.

        Args:
            provider_domain: Filter by provider domain
            consumer_domain: Filter by consumer domain
            data_product_id: Filter by data product
            status: Filter by status

        Returns:
            List of contracts
        """
        contracts = list(self.contracts.values())

        if provider_domain:
            contracts = [c for c in contracts if c.provider_domain == provider_domain]

        if consumer_domain:
            contracts = [c for c in contracts if c.consumer_domain == consumer_domain]

        if data_product_id:
            contracts = [c for c in contracts if c.data_product_id == data_product_id]

        if status:
            contracts = [c for c in contracts if c.status == status]

        return contracts


# Global contract manager instance
_manager: ContractManager | None = None


def get_contract_manager() -> ContractManager:
    """Get or create global contract manager.

    Returns:
        ContractManager instance
    """
    global _manager
    if _manager is None:
        _manager = ContractManager()
    return _manager
