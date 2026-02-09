"""Base class for privacy mechanisms (ADR-131).

All privacy mechanisms must extend BasePrivacy and implement apply().
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field


class PrivacyConfig(BaseModel):
    """Configuration for privacy mechanism."""

    epsilon: float | None = Field(default=None, description="Privacy budget (for DP)")
    delta: float | None = Field(default=None, description="Privacy parameter (for DP)")
    k_anonymity: int | None = Field(default=None, description="k-anonymity parameter")
    parameters: dict[str, Any] = Field(default_factory=dict, description="Additional parameters")


class PrivacyResult(BaseModel):
    """Result of applying privacy mechanism."""

    transformed_data: Any = Field(description="Privacy-protected data")
    privacy_loss: float = Field(description="Privacy budget consumed (epsilon)")
    audit_metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Audit trail metadata",
    )
    statistics: dict[str, Any] = Field(
        default_factory=dict,
        description="Privacy statistics (noise added, records suppressed, etc.)",
    )


class BasePrivacy(ABC):
    """Abstract base class for privacy mechanisms.

    Implements the plugin pattern for extensible privacy protection.
    Supports differential privacy, k-anonymity, masking, etc.

    Example:
        class DifferentialPrivacyMechanism(BasePrivacy):
            async def apply(self, data: pd.DataFrame, config: PrivacyConfig) -> PrivacyResult:
                epsilon = config.epsilon or 1.0
                # Add Laplace noise to numerical columns
                noisy_data = data + np.random.laplace(0, 1/epsilon, data.shape)
                return PrivacyResult(
                    transformed_data=noisy_data,
                    privacy_loss=epsilon,
                    statistics={"noise_scale": 1/epsilon},
                )

            async def audit(self) -> dict[str, Any]:
                return {"total_epsilon_consumed": 5.2}

            def get_mechanism_type(self) -> str:
                return "differential_privacy"
    """

    @abstractmethod
    async def apply(self, data: Any, config: PrivacyConfig) -> PrivacyResult:
        """Apply privacy mechanism to data.

        Args:
            data: Original data to protect
            config: Privacy configuration

        Returns:
            PrivacyResult with transformed data and privacy loss

        Raises:
            Exception: If privacy application fails
        """
        ...

    @abstractmethod
    async def audit(self) -> dict[str, Any]:
        """Return audit information about privacy budget usage.

        Returns:
            Dictionary with privacy audit metadata
        """
        ...

    @abstractmethod
    def get_mechanism_type(self) -> str:
        """Return the privacy mechanism type (e.g., 'differential_privacy', 'k_anonymity')."""
        ...

    def get_name(self) -> str:
        """Return human-readable mechanism name (defaults to class name)."""
        return self.__class__.__name__

    def get_description(self) -> str:
        """Return mechanism description (defaults to docstring)."""
        return (self.__class__.__doc__ or "").strip()

    async def initialize(self) -> None:  # noqa: B027
        """Initialize privacy mechanism."""

    async def shutdown(self) -> None:  # noqa: B027
        """Gracefully shutdown mechanism."""
