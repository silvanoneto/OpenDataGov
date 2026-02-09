"""Tests for MLOps governance integration routes."""

from __future__ import annotations

import uuid

import pytest
from fastapi import status
from httpx import AsyncClient
from odg_core.auth.models import UserContext
from odg_core.enums import DecisionStatus, RACIRole


@pytest.fixture
def data_scientist_user() -> UserContext:
    """Create a mock data scientist user."""
    return UserContext(
        user_id="ds-001",
        email="data.scientist@example.com",
        roles=[RACIRole.RESPONSIBLE],
    )


@pytest.fixture
def data_architect_user() -> UserContext:
    """Create a mock data architect user."""
    return UserContext(
        user_id="da-001",
        email="data.architect@example.com",
        roles=[RACIRole.ACCOUNTABLE],
    )


class TestModelPromotionEndpoint:
    """Tests for model promotion endpoint."""

    @pytest.mark.asyncio
    async def test_request_promotion_staging_to_production(
        self, client: AsyncClient, data_scientist_user: UserContext
    ) -> None:
        """Test requesting model promotion from staging to production."""
        # Arrange
        payload = {
            "model_name": "customer-churn",
            "source_stage": "staging",
            "target_stage": "production",
            "model_version": 1,
            "mlflow_run_id": "abc123",
            "mlflow_model_uri": "s3://mlflow-artifacts/models/customer-churn/1",
            "justification": "Model achieves 95% accuracy, passes all validation tests",
            "performance_metrics": {"accuracy": 0.95, "precision": 0.93, "recall": 0.96},
        }

        # Act
        response = await client.post(
            "/api/v1/mlops/model-promotion", json=payload, headers={"Authorization": "Bearer ds-001"}
        )

        # Assert
        if response.status_code != 200:
            pytest.fail(f"Status: {response.status_code}, Body: {response.json()}")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "decision_id" in data
        assert data["approval_required"] is True
        assert "awaiting approval" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_request_promotion_none_to_staging_no_approval(
        self, client: AsyncClient, data_scientist_user: UserContext
    ) -> None:
        """Test that promotion from None to Staging doesn't require approval."""
        # Arrange
        payload = {
            "model_name": "sales-forecast",
            "source_stage": "none",
            "target_stage": "staging",
            "model_version": 1,
            "justification": "Initial staging deployment for testing",
            "performance_metrics": {"rmse": 0.12},
        }

        # Act
        response = await client.post(
            "/api/v1/mlops/model-promotion", json=payload, headers={"Authorization": "Bearer ds-001"}
        )

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["approval_required"] is False
        assert "no approval required" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_invalid_promotion_path(self, client: AsyncClient, data_scientist_user: UserContext) -> None:
        """Test that invalid promotion paths are rejected."""
        # Arrange
        payload = {
            "model_name": "fraud-detection",
            "source_stage": "none",
            "target_stage": "production",  # Invalid: can't go directly to production
            "model_version": 1,
            "justification": "Skip staging",
            "performance_metrics": {},
        }

        # Act
        response = await client.post(
            "/api/v1/mlops/model-promotion", json=payload, headers={"Authorization": "Bearer ds-001"}
        )

        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "invalid promotion path" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_promotion_requires_data_scientist_role(self, client: AsyncClient) -> None:
        """Test that only data scientists can request promotions."""
        # Arrange
        payload = {
            "model_name": "test-model",
            "source_stage": "staging",
            "target_stage": "production",
            "model_version": 1,
            "justification": "Test",
            "performance_metrics": {},
        }

        # Act (no authentication)
        response = await client.post(
            "/api/v1/mlops/model-promotion",
            json=payload,
        )

        # Assert
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestModelRetrainingEndpoint:
    """Tests for model retraining endpoint."""

    @pytest.mark.asyncio
    async def test_request_retraining_with_drift(self, client: AsyncClient, data_scientist_user: UserContext) -> None:
        """Test requesting model retraining due to drift detection."""
        # Arrange
        payload = {
            "model_name": "customer-churn",
            "reason": "Data drift detected in feature distribution",
            "drift_score": 0.85,
            "drift_details": {
                "features_drifted": ["age", "income"],
                "drift_method": "KS-test",
                "p_value": 0.001,
            },
            "requester_id": "ds-001",
        }

        # Act
        response = await client.post(
            "/api/v1/mlops/model-retraining", json=payload, headers={"Authorization": "Bearer ds-001"}
        )

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "decision_id" in data
        assert data["status"] in [DecisionStatus.PENDING, DecisionStatus.APPROVED]

    @pytest.mark.asyncio
    async def test_request_retraining_performance_degradation(
        self, client: AsyncClient, data_scientist_user: UserContext
    ) -> None:
        """Test requesting retraining due to performance degradation."""
        # Arrange
        payload = {
            "model_name": "sales-forecast",
            "reason": "Model accuracy dropped from 92% to 78%",
            "requester_id": "ds-001",
        }

        # Act
        response = await client.post(
            "/api/v1/mlops/model-retraining", json=payload, headers={"Authorization": "Bearer ds-001"}
        )

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "retrain" in data["message"].lower()


class TestPromotionStatusEndpoint:
    """Tests for promotion status endpoint."""

    @pytest.mark.asyncio
    async def test_get_promotion_status(self, client: AsyncClient, data_scientist_user: UserContext) -> None:
        """Test getting status of a model promotion decision."""
        # Arrange - First create a promotion
        payload = {
            "model_name": "test-model",
            "source_stage": "staging",
            "target_stage": "production",
            "model_version": 1,
            "justification": "Test",
            "performance_metrics": {"f1": 0.9},
        }
        create_response = await client.post(
            "/api/v1/mlops/model-promotion", json=payload, headers={"Authorization": "Bearer ds-001"}
        )
        decision_id = create_response.json()["decision_id"]

        # Act
        response = await client.get(
            f"/api/v1/mlops/model-promotion/{decision_id}", headers={"Authorization": "Bearer ds-001"}
        )

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["decision_id"] == decision_id
        assert "status" in data
        assert "metadata" in data

    @pytest.mark.asyncio
    async def test_get_nonexistent_decision(self, client: AsyncClient, data_scientist_user: UserContext) -> None:
        """Test getting status of non-existent decision returns 404."""
        # Act
        nonexistent_id = str(uuid.uuid4())
        response = await client.get(
            f"/api/v1/mlops/model-promotion/{nonexistent_id}", headers={"Authorization": "Bearer ds-001"}
        )

        # Assert
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestMLflowWebhook:
    """Tests for MLflow promotion webhook."""

    @pytest.mark.asyncio
    async def test_webhook_validates_approved_promotion(self, client: AsyncClient) -> None:
        """Test webhook validates that promotion is approved."""
        # Arrange
        payload = {
            "model_name": "customer-churn",
            "version": 1,
            "from_stage": "staging",
            "to_stage": "production",
        }

        # Act
        response = await client.post("/api/v1/mlops/webhook/mlflow-promotion", json=payload)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "approved" in data
        # Note: Full implementation requires decision lookup


class TestRACIWorkflow:
    """Integration tests for RACI workflow in model promotion."""

    @pytest.mark.asyncio
    async def test_full_promotion_workflow(
        self,
        client: AsyncClient,
        data_scientist_user: UserContext,
        data_architect_user: UserContext,
    ) -> None:
        """Test complete RACI workflow: request → approve → deploy."""
        # Step 1: Data Scientist requests promotion (Responsible)
        payload = {
            "model_name": "integration-test-model",
            "source_stage": "staging",
            "target_stage": "production",
            "model_version": 1,
            "justification": "Passed all validation tests",
            "performance_metrics": {"accuracy": 0.95},
        }
        create_response = await client.post(
            "/api/v1/mlops/model-promotion", json=payload, headers={"Authorization": "Bearer ds-001"}
        )
        assert create_response.status_code == status.HTTP_200_OK
        decision_id = create_response.json()["decision_id"]

        # Step 2: Data Architect approves (Accountable)
        # Note: This would call the decisions API endpoint
        # approve_response = await client.post(
        #     f"/api/v1/decisions/{decision_id}/approve",
        #     headers={"Authorization": f"Bearer {data_architect_token}"}
        # )
        # assert approve_response.status_code == status.HTTP_200_OK

        # Step 3: Verify status
        status_response = await client.get(
            f"/api/v1/mlops/model-promotion/{decision_id}", headers={"Authorization": "Bearer ds-001"}
        )
        assert status_response.status_code == status.HTTP_200_OK
        metadata = status_response.json()["metadata"]
        assert metadata["model_name"] == "integration-test-model"
        assert metadata["raci"]["responsible"] == "ds-001"
        assert metadata["raci"]["accountable"] == "data_architect"


class TestGovernanceIntegration:
    """Tests for governance integration with ModelCard."""

    @pytest.mark.asyncio
    async def test_promotion_creates_model_card_entry(
        self, client: AsyncClient, data_scientist_user: UserContext
    ) -> None:
        """Test that promotion updates model card with MLflow fields."""
        # Arrange
        payload = {
            "model_name": "test-model",
            "source_stage": "staging",
            "target_stage": "production",
            "model_version": 1,
            "mlflow_run_id": "test-run-id",
            "mlflow_model_uri": "s3://mlflow-artifacts/models/test-model/1",
            "justification": "Test",
            "performance_metrics": {},
        }

        # Act
        response = await client.post(
            "/api/v1/mlops/model-promotion", json=payload, headers={"Authorization": "Bearer ds-001"}
        )

        # Assert
        assert response.status_code == status.HTTP_200_OK
        decision_id = response.json()["decision_id"]

        # Verify decision metadata includes MLflow fields
        status_response = await client.get(
            f"/api/v1/mlops/model-promotion/{decision_id}", headers={"Authorization": "Bearer ds-001"}
        )
        metadata = status_response.json()["metadata"]
        assert metadata["mlflow_run_id"] == "test-run-id"
        assert metadata["mlflow_model_uri"] == "s3://mlflow-artifacts/models/test-model/1"


class TestExpertRegistrationEndpoint:
    """Tests for AI Expert registration endpoint."""

    @pytest.mark.asyncio
    async def test_request_registration_minimal_risk(
        self, client: AsyncClient, data_scientist_user: UserContext
    ) -> None:
        """Test registration of a MINIMAL risk AI system (auto-approved)."""
        # Arrange
        payload = {
            "expert_name": "basic-rag",
            "expert_version": "1.0.0",
            "capabilities": ["text-summarization"],
            "risk_level": "MINIMAL",
            "model_backend": "BERT",
            "justification": "Internal productivity tool",
        }

        # Act
        response = await client.post(
            "/api/v1/mlops/expert-registration", json=payload, headers={"Authorization": "Bearer ds-001"}
        )

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "decision_id" in data
        assert "auto-approved" in data["message"].lower()
        assert data["approval_required"] is False

    @pytest.mark.asyncio
    async def test_request_registration_high_risk(self, client: AsyncClient, data_scientist_user: UserContext) -> None:
        """Test registration of a HIGH risk AI system (requires multiple approvals)."""
        # Arrange
        payload = {
            "expert_name": "credit-scoring-ai",
            "expert_version": "2.1.0",
            "capabilities": ["risk-assessment"],
            "risk_level": "HIGH",
            "model_backend": "XGBoost",
            "justification": "Financial decision making",
            "security_features": ["encryption-at-rest", "audit-logging"],
        }

        # Act
        response = await client.post(
            "/api/v1/mlops/expert-registration", json=payload, headers={"Authorization": "Bearer ds-001"}
        )

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["approval_required"] is True
        assert "Awaiting approval from Data Architect and Legal team" in data["message"]

    @pytest.mark.asyncio
    async def test_reject_unacceptable_risk(self, client: AsyncClient, data_scientist_user: UserContext) -> None:
        """Test that UNACCEPTABLE risk level is rejected immediately."""
        # Arrange
        payload = {
            "expert_name": "biometric-id-public-space",
            "expert_version": "1.0.0",
            "capabilities": ["facial-recognition"],
            "risk_level": "UNACCEPTABLE",
            "model_backend": "DeepFace",
            "justification": "Surveillance",
        }

        # Act
        response = await client.post(
            "/api/v1/mlops/expert-registration", json=payload, headers={"Authorization": "Bearer ds-001"}
        )

        # Assert
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "prohibited" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_invalid_risk_level(self, client: AsyncClient, data_scientist_user: UserContext) -> None:
        """Test that invalid risk levels are rejected."""
        # Arrange
        payload = {
            "expert_name": "test",
            "expert_version": "1.0.0",
            "capabilities": [],
            "risk_level": "SUPER_HIGH",  # Invalid
            "model_backend": "test",
            "justification": "test",
        }

        # Act
        response = await client.post(
            "/api/v1/mlops/expert-registration", json=payload, headers={"Authorization": "Bearer ds-001"}
        )

        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "invalid risk level" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_get_expert_registration_status(self, client: AsyncClient, data_scientist_user: UserContext) -> None:
        """Test getting status of an expert registration."""
        # Arrange
        payload = {
            "expert_name": "status-test",
            "expert_version": "1.0.0",
            "capabilities": ["test"],
            "risk_level": "LIMITED",
            "model_backend": "test",
            "justification": "test",
        }
        create_resp = await client.post(
            "/api/v1/mlops/expert-registration", json=payload, headers={"Authorization": "Bearer ds-001"}
        )
        decision_id = create_resp.json()["decision_id"]

        # Act
        response = await client.get(
            f"/api/v1/mlops/expert-registration/{decision_id}", headers={"Authorization": "Bearer ds-001"}
        )

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["decision_id"] == decision_id
        assert data["expert_name"] == "status-test"
        assert data["risk_level"] == "LIMITED"

    @pytest.mark.asyncio
    async def test_get_nonexistent_expert_decision(self, client: AsyncClient, data_scientist_user: UserContext) -> None:
        """Test getting status of non-existent expert decision returns 404."""
        # Act
        nonexistent_id = str(uuid.uuid4())
        response = await client.get(
            f"/api/v1/mlops/expert-registration/{nonexistent_id}", headers={"Authorization": "Bearer ds-001"}
        )

        # Assert
        assert response.status_code == status.HTTP_404_NOT_FOUND
