"""GPU Manager Service - Main FastAPI application."""

from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import Depends, FastAPI, HTTPException
from gpu_manager.job_queue import JobQueueManager
from gpu_manager.kubernetes_orchestrator import KubernetesOrchestrator
from gpu_manager.models import (
    GPU_HOURLY_COST,
    ClusterStats,
    GPUJobRequest,
    GPUJobResponse,
    GPUJobRow,
    JobStatus,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Database setup
DATABASE_URL = "postgresql+asyncpg://postgres:postgres@postgres:5432/gpu_manager"
engine = create_async_engine(DATABASE_URL, echo=True)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncSession:
    """Get database session."""
    async with AsyncSessionLocal() as session:
        yield session


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    logger.info("Starting GPU Manager Service...")
    yield
    logger.info("Shutting down GPU Manager Service...")


app = FastAPI(
    title="GPU Manager Service",
    description="Auto-scaling GPU cluster management for ML workloads",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "gpu-manager"}


@app.post("/api/v1/gpu/jobs", response_model=GPUJobResponse)
async def create_job(request: GPUJobRequest, db: AsyncSession = Depends(get_db)) -> GPUJobResponse:
    """Submit a new GPU job.

    Args:
        request: Job request specification
        db: Database session

    Returns:
        Job response with job_id and status

    Example:
        ```python
        POST /api/v1/gpu/jobs
        {
          "job_name": "finetune_llama_7b",
          "project_id": "ml-research",
          "priority": "high",
          "gpu_requirements": {
            "gpu_type": "A100_80GB",
            "gpu_count": 4,
            "gpu_memory_gb": 80
          },
          "container": {
            "image": "nvcr.io/nvidia/pytorch:24.01-py3",
            "command": ["python", "train.py"]
          }
        }
        ```
    """
    job_id = f"gpu-job-{uuid.uuid4().hex[:8]}"

    # Estimate cost
    gpu_cost = GPU_HOURLY_COST.get(request.gpu_requirements.gpu_type, 0.0)
    estimated_cost = gpu_cost * request.gpu_requirements.gpu_count * request.max_duration_hours

    # Apply spot discount if preemptible
    if request.preemptible:
        estimated_cost *= 0.30  # 70% discount

    # Create job row
    job = GPUJobRow(
        job_id=job_id,
        job_name=request.job_name,
        project_id=request.project_id,
        user_id="anonymous",  # TODO: Get from auth
        priority=request.priority.value,
        status=JobStatus.PENDING.value,
        gpu_type=request.gpu_requirements.gpu_type.value,
        gpu_count=request.gpu_requirements.gpu_count,
        gpu_memory_gb=request.gpu_requirements.gpu_memory_gb,
        container_image=request.container.image,
        container_command=request.container.command,
        container_args=request.container.args,
        container_env=request.container.env,
        cpu_request=request.resources.cpu,
        memory_request=request.resources.memory,
        ephemeral_storage=request.resources.ephemeral_storage,
        budget_limit_usd=request.budget_limit_usd,
        max_duration_hours=request.max_duration_hours,
        preemptible=request.preemptible,
        checkpoint_s3_path=request.checkpoint_s3_path,
        estimated_cost_usd=estimated_cost,
        created_at=datetime.utcnow(),
    )

    db.add(job)
    await db.commit()
    await db.refresh(job)

    # Enqueue job
    queue_manager = JobQueueManager(db)
    queue_position = await queue_manager.enqueue_job(job_id, request.priority)

    # Estimate start time
    estimated_start = await queue_manager.estimate_start_time(job_id)

    logger.info(f"Created job {job_id} with priority {request.priority.value}, queue position {queue_position}")

    return GPUJobResponse(
        job_id=job.job_id,
        job_name=job.job_name,
        project_id=job.project_id,
        priority=request.priority,
        status=JobStatus.QUEUED,
        queue_position=queue_position,
        estimated_start_time=estimated_start,
        estimated_cost_usd=estimated_cost,
        actual_cost_usd=None,
        created_at=job.created_at,
        started_at=None,
        completed_at=None,
        error_message=None,
    )


@app.get("/api/v1/gpu/jobs/{job_id}", response_model=GPUJobResponse)
async def get_job(job_id: str, db: AsyncSession = Depends(get_db)) -> GPUJobResponse:
    """Get job status.

    Args:
        job_id: Job identifier
        db: Database session

    Returns:
        Job details

    Raises:
        HTTPException: If job not found
    """
    result = await db.execute(select(GPUJobRow).where(GPUJobRow.job_id == job_id))
    job = result.scalars().first()

    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    return GPUJobResponse(
        job_id=job.job_id,
        job_name=job.job_name,
        project_id=job.project_id,
        priority=job.priority,
        status=JobStatus(job.status),
        queue_position=job.queue_position,
        estimated_start_time=None,
        estimated_cost_usd=job.estimated_cost_usd,
        actual_cost_usd=job.actual_cost_usd,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        error_message=job.error_message,
    )


@app.get("/api/v1/gpu/jobs")
async def list_jobs(
    project_id: str | None = None,
    status: JobStatus | None = None,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
) -> list[GPUJobResponse]:
    """List GPU jobs with optional filters.

    Args:
        project_id: Filter by project
        status: Filter by status
        limit: Maximum number of jobs to return
        db: Database session

    Returns:
        List of jobs
    """
    query = select(GPUJobRow).order_by(GPUJobRow.created_at.desc()).limit(limit)

    if project_id:
        query = query.where(GPUJobRow.project_id == project_id)

    if status:
        query = query.where(GPUJobRow.status == status.value)

    result = await db.execute(query)
    jobs = result.scalars().all()

    return [
        GPUJobResponse(
            job_id=job.job_id,
            job_name=job.job_name,
            project_id=job.project_id,
            priority=job.priority,
            status=JobStatus(job.status),
            queue_position=job.queue_position,
            estimated_start_time=None,
            estimated_cost_usd=job.estimated_cost_usd,
            actual_cost_usd=job.actual_cost_usd,
            created_at=job.created_at,
            started_at=job.started_at,
            completed_at=job.completed_at,
            error_message=job.error_message,
        )
        for job in jobs
    ]


@app.delete("/api/v1/gpu/jobs/{job_id}")
async def cancel_job(job_id: str, db: AsyncSession = Depends(get_db)):
    """Cancel a job.

    Args:
        job_id: Job identifier
        db: Database session

    Returns:
        Success message

    Raises:
        HTTPException: If job cannot be cancelled
    """
    queue_manager = JobQueueManager(db)
    k8s = KubernetesOrchestrator()

    # Cancel in queue
    cancelled = await queue_manager.cancel_job(job_id)

    if not cancelled:
        raise HTTPException(status_code=400, detail=f"Cannot cancel job {job_id}")

    # Delete from Kubernetes if running
    await k8s.delete_job(job_id)

    logger.info(f"Cancelled job {job_id}")

    return {"message": f"Job {job_id} cancelled successfully"}


@app.get("/api/v1/gpu/cluster/stats", response_model=ClusterStats)
async def get_cluster_stats(db: AsyncSession = Depends(get_db)) -> ClusterStats:
    """Get GPU cluster statistics.

    Args:
        db: Database session

    Returns:
        Cluster statistics
    """
    k8s = KubernetesOrchestrator()

    # Get GPU capacity
    gpu_capacity = await k8s.get_node_gpu_capacity()
    total_gpus = sum(node["gpu_count"] for node in gpu_capacity.values())
    available_gpus = await k8s.get_available_gpus()

    # Get job stats
    queue_manager = JobQueueManager(db)
    job_stats = await queue_manager.get_queue_stats()

    # Calculate cost
    result = await db.execute(
        select(GPUJobRow).where(GPUJobRow.created_at >= datetime.utcnow().replace(hour=0, minute=0, second=0))
    )
    today_jobs = result.scalars().all()
    total_cost_today = sum(job.actual_cost_usd or 0 for job in today_jobs)

    # Spot instance percentage
    spot_nodes = sum(1 for node in gpu_capacity.values() if node["capacity_type"] == "spot")
    spot_percentage = (spot_nodes / len(gpu_capacity) * 100) if gpu_capacity else 0.0

    return ClusterStats(
        total_gpus=total_gpus,
        available_gpus=available_gpus,
        in_use_gpus=total_gpus - available_gpus,
        gpu_utilization_avg=0.0,  # TODO: Get from Prometheus
        total_jobs=job_stats["total_jobs"],
        running_jobs=job_stats["running"],
        queued_jobs=job_stats["queued"],
        total_cost_today_usd=total_cost_today,
        spot_instance_percentage=spot_percentage,
    )


@app.get("/api/v1/gpu/jobs/{job_id}/logs")
async def get_job_logs(job_id: str, tail_lines: int = 100) -> dict[str, str]:
    """Get job logs.

    Args:
        job_id: Job identifier
        tail_lines: Number of lines to retrieve

    Returns:
        Job logs

    Raises:
        HTTPException: If job not found
    """
    k8s = KubernetesOrchestrator()

    # Get pod name
    status = await k8s.get_job_status(job_id)
    pod_name = status.get("pod_name")

    if not pod_name:
        raise HTTPException(status_code=404, detail=f"Pod not found for job {job_id}")

    logs = await k8s.get_pod_logs(pod_name, tail_lines)

    return {"job_id": job_id, "pod_name": pod_name, "logs": logs}


@app.post("/api/v1/gpu/jobs/{job_id}/submit-to-k8s")
async def submit_job_to_k8s(job_id: str, db: AsyncSession = Depends(get_db)):
    """Submit queued job to Kubernetes.

    Args:
        job_id: Job identifier
        db: Database session

    Returns:
        Kubernetes job metadata

    Note:
        This is called by the scheduler worker, not by users directly.
    """
    result = await db.execute(select(GPUJobRow).where(GPUJobRow.job_id == job_id))
    job = result.scalars().first()

    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    if job.status != JobStatus.QUEUED.value:
        raise HTTPException(status_code=400, detail=f"Job {job_id} is not in queued status")

    k8s = KubernetesOrchestrator()
    metadata = await k8s.submit_job(job)

    logger.info(f"Submitted job {job_id} to Kubernetes: {metadata}")

    return metadata


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
