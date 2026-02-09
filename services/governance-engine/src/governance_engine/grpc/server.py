"""gRPC server for governance-engine (ADR-090)."""

from __future__ import annotations

import asyncio
import logging
import os
from typing import TYPE_CHECKING

import grpc
from odg_core.db.engine import create_async_engine_factory, get_async_session_factory
from odg_core.proto_gen import governance_pb2_grpc
from odg_core.settings import DatabaseSettings
from odg_core.telemetry import init_telemetry, shutdown_telemetry

from governance_engine.domain.approval_service import ApprovalService
from governance_engine.domain.audit_service import AuditService
from governance_engine.domain.decision_service import DecisionService
from governance_engine.domain.veto_service import VetoService
from governance_engine.grpc.governance_service import GovernanceServiceServicer
from governance_engine.repository.postgres import (
    PgApprovalRepository,
    PgAuditRepository,
    PgDecisionRepository,
    PgRACIRepository,
    PgVetoRepository,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

logger = logging.getLogger(__name__)

# gRPC server port (ADR-090 specifies 50051 for governance-engine)
GRPC_PORT = 50051


async def serve_grpc(port: int = GRPC_PORT, tls_enabled: bool = True) -> None:
    """Start gRPC server for governance-engine.

    Args:
        port: Port to bind the gRPC server (default: 50051)
        tls_enabled: Whether to enable TLS (default: True)
    """
    init_telemetry("governance-engine-grpc")

    # Initialize database
    db_settings = DatabaseSettings()
    engine: AsyncEngine = create_async_engine_factory(db_settings)
    session_factory = get_async_session_factory(engine)

    # Create repositories and services
    async with session_factory() as session:
        audit_repo = PgAuditRepository(session)
        audit_service = AuditService(repo=audit_repo)

        decision_repo = PgDecisionRepository(session)
        decision_service = DecisionService(repo=decision_repo, audit=audit_service)

        approval_repo = PgApprovalRepository(session)
        raci_repo = PgRACIRepository(session)
        approval_service = ApprovalService(
            repo=approval_repo,
            raci_repo=raci_repo,
            decision_service=decision_service,
            audit=audit_service,
        )

        veto_repo = PgVetoRepository(session)
        veto_service = VetoService(
            repo=veto_repo,
            raci_repo=raci_repo,
            decision_service=decision_service,
            audit=audit_service,
        )

        # Create gRPC server
        server = grpc.aio.server()

        # Add GovernanceService
        governance_servicer = GovernanceServiceServicer(
            decision_service=decision_service,
            approval_service=approval_service,
            veto_service=veto_service,
        )
        governance_pb2_grpc.add_GovernanceServiceServicer_to_server(governance_servicer, server)  # type: ignore[no-untyped-call]

        # Configure TLS if enabled
        if tls_enabled:
            tls_cert_path = os.getenv("GRPC_TLS_CERT", "/etc/grpc/tls/tls.crt")
            tls_key_path = os.getenv("GRPC_TLS_KEY", "/etc/grpc/tls/tls.key")

            if os.path.exists(tls_cert_path) and os.path.exists(tls_key_path):
                with open(tls_cert_path, "rb") as f:
                    cert_chain = f.read()
                with open(tls_key_path, "rb") as f:
                    private_key = f.read()

                server_credentials = grpc.ssl_server_credentials([(private_key, cert_chain)])
                server.add_secure_port(f"[::]:{port}", server_credentials)
                logger.info(f"Starting gRPC server with TLS on port {port}")
            else:
                logger.warning(
                    "TLS certs not found at %s and %s, falling back to insecure", tls_cert_path, tls_key_path
                )
                server.add_insecure_port(f"[::]:{port}")
                logger.info(f"Starting gRPC server (insecure) on port {port}")
        else:
            server.add_insecure_port(f"[::]:{port}")
            logger.info(f"Starting gRPC server (insecure) on port {port}")

        # Start server
        await server.start()

        try:
            await server.wait_for_termination()
        except KeyboardInterrupt:
            logger.info("Received shutdown signal")
        finally:
            logger.info("Stopping gRPC server")
            await server.stop(grace=5)
            await engine.dispose()
            shutdown_telemetry()


if __name__ == "__main__":
    asyncio.run(serve_grpc())
