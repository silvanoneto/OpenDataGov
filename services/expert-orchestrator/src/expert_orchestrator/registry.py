"""Expert Registry - Manages available AI experts and their capabilities."""

from __future__ import annotations

import logging
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class ExpertCapability(StrEnum):
    """Capabilities that experts can provide."""

    SCHEMA_ANALYSIS = "schema_analysis"
    TYPE_INFERENCE = "type_inference"
    QUALITY_VALIDATION = "quality_validation"
    ANOMALY_DETECTION = "anomaly_detection"
    LINEAGE_TRACING = "lineage_tracing"
    IMPACT_ASSESSMENT = "impact_assessment"
    PERFORMANCE_TUNING = "performance_tuning"
    QUERY_OPTIMIZATION = "query_optimization"
    SECURITY_SCANNING = "security_scanning"
    PII_DETECTION = "pii_detection"
    COMPLIANCE_CHECKING = "compliance_checking"
    GDPR_VALIDATION = "gdpr_validation"
    COST_OPTIMIZATION = "cost_optimization"
    FINOPS_ANALYSIS = "finops_analysis"


class ExpertStatus(StrEnum):
    """Current status of an expert."""

    AVAILABLE = "available"
    BUSY = "busy"
    OFFLINE = "offline"
    MAINTENANCE = "maintenance"


class LLMBackend(StrEnum):
    """Supported LLM backends (February 2026 - Latest Models)."""

    # OpenAI (Latest: GPT-5 family)
    GPT5_2 = "gpt-5.2"  # Latest flagship - Instant & Thinking modes
    GPT5_1 = "gpt-5.1"  # Previous flagship
    GPT4O = "gpt-4o"  # Legacy
    O1 = "o1"  # Reasoning model (legacy)
    O1_MINI = "o1-mini"
    O1_PREVIEW = "o1-preview"

    # Anthropic (Latest: Claude 4 family)
    CLAUDE_4_OPUS_46 = "claude-opus-4.6"  # Latest flagship - Extended thinking, 200K-1M context
    CLAUDE_4_SONNET_46 = "claude-sonnet-4.6"  # Latest mid-tier
    CLAUDE_37_SONNET = "claude-3.7-sonnet"  # Legacy
    CLAUDE_36_SONNET = "claude-3.6-sonnet"  # Legacy
    CLAUDE_35_HAIKU = "claude-3.5-haiku"  # Legacy

    # Google (Latest: Gemini 3)
    GEMINI_3 = "gemini-3"  # Latest - Multimodal with video, spatial reasoning
    GEMINI_20_FLASH = "gemini-2.0-flash"  # Legacy
    GEMINI_20_PRO = "gemini-2.0-pro"  # Legacy

    # Meta (Latest: Llama 4)
    LLAMA_4_MAVERICK = "llama-4-maverick"  # Latest - Outperforms GPT-4o
    LLAMA_4_SCOUT = "llama-4-scout"  # Latest - Outperforms Gemini 2.0 Flash
    LLAMA_33 = "llama-3.3-70b"  # Legacy

    # Other Open Source
    DEEPSEEK_V3 = "deepseek-v3"


class ExpertRegistration(BaseModel):
    """Expert registration information."""

    expert_id: str = Field(..., description="Unique expert identifier")
    expert_name: str = Field(..., description="Human-readable expert name")
    expert_type: str = Field(..., description="Expert type (SchemaExpert, QualityExpert, etc.)")
    capabilities: list[ExpertCapability] = Field(..., description="Capabilities provided")
    llm_backend: LLMBackend = Field(..., description="LLM backend used")
    max_concurrent_tasks: int = Field(default=5, description="Max parallel tasks")
    average_latency_ms: int = Field(default=5000, description="Average response time")
    status: ExpertStatus = Field(default=ExpertStatus.AVAILABLE)
    endpoint: str = Field(..., description="Expert API endpoint")
    version: str = Field(default="1.0.0", description="Expert version")
    description: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    registered_at: datetime = Field(default_factory=datetime.utcnow)
    last_health_check: datetime | None = None


class ExpertMetrics(BaseModel):
    """Real-time metrics for an expert."""

    expert_id: str
    current_load: int  # Number of active tasks
    total_invocations: int
    successful_invocations: int
    failed_invocations: int
    average_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    last_invocation_at: datetime | None
    uptime_percentage: float


class ExpertRegistry:
    """Registry for managing AI experts."""

    def __init__(self, db: AsyncSession):
        """Initialize expert registry.

        Args:
            db: Database session
        """
        self.db = db
        self._experts: dict[str, ExpertRegistration] = {}
        self._metrics: dict[str, ExpertMetrics] = {}

    async def register_expert(self, registration: ExpertRegistration) -> bool:
        """Register a new expert.

        Args:
            registration: Expert registration data

        Returns:
            True if registration successful

        Example:
            >>> registry = ExpertRegistry(db)
            >>> await registry.register_expert(ExpertRegistration(
            ...     expert_id="schema_expert_1",
            ...     expert_name="Schema Analysis Expert",
            ...     expert_type="SchemaExpert",
            ...     capabilities=[ExpertCapability.SCHEMA_ANALYSIS],
            ...     llm_backend=LLMBackend.GPT4_TURBO,
            ...     endpoint="http://schema-expert:8000"
            ... ))
        """
        logger.info(f"Registering expert: {registration.expert_id}")

        # Store in memory cache
        self._experts[registration.expert_id] = registration

        # Initialize metrics
        self._metrics[registration.expert_id] = ExpertMetrics(
            expert_id=registration.expert_id,
            current_load=0,
            total_invocations=0,
            successful_invocations=0,
            failed_invocations=0,
            average_latency_ms=registration.average_latency_ms,
            p95_latency_ms=registration.average_latency_ms * 1.5,
            p99_latency_ms=registration.average_latency_ms * 2.0,
            last_invocation_at=None,
            uptime_percentage=100.0,
        )

        # Persist to database
        from expert_orchestrator.models import ExpertRegistrationRow

        expert_row = ExpertRegistrationRow(
            expert_id=registration.expert_id,
            expert_name=registration.expert_name,
            expert_type=registration.expert_type,
            capabilities=[cap.value for cap in registration.capabilities],
            llm_backend=registration.llm_backend.value,
            max_concurrent_tasks=registration.max_concurrent_tasks,
            average_latency_ms=registration.average_latency_ms,
            status=registration.status.value,
            endpoint=registration.endpoint,
            version=registration.version,
            description=registration.description,
            metadata=registration.metadata,
            registered_at=registration.registered_at,
        )

        self.db.add(expert_row)
        await self.db.commit()

        logger.info(f"✅ Expert registered: {registration.expert_id}")
        return True

    async def get_expert(self, expert_id: str) -> ExpertRegistration | None:
        """Get expert by ID.

        Args:
            expert_id: Expert identifier

        Returns:
            Expert registration or None if not found
        """
        return self._experts.get(expert_id)

    async def find_experts_by_capability(
        self, capability: ExpertCapability, status: ExpertStatus = ExpertStatus.AVAILABLE
    ) -> list[ExpertRegistration]:
        """Find experts that provide a specific capability.

        Args:
            capability: Required capability
            status: Filter by status (default: AVAILABLE)

        Returns:
            List of matching experts

        Example:
            >>> experts = await registry.find_experts_by_capability(
            ...     ExpertCapability.SCHEMA_ANALYSIS
            ... )
            >>> print(f"Found {len(experts)} schema experts")
        """
        return [
            expert for expert in self._experts.values() if capability in expert.capabilities and expert.status == status
        ]

    async def find_experts_by_type(self, expert_type: str) -> list[ExpertRegistration]:
        """Find experts by type.

        Args:
            expert_type: Expert type (e.g., "SchemaExpert")

        Returns:
            List of matching experts
        """
        return [expert for expert in self._experts.values() if expert.expert_type == expert_type]

    async def get_least_loaded_expert(self, capability: ExpertCapability) -> ExpertRegistration | None:
        """Get the least loaded expert for a capability.

        Args:
            capability: Required capability

        Returns:
            Expert with lowest current load, or None if none available

        Example:
            >>> expert = await registry.get_least_loaded_expert(
            ...     ExpertCapability.QUALITY_VALIDATION
            ... )
        """
        candidates = await self.find_experts_by_capability(capability)

        if not candidates:
            logger.warning(f"No experts found for capability: {capability}")
            return None

        # Sort by load ratio (current_load / max_concurrent_tasks)
        def load_ratio(expert: ExpertRegistration) -> float:
            metrics = self._metrics.get(expert.expert_id)
            if not metrics:
                return 0.0
            return metrics.current_load / expert.max_concurrent_tasks

        return min(candidates, key=load_ratio)

    async def update_expert_status(self, expert_id: str, status: ExpertStatus) -> bool:
        """Update expert status.

        Args:
            expert_id: Expert identifier
            status: New status

        Returns:
            True if updated successfully
        """
        expert = self._experts.get(expert_id)
        if not expert:
            logger.error(f"Expert not found: {expert_id}")
            return False

        expert.status = status
        expert.last_health_check = datetime.utcnow()

        logger.info(f"Updated expert {expert_id} status: {status.value}")
        return True

    async def increment_load(self, expert_id: str) -> None:
        """Increment expert's current load.

        Args:
            expert_id: Expert identifier
        """
        metrics = self._metrics.get(expert_id)
        if metrics:
            metrics.current_load += 1

    async def decrement_load(self, expert_id: str) -> None:
        """Decrement expert's current load.

        Args:
            expert_id: Expert identifier
        """
        metrics = self._metrics.get(expert_id)
        if metrics:
            metrics.current_load = max(0, metrics.current_load - 1)

    async def record_invocation(self, expert_id: str, latency_ms: int, success: bool) -> None:
        """Record expert invocation metrics.

        Args:
            expert_id: Expert identifier
            latency_ms: Response latency in milliseconds
            success: Whether invocation succeeded
        """
        metrics = self._metrics.get(expert_id)
        if not metrics:
            return

        metrics.total_invocations += 1
        if success:
            metrics.successful_invocations += 1
        else:
            metrics.failed_invocations += 1

        # Update rolling average latency
        n = metrics.total_invocations
        metrics.average_latency_ms = (metrics.average_latency_ms * (n - 1) + latency_ms) / n

        metrics.last_invocation_at = datetime.utcnow()

        # Update uptime percentage
        success_rate = metrics.successful_invocations / metrics.total_invocations
        metrics.uptime_percentage = success_rate * 100

    async def get_metrics(self, expert_id: str) -> ExpertMetrics | None:
        """Get expert metrics.

        Args:
            expert_id: Expert identifier

        Returns:
            Expert metrics or None
        """
        return self._metrics.get(expert_id)

    async def list_all_experts(self) -> list[ExpertRegistration]:
        """List all registered experts.

        Returns:
            List of all experts
        """
        return list(self._experts.values())

    async def health_check_all(self) -> dict[str, bool]:
        """Perform health check on all experts.

        Returns:
            Dict mapping expert_id to health status (True = healthy)
        """
        results = {}

        for expert_id, expert in self._experts.items():
            try:
                # TODO: Implement actual HTTP health check to expert.endpoint
                # For now, assume healthy if status is AVAILABLE
                is_healthy = expert.status == ExpertStatus.AVAILABLE
                results[expert_id] = is_healthy

                if is_healthy:
                    await self.update_expert_status(expert_id, ExpertStatus.AVAILABLE)
                else:
                    await self.update_expert_status(expert_id, ExpertStatus.OFFLINE)

            except Exception as e:
                logger.error(f"Health check failed for {expert_id}: {e}")
                results[expert_id] = False
                await self.update_expert_status(expert_id, ExpertStatus.OFFLINE)

        return results
