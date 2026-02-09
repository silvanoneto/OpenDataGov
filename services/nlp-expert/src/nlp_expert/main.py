"""NLP Expert Service - Main application."""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from nlp_expert.expert import NLPExpert

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Global expert instance
expert: NLPExpert | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Manage application lifecycle."""
    global expert

    logger.info("Starting NLP Expert Service...")

    # Initialize expert
    expert = NLPExpert(
        model_name="bert-base-uncased",
        device="cpu",  # Use "cuda" for GPU
    )

    logger.info("✓ NLP Expert initialized")

    yield

    logger.info("Shutting down NLP Expert Service...")


app = FastAPI(
    title="OpenDataGov NLP Expert",
    version="0.1.0",
    description="Natural language processing expert with BERT and PII detection",
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
        # Sentiment analysis
        curl -X POST http://nlp-expert:8006/api/v1/expert/process \\
          -H "Content-Type: application/json" \\
          -d '{
            "capability": "sentiment_analysis",
            "query": "I absolutely love this product! Best purchase ever!",
            "context": {}
          }'

        # Named entity recognition (NER)
        curl -X POST http://nlp-expert:8006/api/v1/expert/process \\
          -H "Content-Type: application/json" \\
          -d '{
            "capability": "named_entity_recognition",
            "query": "John Doe works at Acme Corp in New York. Contact: john@example.com",
            "context": {}
          }'

        # Text classification
        curl -X POST http://nlp-expert:8006/api/v1/expert/process \\
          -H "Content-Type: application/json" \\
          -d '{
            "capability": "text_classification",
            "query": "This is a technical support request about database issues",
            "context": {
              "labels": ["technical", "sales", "support", "billing"]
            }
          }'

        # Question answering
        curl -X POST http://nlp-expert:8006/api/v1/expert/process \\
          -H "Content-Type: application/json" \\
          -d '{
            "capability": "question_answering",
            "query": "What is the capital of France?",
            "context": {
              "passage": "France is a country in Europe. Paris is the capital and largest city."
            }
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
        "expert_name": "nlp-expert",
        "capabilities": [
            {
                "name": "text_classification",
                "description": "Classify text into predefined categories",
            },
            {
                "name": "named_entity_recognition",
                "description": "Extract named entities with PII detection (GDPR/LGPD)",
            },
            {
                "name": "sentiment_analysis",
                "description": "Analyze sentiment (positive/negative/neutral)",
            },
            {
                "name": "text_summarization",
                "description": "Summarize long documents",
            },
            {
                "name": "question_answering",
                "description": "Answer questions based on context",
            },
        ],
        "risk_level": "LIMITED",  # EU AI Act
        "requires_model_card": True,
        "model_backend": "BERT (bert-base-uncased)",
        "privacy_features": [
            "PII detection (email, phone, SSN, credit card, IP)",
            "GDPR/LGPD compliance checks",
            "Automatic approval requirement for PII-containing text",
        ],
    }
