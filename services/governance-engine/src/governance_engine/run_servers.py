"""Run both REST (FastAPI) and gRPC servers concurrently."""

from __future__ import annotations

import asyncio
import logging

import uvicorn

from governance_engine.grpc.server import serve_grpc
from governance_engine.main import app

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def run_fastapi_server() -> None:
    """Run FastAPI server."""
    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
    )
    server = uvicorn.Server(config)
    await server.serve()


async def run_both_servers() -> None:
    """Run both FastAPI and gRPC servers concurrently."""
    logger.info("Starting governance-engine with REST (8000) and gRPC (50051) servers")

    # Run both servers concurrently
    await asyncio.gather(
        run_fastapi_server(),
        serve_grpc(port=50051),
    )


if __name__ == "__main__":
    asyncio.run(run_both_servers())
