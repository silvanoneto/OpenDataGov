"""gRPC GovernanceService implementation."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import grpc
from google.protobuf.timestamp_pb2 import Timestamp
from odg_core.enums import DecisionStatus, DecisionType, RACIRole, VoteValue
from odg_core.proto_gen import governance_pb2, governance_pb2_grpc

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from odg_core.models import GovernanceDecision

    from governance_engine.domain.approval_service import ApprovalService
    from governance_engine.domain.decision_service import DecisionService
    from governance_engine.domain.veto_service import VetoService

logger = logging.getLogger(__name__)


def _decision_to_proto(decision: GovernanceDecision) -> governance_pb2.GovernanceDecision:
    """Convert domain model GovernanceDecision to protobuf."""
    created_at = Timestamp()
    created_at.FromDatetime(decision.created_at)

    updated_at = Timestamp()
    updated_at.FromDatetime(decision.updated_at)

    return governance_pb2.GovernanceDecision(
        id=str(decision.id),
        decision_type=_decision_type_to_proto(decision.decision_type),  # type: ignore[arg-type]
        title=decision.title,
        description=decision.description,
        status=_decision_status_to_proto(decision.status),  # type: ignore[arg-type]
        domain_id=decision.domain_id,
        created_by=decision.created_by,
        created_at=created_at,
        updated_at=updated_at,
        metadata=decision.metadata or {},
        source_layer=decision.promotion.source_layer if decision.promotion else "",
        target_layer=decision.promotion.target_layer if decision.promotion else "",
        data_classification=decision.promotion.data_classification.value
        if decision.promotion and decision.promotion.data_classification
        else "",
    )


def _decision_type_to_proto(decision_type: DecisionType) -> int:
    """Convert DecisionType enum to proto enum value."""
    mapping = {
        DecisionType.DATA_PROMOTION: governance_pb2.DECISION_TYPE_DATA_PROMOTION,
        DecisionType.SCHEMA_CHANGE: governance_pb2.DECISION_TYPE_SCHEMA_CHANGE,
        DecisionType.ACCESS_GRANT: governance_pb2.DECISION_TYPE_ACCESS_GRANT,
        DecisionType.EXPERT_REGISTRATION: governance_pb2.DECISION_TYPE_EXPERT_REGISTRATION,
        DecisionType.POLICY_CHANGE: governance_pb2.DECISION_TYPE_POLICY_CHANGE,
        DecisionType.EMERGENCY: governance_pb2.DECISION_TYPE_EMERGENCY,
    }
    return mapping.get(decision_type, governance_pb2.DECISION_TYPE_UNSPECIFIED)


def _decision_status_to_proto(status: DecisionStatus) -> int:
    """Convert DecisionStatus enum to proto enum value."""
    mapping = {
        DecisionStatus.PENDING: governance_pb2.DECISION_STATUS_PENDING,
        DecisionStatus.AWAITING_APPROVAL: governance_pb2.DECISION_STATUS_AWAITING_APPROVAL,
        DecisionStatus.APPROVED: governance_pb2.DECISION_STATUS_APPROVED,
        DecisionStatus.REJECTED: governance_pb2.DECISION_STATUS_REJECTED,
        DecisionStatus.VETOED: governance_pb2.DECISION_STATUS_VETOED,
        DecisionStatus.ESCALATED: governance_pb2.DECISION_STATUS_ESCALATED,
    }
    return mapping.get(status, governance_pb2.DECISION_STATUS_UNSPECIFIED)


def _proto_to_decision_type(proto_type: int) -> DecisionType:
    """Convert proto enum to DecisionType."""
    mapping: dict[int, DecisionType] = {
        governance_pb2.DECISION_TYPE_DATA_PROMOTION: DecisionType.DATA_PROMOTION,
        governance_pb2.DECISION_TYPE_SCHEMA_CHANGE: DecisionType.SCHEMA_CHANGE,
        governance_pb2.DECISION_TYPE_ACCESS_GRANT: DecisionType.ACCESS_GRANT,
        governance_pb2.DECISION_TYPE_EXPERT_REGISTRATION: DecisionType.EXPERT_REGISTRATION,
        governance_pb2.DECISION_TYPE_POLICY_CHANGE: DecisionType.POLICY_CHANGE,
        governance_pb2.DECISION_TYPE_EMERGENCY: DecisionType.EMERGENCY,
    }
    return mapping.get(proto_type, DecisionType.DATA_PROMOTION)


def _proto_to_decision_status(proto_status: int) -> DecisionStatus | None:
    """Convert proto enum to DecisionStatus."""
    mapping: dict[int, DecisionStatus] = {
        governance_pb2.DECISION_STATUS_PENDING: DecisionStatus.PENDING,
        governance_pb2.DECISION_STATUS_AWAITING_APPROVAL: DecisionStatus.AWAITING_APPROVAL,
        governance_pb2.DECISION_STATUS_APPROVED: DecisionStatus.APPROVED,
        governance_pb2.DECISION_STATUS_REJECTED: DecisionStatus.REJECTED,
        governance_pb2.DECISION_STATUS_VETOED: DecisionStatus.VETOED,
        governance_pb2.DECISION_STATUS_ESCALATED: DecisionStatus.ESCALATED,
    }
    return mapping.get(proto_status)


def _proto_to_vote_value(proto_vote: int) -> VoteValue:
    """Convert proto enum to VoteValue."""
    mapping: dict[int, VoteValue] = {
        governance_pb2.VOTE_VALUE_APPROVE: VoteValue.APPROVE,
        governance_pb2.VOTE_VALUE_REJECT: VoteValue.REJECT,
        governance_pb2.VOTE_VALUE_ABSTAIN: VoteValue.ABSTAIN,
    }
    return mapping.get(proto_vote, VoteValue.ABSTAIN)


def _proto_to_raci_role(proto_role: int) -> RACIRole:
    """Convert proto enum to RACIRole."""
    mapping: dict[int, RACIRole] = {
        governance_pb2.RACI_ROLE_RESPONSIBLE: RACIRole.RESPONSIBLE,
        governance_pb2.RACI_ROLE_ACCOUNTABLE: RACIRole.ACCOUNTABLE,
        governance_pb2.RACI_ROLE_CONSULTED: RACIRole.CONSULTED,
        governance_pb2.RACI_ROLE_INFORMED: RACIRole.INFORMED,
    }
    return mapping.get(proto_role, RACIRole.INFORMED)


class GovernanceServiceServicer(governance_pb2_grpc.GovernanceServiceServicer):
    """Implementation of GovernanceService gRPC service."""

    def __init__(
        self,
        decision_service: DecisionService,
        approval_service: ApprovalService,
        veto_service: VetoService,
    ) -> None:
        self.decision_service = decision_service
        self.approval_service = approval_service
        self.veto_service = veto_service

    async def CreateDecision(
        self,
        request: governance_pb2.CreateDecisionRequest,
        context: grpc.aio.ServicerContext[governance_pb2.CreateDecisionRequest, governance_pb2.GovernanceDecision],
    ) -> governance_pb2.GovernanceDecision:
        """Create a new governance decision."""
        try:
            decision_type = _proto_to_decision_type(request.decision_type)

            # Create decision using domain service
            decision = await self.decision_service.create_decision(
                decision_type=decision_type,
                title=request.title,
                description=request.description,
                domain_id=request.domain_id,
                created_by=request.created_by,
                promotion=None,  # TODO: Parse from request if needed
                metadata=dict(request.metadata) if request.metadata else None,
            )

            return _decision_to_proto(decision)

        except Exception as e:
            logger.exception("Error creating decision via gRPC")
            await context.abort(grpc.StatusCode.INTERNAL, f"Failed to create decision: {e}")
            raise  # unreachable; abort raises, but helps mypy

    async def GetDecision(
        self,
        request: governance_pb2.GetDecisionRequest,
        context: grpc.aio.ServicerContext[governance_pb2.GetDecisionRequest, governance_pb2.GovernanceDecision],
    ) -> governance_pb2.GovernanceDecision:
        """Get a decision by ID."""
        try:
            import uuid

            decision_id = uuid.UUID(request.id)
            decision = await self.decision_service.get_decision(decision_id)

            if decision is None:
                await context.abort(grpc.StatusCode.NOT_FOUND, f"Decision {request.id} not found")
                msg = "unreachable"
                raise AssertionError(msg)

            return _decision_to_proto(decision)

        except ValueError:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Invalid UUID format")
            raise  # unreachable; abort raises, but helps mypy
        except Exception as e:
            logger.exception("Error getting decision via gRPC")
            await context.abort(grpc.StatusCode.INTERNAL, f"Failed to get decision: {e}")
            raise  # unreachable; abort raises, but helps mypy

    async def ListDecisions(
        self,
        request: governance_pb2.ListDecisionsRequest,
        context: grpc.aio.ServicerContext[governance_pb2.ListDecisionsRequest, governance_pb2.ListDecisionsResponse],
    ) -> governance_pb2.ListDecisionsResponse:
        """List decisions with filters."""
        try:
            domain_id = request.domain_id if request.domain_id else None
            status = _proto_to_decision_status(request.status) if request.status else None
            limit = request.limit if request.limit > 0 else 50
            offset = request.offset if request.offset >= 0 else 0

            decisions = await self.decision_service.list_decisions(
                domain_id=domain_id,
                status=status,
                limit=limit,
                offset=offset,
            )

            proto_decisions = [_decision_to_proto(d) for d in decisions]

            return governance_pb2.ListDecisionsResponse(
                decisions=proto_decisions,
                total_count=len(proto_decisions),  # TODO: Get actual count from service
            )

        except Exception as e:
            logger.exception("Error listing decisions via gRPC")
            await context.abort(grpc.StatusCode.INTERNAL, f"Failed to list decisions: {e}")
            raise  # unreachable; abort raises, but helps mypy

    async def CastVote(
        self,
        request: governance_pb2.CastVoteRequest,
        context: grpc.aio.ServicerContext[governance_pb2.CastVoteRequest, governance_pb2.ApprovalRecord],
    ) -> governance_pb2.ApprovalRecord:
        """Cast a vote on a decision."""
        try:
            import uuid

            decision_id = uuid.UUID(request.decision_id)
            vote = _proto_to_vote_value(request.vote)

            approval = await self.approval_service.cast_vote(
                decision_id=decision_id,
                voter_id=request.voter_id,
                vote=vote,
                comment=request.comment,
            )

            # Convert approval to proto
            voted_at = Timestamp()
            voted_at.FromDatetime(approval.voted_at)

            return governance_pb2.ApprovalRecord(
                id=str(approval.id),
                decision_id=str(approval.decision_id),
                voter_id=approval.voter_id,
                voter_role=governance_pb2.RACI_ROLE_RESPONSIBLE,  # TODO: Map from approval.voter_role
                vote=request.vote,
                comment=approval.comment,
                voted_at=voted_at,
            )

        except ValueError:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Invalid UUID format")
            raise  # unreachable; abort raises, but helps mypy
        except Exception as e:
            logger.exception("Error casting vote via gRPC")
            await context.abort(grpc.StatusCode.INTERNAL, f"Failed to cast vote: {e}")
            raise  # unreachable; abort raises, but helps mypy

    async def ExerciseVeto(
        self,
        request: governance_pb2.ExerciseVetoRequest,
        context: grpc.aio.ServicerContext[governance_pb2.ExerciseVetoRequest, governance_pb2.VetoRecord],
    ) -> governance_pb2.VetoRecord:
        """Exercise a veto on a decision."""
        try:
            import uuid

            decision_id = uuid.UUID(request.decision_id)

            veto = await self.veto_service.exercise_veto(
                decision_id=decision_id,
                vetoed_by=request.vetoed_by,
                reason=request.reason,
            )

            # Convert veto to proto
            vetoed_at = Timestamp()
            vetoed_at.FromDatetime(veto.vetoed_at)

            return governance_pb2.VetoRecord(
                id=str(veto.id),
                decision_id=str(veto.decision_id),
                vetoed_by=veto.vetoed_by,
                vetoed_by_role=request.vetoed_by_role,
                reason=veto.reason,
                status=governance_pb2.VETO_STATUS_ACTIVE,
                vetoed_at=vetoed_at,
            )

        except ValueError:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Invalid UUID format")
            raise  # unreachable; abort raises, but helps mypy
        except Exception as e:
            logger.exception("Error exercising veto via gRPC")
            await context.abort(grpc.StatusCode.INTERNAL, f"Failed to exercise veto: {e}")
            raise  # unreachable; abort raises, but helps mypy

    async def SubmitDecision(
        self,
        request: governance_pb2.SubmitDecisionRequest,
        context: grpc.aio.ServicerContext[governance_pb2.SubmitDecisionRequest, governance_pb2.GovernanceDecision],
    ) -> governance_pb2.GovernanceDecision:
        """Submit a decision for approval workflow."""
        try:
            import uuid

            decision_id = uuid.UUID(request.decision_id)
            # NOTE: SubmitDecisionRequest in proto does not current have actor_id
            actor_id = "grpc-client"
            decision = await self.decision_service.submit_for_approval(decision_id, actor_id)

            return _decision_to_proto(decision)

        except ValueError:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Invalid UUID format")
            raise  # unreachable; abort raises, but helps mypy
        except Exception as e:
            logger.exception("Error submitting decision via gRPC")
            await context.abort(grpc.StatusCode.INTERNAL, f"Failed to submit decision: {e}")
            raise  # unreachable; abort raises, but helps mypy

    async def StreamDecisions(
        self,
        request: governance_pb2.StreamDecisionsRequest,
        context: grpc.aio.ServicerContext[governance_pb2.StreamDecisionsRequest, governance_pb2.GovernanceDecision],
    ) -> AsyncIterator[governance_pb2.GovernanceDecision]:
        """Stream decisions (server streaming)."""
        try:
            # TODO: Implement actual streaming logic
            # For now, just return a single list as a stream
            domain_id = request.domain_id if request.domain_id else None
            status = _proto_to_decision_status(request.status) if request.status else None

            decisions = await self.decision_service.list_decisions(
                domain_id=domain_id,
                status=status,
                limit=100,
            )

            for decision in decisions:
                yield _decision_to_proto(decision)

        except Exception as e:
            logger.exception("Error streaming decisions via gRPC")
            await context.abort(grpc.StatusCode.INTERNAL, f"Failed to stream decisions: {e}")
