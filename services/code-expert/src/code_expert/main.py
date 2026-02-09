"""Code Expert Service - Main application."""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from code_expert.expert import CodeExpert

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Global expert instance
expert: CodeExpert | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Manage application lifecycle."""
    global expert

    logger.info("Starting Code Expert Service...")

    # Initialize expert
    expert = CodeExpert(
        model_name="bigcode/starcoder",
        max_length=512,
        temperature=0.2,
    )

    logger.info("✓ Code Expert initialized")

    yield

    logger.info("Shutting down Code Expert Service...")


app = FastAPI(
    title="OpenDataGov Code Expert",
    version="0.1.0",
    description="Code generation and analysis expert with security scanning",
    lifespan=lifespan,
)


class ExpertRequest(BaseModel):
    """Expert request model."""

    capability: str
    query: str
    context: dict[str, Any] = {}


class ExpertResponse(BaseModel):
    """Expert response model."""

    recommendation: str
    confidence: float
    reasoning: str
    metadata: dict[str, Any]
    requires_approval: bool


@app.post("/api/v1/expert/process", response_model=ExpertResponse)
async def process_request(request: ExpertRequest) -> ExpertResponse:
    """Process expert request.

    Args:
        request: Expert request with capability and query

    Returns:
        Expert response with recommendation

    Example:
        ```bash
        # Generate code
        curl -X POST http://code-expert:8004/api/v1/expert/process \\
          -H "Content-Type: application/json" \\
          -d '{
            "capability": "code_generation",
            "query": "Write a function to validate email addresses",
            "context": {"language": "python"}
          }'

        # Review code
        curl -X POST http://code-expert:8004/api/v1/expert/process \\
          -H "Content-Type: application/json" \\
          -d '{
            "capability": "code_review",
            "query": "def unsafe_func(cmd): os.system(cmd)",
            "context": {"language": "python"}
          }'
        ```
    """
    if expert is None:
        raise HTTPException(status_code=503, detail="Expert not initialized")

    result = await expert.process(request.model_dump())

    return ExpertResponse(**result)


@app.get("/health")
async def health() -> dict:
    """Health check."""
    return {"status": "ok"}


@app.get("/capabilities")
async def get_capabilities() -> dict:
    """Get expert capabilities.

    Returns:
        List of supported capabilities
    """
    return {
        "expert_name": "code-expert",
        "capabilities": [
            {
                "name": "code_generation",
                "description": "Generate code from natural language descriptions",
            },
            {
                "name": "code_review",
                "description": "Review code for security and quality issues",
            },
            {
                "name": "refactoring",
                "description": "Suggest code refactoring improvements",
            },
            {
                "name": "bug_fix",
                "description": "Suggest fixes for identified bugs",
            },
        ],
        "risk_level": "LIMITED",  # EU AI Act
        "requires_model_card": True,
        "security_features": [
            "Syntax validation (AST/TreeSitter)",
            "Security scanning (pattern-based)",
            "Human-in-the-loop (approval required)",
        ],
    }
