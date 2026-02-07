"""Unit tests for the promotion logic with mocked MinIO."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from lakehouse_agent.promotion import PromotionError, PromotionService
from odg_core.enums import MedallionLayer

# ── Fixtures ─────────────────────────────────────────────


@pytest.fixture
def mock_bucket_manager() -> MagicMock:
    """Return a mock that satisfies the ``BucketManager`` protocol."""
    manager = MagicMock()
    manager.get_object = AsyncMock(return_value=b"dataset-bytes")
    manager.upload_object = AsyncMock(
        return_value={
            "bucket": "target",
            "key": "ds-1",
            "etag": "abc123",
            "version_id": None,
        }
    )
    return manager


@pytest.fixture
def promotion_service(mock_bucket_manager: MagicMock) -> PromotionService:
    return PromotionService(bucket_manager=mock_bucket_manager)


# ── Tests ────────────────────────────────────────────────


class TestBronzeToSilverAutoPromotion:
    async def test_auto_approved_when_dq_meets_threshold(
        self, promotion_service: PromotionService, mock_bucket_manager: MagicMock
    ) -> None:
        result = await promotion_service.promote(
            domain_id="finance",
            source_layer=MedallionLayer.BRONZE,
            target_layer=MedallionLayer.SILVER,
            dataset_id="ds-revenue-2024",
            dq_score=0.75,
        )

        assert result["promoted"] is True
        assert result["auto_approved"] is True
        assert result["governance_decision_id"] is None
        assert result["source_layer"] == "bronze"
        assert result["target_layer"] == "silver"

        # Verify that MinIO operations were called.
        mock_bucket_manager.get_object.assert_awaited_once_with("odg-bronze-finance", "ds-revenue-2024")
        mock_bucket_manager.upload_object.assert_awaited_once_with(
            "odg-silver-finance", "ds-revenue-2024", b"dataset-bytes"
        )

    async def test_auto_approved_at_exact_threshold(self, promotion_service: PromotionService) -> None:
        result = await promotion_service.promote(
            domain_id="hr",
            source_layer=MedallionLayer.BRONZE,
            target_layer=MedallionLayer.SILVER,
            dataset_id="ds-payroll",
            dq_score=0.7,
        )

        assert result["promoted"] is True
        assert result["auto_approved"] is True


class TestSilverToGoldRequiresGovernance:
    async def test_governance_decision_created(self, promotion_service: PromotionService) -> None:
        result = await promotion_service.promote(
            domain_id="finance",
            source_layer=MedallionLayer.SILVER,
            target_layer=MedallionLayer.GOLD,
            dataset_id="ds-revenue-2024",
            dq_score=0.90,
        )

        assert result["promoted"] is False
        assert result["auto_approved"] is False
        assert result["governance_decision_id"] is not None
        assert result["source_layer"] == "silver"
        assert result["target_layer"] == "gold"
        assert "Governance decision required" in result["reason"]


class TestGoldToPlatinumRequiresGovernance:
    async def test_governance_decision_created(self, promotion_service: PromotionService) -> None:
        result = await promotion_service.promote(
            domain_id="finance",
            source_layer=MedallionLayer.GOLD,
            target_layer=MedallionLayer.PLATINUM,
            dataset_id="ds-revenue-2024",
            dq_score=0.98,
        )

        assert result["promoted"] is False
        assert result["auto_approved"] is False
        assert result["governance_decision_id"] is not None
        assert result["source_layer"] == "gold"
        assert result["target_layer"] == "platinum"
        assert "Governance decision required" in result["reason"]


class TestInsufficientDQScore:
    async def test_bronze_to_silver_below_threshold(self, promotion_service: PromotionService) -> None:
        result = await promotion_service.promote(
            domain_id="finance",
            source_layer=MedallionLayer.BRONZE,
            target_layer=MedallionLayer.SILVER,
            dataset_id="ds-revenue-2024",
            dq_score=0.5,
        )

        assert result["promoted"] is False
        assert result["auto_approved"] is False
        assert result["governance_decision_id"] is None
        assert "below the required threshold" in result["reason"]

    async def test_silver_to_gold_below_threshold(self, promotion_service: PromotionService) -> None:
        result = await promotion_service.promote(
            domain_id="finance",
            source_layer=MedallionLayer.SILVER,
            target_layer=MedallionLayer.GOLD,
            dataset_id="ds-costs",
            dq_score=0.80,
        )

        assert result["promoted"] is False
        assert result["auto_approved"] is False
        assert result["governance_decision_id"] is None
        assert "below the required threshold" in result["reason"]

    async def test_gold_to_platinum_below_threshold(self, promotion_service: PromotionService) -> None:
        result = await promotion_service.promote(
            domain_id="finance",
            source_layer=MedallionLayer.GOLD,
            target_layer=MedallionLayer.PLATINUM,
            dataset_id="ds-kpis",
            dq_score=0.90,
        )

        assert result["promoted"] is False
        assert result["auto_approved"] is False
        assert result["governance_decision_id"] is None
        assert "below the required threshold" in result["reason"]


class TestInvalidTransition:
    async def test_skipping_layer_raises(self, promotion_service: PromotionService) -> None:
        with pytest.raises(PromotionError, match="exactly one layer"):
            await promotion_service.promote(
                domain_id="finance",
                source_layer=MedallionLayer.BRONZE,
                target_layer=MedallionLayer.GOLD,
                dataset_id="ds-1",
                dq_score=0.99,
            )

    async def test_backward_promotion_raises(self, promotion_service: PromotionService) -> None:
        with pytest.raises(PromotionError, match="exactly one layer"):
            await promotion_service.promote(
                domain_id="finance",
                source_layer=MedallionLayer.GOLD,
                target_layer=MedallionLayer.SILVER,
                dataset_id="ds-1",
                dq_score=0.99,
            )
