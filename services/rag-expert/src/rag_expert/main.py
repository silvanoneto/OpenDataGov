"""RAG Expert Service - Main application."""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from rag_expert.expert import RAGExpert

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Global expert instance
expert: RAGExpert | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Manage application lifecycle."""
    global expert

    logger.info("Starting RAG Expert Service...")

    # Initialize expert
    expert = RAGExpert(
        qdrant_url="http://qdrant:6333",
        collection_name="governance_docs",
    )

    logger.info("✓ RAG Expert initialized")

    yield

    logger.info("Shutting down RAG Expert Service...")


app = FastAPI(
    title="OpenDataGov RAG Expert",
    version="0.1.0",
    description="Retrieval-Augmented Generation expert for governance Q&A",
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
        curl -X POST http://rag-expert:8002/api/v1/expert/process \\
          -H "Content-Type: application/json" \\
          -d '{
            "capability": "qa_generation",
            "query": "What is our data retention policy?",
            "context": {"domain": "privacy"}
          }'
        ```
    """
    if expert is None:
        raise HTTPException(status_code=503, detail="Expert not initialized")

    result = await expert.process(request.model_dump())

    return ExpertResponse(**result)


class DocumentIngestRequest(BaseModel):
    """Document ingestion request."""

    doc_id: str
    text: str
    metadata: dict[str, Any] = {}


@app.post("/api/v1/documents/ingest")
async def ingest_document(request: DocumentIngestRequest) -> dict:
    """Ingest document into vector store.

    Args:
        request: Document with ID, text, and metadata

    Returns:
        Status

    Example:
        ```bash
        curl -X POST http://rag-expert:8002/api/v1/documents/ingest \\
          -H "Content-Type: application/json" \\
          -d '{
            "doc_id": "policy-001",
            "text": "Our data retention policy states...",
            "metadata": {"category": "privacy", "version": "1.0"}
          }'
        ```
    """
    if expert is None:
        raise HTTPException(status_code=503, detail="Expert not initialized")

    expert.ingest_document(
        doc_id=request.doc_id,
        text=request.text,
        metadata=request.metadata,
    )

    return {"status": "success", "doc_id": request.doc_id}


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
        "expert_name": "rag-expert",
        "capabilities": [
            {
                "name": "document_search",
                "description": "Semantic search over governance documents",
            },
            {
                "name": "qa_generation",
                "description": "Answer questions using retrieved context",
            },
            {
                "name": "summarization",
                "description": "Summarize governance policies",
            },
            {
                "name": "compliance_check",
                "description": "Check compliance against regulations",
            },
        ],
        "risk_level": "LIMITED",  # EU AI Act
        "requires_model_card": True,
    }
