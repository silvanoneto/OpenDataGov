"""Vision Expert Service - Main application."""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from vision_expert.expert import VisionExpert

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Global expert instance
expert: VisionExpert | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Manage application lifecycle."""
    global expert

    logger.info("Starting Vision Expert Service...")

    # Initialize expert
    expert = VisionExpert(
        model_name="openai/clip-vit-base-patch32",
        device="cpu",  # Use "cuda" for GPU
    )

    logger.info("✓ Vision Expert initialized")

    yield

    logger.info("Shutting down Vision Expert Service...")


app = FastAPI(
    title="OpenDataGov Vision Expert",
    version="0.1.0",
    description="Image analysis and understanding expert with CLIP",
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
        # Image classification
        curl -X POST http://vision-expert:8005/api/v1/expert/process \\
          -H "Content-Type: application/json" \\
          -d '{
            "capability": "image_classification",
            "query": "Classify this image",
            "context": {
              "image_url": "https://example.com/image.jpg",
              "labels": ["cat", "dog", "bird", "car"]
            }
          }'

        # Image-text similarity
        curl -X POST http://vision-expert:8005/api/v1/expert/process \\
          -H "Content-Type: application/json" \\
          -d '{
            "capability": "image_text_similarity",
            "query": "A sunny beach with palm trees",
            "context": {
              "image_url": "https://example.com/beach.jpg",
              "texts": [
                "A sunny beach with palm trees",
                "A snowy mountain landscape",
                "An urban city street"
              ]
            }
          }'

        # Visual QA
        curl -X POST http://vision-expert:8005/api/v1/expert/process \\
          -H "Content-Type: application/json" \\
          -d '{
            "capability": "visual_qa",
            "query": "What color is the car in the image?",
            "context": {
              "image_url": "https://example.com/car.jpg"
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
        "expert_name": "vision-expert",
        "capabilities": [
            {
                "name": "image_classification",
                "description": "Classify images into predefined categories",
            },
            {
                "name": "image_text_similarity",
                "description": "Match images to text descriptions using CLIP",
            },
            {
                "name": "visual_qa",
                "description": "Answer questions about image content",
            },
            {
                "name": "object_detection",
                "description": "Detect and locate objects in images",
            },
        ],
        "risk_level": "LIMITED",  # EU AI Act
        "requires_model_card": True,
        "model_backend": "OpenAI CLIP (ViT-B/32)",
        "supported_formats": ["JPEG", "PNG", "WebP", "BMP"],
    }
