"""Database models for GPU Manager."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import JSON, BigInteger, Boolean, Column, DateTime, Float, Integer, String
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class JobStatus(StrEnum):
    """Job execution status."""

    PENDING = "pending"  # Aguardando recursos
    QUEUED = "queued"  # Na fila de execução
    PROVISIONING = "provisioning"  # Nodes sendo criados
    RUNNING = "running"  # Job executando
    COMPLETED = "completed"  # Sucesso
    FAILED = "failed"  # Falha
    PREEMPTED = "preempted"  # Spot instance preempted
    CANCELLED = "cancelled"  # Cancelado pelo usuário


class JobPriority(StrEnum):
    """Job priority levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class GPUType(StrEnum):
    """Supported GPU types."""

    A100_80GB = "A100_80GB"  # NVIDIA A100 80GB (p4d.24xlarge)
    H100_80GB = "H100_80GB"  # NVIDIA H100 80GB (p5.48xlarge)
    L40S_48GB = "L40S_48GB"  # NVIDIA L40S 48GB (g6.48xlarge)
    A10G_24GB = "A10G_24GB"  # NVIDIA A10G 24GB (g5.xlarge)
    T4_16GB = "T4_16GB"  # NVIDIA T4 16GB (g4dn.xlarge)


# GPU Hourly Costs (USD) - AWS us-east-1, Feb 2026
GPU_HOURLY_COST = {
    GPUType.A100_80GB: 4.10,
    GPUType.H100_80GB: 5.50,
    GPUType.L40S_48GB: 2.20,
    GPUType.A10G_24GB: 1.10,
    GPUType.T4_16GB: 0.526,
}

SPOT_DISCOUNT = 0.70  # 70% cheaper than on-demand


class GPUJobRow(Base):
    """GPU Job database table."""

    __tablename__ = "gpu_jobs"

    # Identity
    job_id = Column(String, primary_key=True)  # e.g., "gpu-job-abc123"
    job_name = Column(String, nullable=False)
    project_id = Column(String, nullable=False, index=True)
    user_id = Column(String, nullable=False)

    # Scheduling
    priority = Column(String, nullable=False, default=JobPriority.MEDIUM.value)
    status = Column(String, nullable=False, default=JobStatus.PENDING.value, index=True)
    queue_position = Column(Integer, nullable=True)

    # GPU Requirements
    gpu_type = Column(String, nullable=False)  # A100_80GB, H100_80GB, etc.
    gpu_count = Column(Integer, nullable=False)
    gpu_memory_gb = Column(Integer, nullable=False)

    # Container Spec
    container_image = Column(String, nullable=False)
    container_command = Column(JSON, nullable=True)  # ["python", "train.py"]
    container_args = Column(JSON, nullable=True)  # ["--epochs", "100"]
    container_env = Column(JSON, nullable=True)  # {"CUDA_VISIBLE_DEVICES": "0,1"}

    # Resources
    cpu_request = Column(String, nullable=False, default="8")
    memory_request = Column(String, nullable=False, default="32Gi")
    ephemeral_storage = Column(String, nullable=True, default="100Gi")

    # Budget & Limits
    budget_limit_usd = Column(Float, nullable=True)
    max_duration_hours = Column(Integer, nullable=True, default=24)
    preemptible = Column(Boolean, nullable=False, default=True)

    # Execution Metadata
    kubernetes_namespace = Column(String, nullable=True)
    kubernetes_job_name = Column(String, nullable=True)
    node_name = Column(String, nullable=True)
    pod_name = Column(String, nullable=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC))
    queued_at = Column(DateTime, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Cost Tracking
    actual_cost_usd = Column(Float, nullable=True, default=0.0)
    estimated_cost_usd = Column(Float, nullable=True)

    # Error Handling
    error_message = Column(String, nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)
    max_retries = Column(Integer, nullable=False, default=3)

    # Checkpointing
    checkpoint_s3_path = Column(String, nullable=True)
    last_checkpoint_at = Column(DateTime, nullable=True)


class GPUNodeRow(Base):
    """GPU Node tracking table."""

    __tablename__ = "gpu_nodes"

    # Identity
    node_name = Column(String, primary_key=True)
    instance_type = Column(String, nullable=False)  # p4d.24xlarge, p5.48xlarge
    gpu_type = Column(String, nullable=False)
    gpu_count = Column(Integer, nullable=False)

    # Status
    status = Column(String, nullable=False, default="pending")  # pending, ready, terminating
    capacity_type = Column(String, nullable=False)  # spot, on-demand
    availability_zone = Column(String, nullable=False)

    # Cost
    hourly_cost_usd = Column(Float, nullable=False)
    total_cost_usd = Column(Float, nullable=False, default=0.0)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC))
    ready_at = Column(DateTime, nullable=True)
    terminated_at = Column(DateTime, nullable=True)

    # Utilization
    gpu_utilization_avg = Column(Float, nullable=True)  # 0-100%
    gpu_memory_used_gb = Column(Float, nullable=True)


class GPUMetricsRow(Base):
    """GPU Metrics snapshots."""

    __tablename__ = "gpu_metrics"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC), index=True)

    # GPU Identity
    node_name = Column(String, nullable=False, index=True)
    gpu_id = Column(Integer, nullable=False)  # 0-7 for 8-GPU nodes
    gpu_type = Column(String, nullable=False)

    # Metrics
    gpu_utilization = Column(Float, nullable=False)  # 0-100%
    gpu_memory_used_mb = Column(Float, nullable=False)
    gpu_memory_total_mb = Column(Float, nullable=False)
    gpu_temperature_c = Column(Float, nullable=False)
    gpu_power_usage_w = Column(Float, nullable=False)
    gpu_sm_clock_mhz = Column(Integer, nullable=False)
    gpu_mem_clock_mhz = Column(Integer, nullable=False)

    # Job Association
    job_id = Column(String, nullable=True, index=True)
    pod_name = Column(String, nullable=True)


# Pydantic Models for API


class GPURequirements(BaseModel):
    """GPU requirements for a job."""

    gpu_type: GPUType
    gpu_count: int = Field(ge=1, le=8, description="Number of GPUs (1-8)")
    gpu_memory_gb: int = Field(ge=10, description="GPU memory per GPU in GB")


class ContainerSpec(BaseModel):
    """Container specification."""

    image: str
    command: list[str] | None = None
    args: list[str] | None = None
    env: dict[str, str] | None = None


class ResourceRequests(BaseModel):
    """CPU/Memory resource requests."""

    cpu: str = "8"
    memory: str = "32Gi"
    ephemeral_storage: str = "100Gi"


class GPUJobRequest(BaseModel):
    """Request to create a GPU job."""

    job_name: str
    project_id: str
    priority: JobPriority = JobPriority.MEDIUM
    gpu_requirements: GPURequirements
    container: ContainerSpec
    resources: ResourceRequests = ResourceRequests()
    budget_limit_usd: float | None = None
    max_duration_hours: int = 24
    preemptible: bool = True  # Allow spot instances
    checkpoint_s3_path: str | None = None


class GPUJobResponse(BaseModel):
    """Response for a GPU job."""

    job_id: str
    job_name: str
    project_id: str
    priority: JobPriority
    status: JobStatus
    queue_position: int | None
    estimated_start_time: datetime | None
    estimated_cost_usd: float | None
    actual_cost_usd: float | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    error_message: str | None

    model_config = ConfigDict(from_attributes=True)


class GPUMetrics(BaseModel):
    """Real-time GPU metrics."""

    node_name: str
    gpu_id: int
    gpu_type: str
    gpu_utilization: float
    gpu_memory_used_mb: float
    gpu_memory_total_mb: float
    gpu_temperature_c: float
    gpu_power_usage_w: float
    job_id: str | None
    timestamp: datetime


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
