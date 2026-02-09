"""GPU Manager SDK - Python client for GPU job submission."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class GPUType:
    """GPU types available in cluster."""

    A100_80GB = "A100_80GB"
    H100_80GB = "H100_80GB"
    L40S_48GB = "L40S_48GB"
    A10G_24GB = "A10G_24GB"
    T4_16GB = "T4_16GB"


class JobPriority:
    """Job priority levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class JobStatus:
    """Job status."""

    PENDING = "pending"
    QUEUED = "queued"
    PROVISIONING = "provisioning"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PREEMPTED = "preempted"
    CANCELLED = "cancelled"


class GPURequirements(BaseModel):
    """GPU requirements for a job."""

    gpu_type: str
    gpu_count: int
    gpu_memory_gb: int


class ContainerSpec(BaseModel):
    """Container specification."""

    image: str
    command: list[str] | None = None
    args: list[str] | None = None
    env: dict[str, str] | None = None


class ResourceRequests(BaseModel):
    """Resource requests."""

    cpu: str = "8"
    memory: str = "32Gi"
    ephemeral_storage: str = "100Gi"


class GPUJob(BaseModel):
    """GPU job response."""

    job_id: str
    job_name: str
    project_id: str
    priority: str
    status: str
    queue_position: int | None
    estimated_start_time: datetime | None
    estimated_cost_usd: float | None
    actual_cost_usd: float | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    error_message: str | None


class ClusterStats(BaseModel):
    """GPU cluster statistics."""

    total_gpus: int
    available_gpus: int
    in_use_gpus: int
    gpu_utilization_avg: float
    total_jobs: int
    running_jobs: int
    queued_jobs: int
    total_cost_today_usd: float
    spot_instance_percentage: float


class GPUManagerClient:
    """Client for GPU Manager Service.

    Example:
        ```python
        from odg_core.gpu import GPUManagerClient, GPUType, JobPriority

        client = GPUManagerClient(api_url="http://gpu-manager:8000")

        # Submit GPU job
        job = client.submit_job(
            job_name="finetune_llama_7b",
            project_id="ml-research",
            priority=JobPriority.HIGH,
            gpu_type=GPUType.A100_80GB,
            gpu_count=4,
            container_image="nvcr.io/nvidia/pytorch:24.01-py3",
            container_command=["python", "train.py"],
            budget_limit_usd=100.0
        )

        print(f"Job {job.job_id} submitted, queue position: {job.queue_position}")

        # Wait for job completion
        job = client.wait_for_completion(job.job_id, timeout_minutes=60)
        print(f"Job completed with status: {job.status}")
        ```
    """

    def __init__(
        self,
        api_url: str = "http://gpu-manager:8000",
        timeout: int = 300,
    ):
        """Initialize GPU Manager client.

        Args:
            api_url: GPU Manager API URL
            timeout: Request timeout in seconds
        """
        self.api_url = api_url.rstrip("/")
        self.client = httpx.AsyncClient(timeout=timeout)

    async def submit_job(
        self,
        job_name: str,
        project_id: str,
        gpu_type: str,
        gpu_count: int,
        container_image: str,
        priority: str = JobPriority.MEDIUM,
        gpu_memory_gb: int | None = None,
        container_command: list[str] | None = None,
        container_args: list[str] | None = None,
        container_env: dict[str, str] | None = None,
        cpu: str = "8",
        memory: str = "32Gi",
        budget_limit_usd: float | None = None,
        max_duration_hours: int = 24,
        preemptible: bool = True,
        checkpoint_s3_path: str | None = None,
    ) -> GPUJob:
        """Submit a GPU job.

        Args:
            job_name: Job name
            project_id: Project identifier
            gpu_type: GPU type (A100_80GB, H100_80GB, etc.)
            gpu_count: Number of GPUs (1-8)
            container_image: Docker image
            priority: Job priority (low, medium, high, critical)
            gpu_memory_gb: GPU memory per GPU in GB (default: auto-detect)
            container_command: Container command
            container_args: Container arguments
            container_env: Environment variables
            cpu: CPU request
            memory: Memory request
            budget_limit_usd: Budget limit in USD
            max_duration_hours: Maximum job duration in hours
            preemptible: Allow spot instances
            checkpoint_s3_path: S3 path for checkpoints

        Returns:
            GPU job response

        Example:
            ```python
            job = await client.submit_job(
                job_name="train_model",
                project_id="ml-research",
                gpu_type=GPUType.A100_80GB,
                gpu_count=4,
                container_image="pytorch:latest",
                container_command=["python", "train.py"],
                budget_limit_usd=50.0
            )
            ```
        """
        # Auto-detect GPU memory if not specified
        if gpu_memory_gb is None:
            gpu_memory_map = {
                GPUType.A100_80GB: 80,
                GPUType.H100_80GB: 80,
                GPUType.L40S_48GB: 48,
                GPUType.A10G_24GB: 24,
                GPUType.T4_16GB: 16,
            }
            gpu_memory_gb = gpu_memory_map.get(gpu_type, 80)

        request = {
            "job_name": job_name,
            "project_id": project_id,
            "priority": priority,
            "gpu_requirements": {
                "gpu_type": gpu_type,
                "gpu_count": gpu_count,
                "gpu_memory_gb": gpu_memory_gb,
            },
            "container": {
                "image": container_image,
                "command": container_command,
                "args": container_args,
                "env": container_env,
            },
            "resources": {"cpu": cpu, "memory": memory},
            "budget_limit_usd": budget_limit_usd,
            "max_duration_hours": max_duration_hours,
            "preemptible": preemptible,
            "checkpoint_s3_path": checkpoint_s3_path,
        }

        response = await self.client.post(f"{self.api_url}/api/v1/gpu/jobs", json=request)
        response.raise_for_status()

        data = response.json()
        logger.info(f"Submitted job {data['job_id']}, queue position: {data.get('queue_position')}")

        return GPUJob(**data)

    async def get_job(self, job_id: str) -> GPUJob:
        """Get job status.

        Args:
            job_id: Job identifier

        Returns:
            Job details
        """
        response = await self.client.get(f"{self.api_url}/api/v1/gpu/jobs/{job_id}")
        response.raise_for_status()
        return GPUJob(**response.json())

    async def list_jobs(
        self,
        project_id: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[GPUJob]:
        """List jobs with optional filters.

        Args:
            project_id: Filter by project
            status: Filter by status
            limit: Maximum number of jobs

        Returns:
            List of jobs
        """
        params: dict[str, str | int] = {"limit": limit}
        if project_id:
            params["project_id"] = project_id
        if status:
            params["status"] = status

        response = await self.client.get(f"{self.api_url}/api/v1/gpu/jobs", params=params)
        response.raise_for_status()

        return [GPUJob(**job) for job in response.json()]

    async def cancel_job(self, job_id: str) -> None:
        """Cancel a job.

        Args:
            job_id: Job identifier
        """
        response = await self.client.delete(f"{self.api_url}/api/v1/gpu/jobs/{job_id}")
        response.raise_for_status()
        logger.info(f"Cancelled job {job_id}")

    async def get_logs(self, job_id: str, tail_lines: int = 100) -> str:
        """Get job logs.

        Args:
            job_id: Job identifier
            tail_lines: Number of lines to retrieve

        Returns:
            Job logs
        """
        response = await self.client.get(
            f"{self.api_url}/api/v1/gpu/jobs/{job_id}/logs",
            params={"tail_lines": tail_lines},
        )
        response.raise_for_status()
        data = response.json()
        return str(data["logs"])

    async def wait_for_completion(
        self, job_id: str, timeout_minutes: int = 60, poll_interval_seconds: int = 10
    ) -> GPUJob:
        """Wait for job to complete.

        Args:
            job_id: Job identifier
            timeout_minutes: Maximum time to wait
            poll_interval_seconds: Polling interval

        Returns:
            Completed job

        Raises:
            TimeoutError: If job doesn't complete within timeout
        """
        import asyncio

        start_time = datetime.now(UTC)
        timeout = timedelta(minutes=timeout_minutes)

        while True:
            job = await self.get_job(job_id)

            if job.status in [
                JobStatus.COMPLETED,
                JobStatus.FAILED,
                JobStatus.CANCELLED,
            ]:
                logger.info(f"Job {job_id} finished with status {job.status}")
                return job

            if datetime.now(UTC) - start_time > timeout:
                raise TimeoutError(f"Job {job_id} did not complete within {timeout_minutes} minutes")

            logger.debug(f"Job {job_id} status: {job.status}, waiting...")
            await asyncio.sleep(poll_interval_seconds)

    async def get_cluster_stats(self) -> ClusterStats:
        """Get GPU cluster statistics.

        Returns:
            Cluster stats
        """
        response = await self.client.get(f"{self.api_url}/api/v1/gpu/cluster/stats")
        response.raise_for_status()
        return ClusterStats(**response.json())

    async def close(self) -> None:
        """Close HTTP client."""
        await self.client.aclose()

    async def __aenter__(self) -> GPUManagerClient:
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()


# Synchronous wrapper for convenience
class GPUManagerClientSync:
    """Synchronous wrapper for GPUManagerClient."""

    def __init__(self, api_url: str = "http://gpu-manager:8000"):
        """Initialize synchronous GPU Manager client.

        Args:
            api_url: GPU Manager API URL
        """
        self.async_client = GPUManagerClient(api_url)

    def submit_job(self, **kwargs: Any) -> GPUJob:
        """Submit a GPU job (synchronous)."""
        import asyncio

        return asyncio.run(self.async_client.submit_job(**kwargs))

    def get_job(self, job_id: str) -> GPUJob:
        """Get job status (synchronous)."""
        import asyncio

        return asyncio.run(self.async_client.get_job(job_id))

    def list_jobs(self, **kwargs: Any) -> list[GPUJob]:
        """List jobs (synchronous)."""
        import asyncio

        return asyncio.run(self.async_client.list_jobs(**kwargs))

    def cancel_job(self, job_id: str) -> None:
        """Cancel job (synchronous)."""
        import asyncio

        asyncio.run(self.async_client.cancel_job(job_id))

    def get_logs(self, job_id: str, tail_lines: int = 100) -> str:
        """Get logs (synchronous)."""
        import asyncio

        return asyncio.run(self.async_client.get_logs(job_id, tail_lines))

    def wait_for_completion(self, job_id: str, timeout_minutes: int = 60) -> GPUJob:
        """Wait for completion (synchronous)."""
        import asyncio

        return asyncio.run(self.async_client.wait_for_completion(job_id, timeout_minutes))

    def get_cluster_stats(self) -> ClusterStats:
        """Get cluster stats (synchronous)."""
        import asyncio

        return asyncio.run(self.async_client.get_cluster_stats())
