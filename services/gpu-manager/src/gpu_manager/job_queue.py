"""Job Queue Manager - Priority scheduling for GPU jobs."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from gpu_manager.models import (
    GPU_HOURLY_COST,
    GPUJobRow,
    JobPriority,
    JobStatus,
)
from sqlalchemy import select, update

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class JobQueueManager:
    """Manages job queue with priority scheduling."""

    def __init__(self, db: AsyncSession):
        """Initialize job queue manager.

        Args:
            db: Database session
        """
        self.db = db
        self.priority_weights = {
            JobPriority.CRITICAL: 1000,
            JobPriority.HIGH: 100,
            JobPriority.MEDIUM: 10,
            JobPriority.LOW: 1,
        }

    async def enqueue_job(self, job_id: str, priority: JobPriority = JobPriority.MEDIUM) -> int:
        """Add job to queue and assign position.

        Args:
            job_id: Job identifier
            priority: Job priority

        Returns:
            Queue position (1-indexed)
        """
        # Get current queue size
        result = await self.db.execute(
            select(GPUJobRow).where(GPUJobRow.status.in_([JobStatus.QUEUED, JobStatus.PENDING]))
        )
        queued_jobs = result.scalars().all()

        # Calculate position based on priority
        higher_priority_count = sum(
            1
            for job in queued_jobs
            if self.priority_weights[JobPriority(job.priority)] > self.priority_weights[priority]
        )

        queue_position = higher_priority_count + 1

        # Update job status and position
        await self.db.execute(
            update(GPUJobRow)
            .where(GPUJobRow.job_id == job_id)
            .values(
                status=JobStatus.QUEUED.value,
                queue_position=queue_position,
                queued_at=datetime.utcnow(),
            )
        )
        await self.db.commit()

        logger.info(f"Enqueued job {job_id} with priority {priority.value} at position {queue_position}")
        return queue_position

    async def get_next_job(self, gpu_type: str | None = None) -> GPUJobRow | None:
        """Get next job from queue based on priority.

        Args:
            gpu_type: Filter by GPU type (optional)

        Returns:
            Next job to execute or None if queue is empty
        """
        query = select(GPUJobRow).where(GPUJobRow.status == JobStatus.QUEUED.value)

        if gpu_type:
            query = query.where(GPUJobRow.gpu_type == gpu_type)

        # Order by priority (descending) then created_at (ascending)
        query = query.order_by(GPUJobRow.priority.desc(), GPUJobRow.created_at.asc())

        result = await self.db.execute(query.limit(1))
        job = result.scalars().first()

        if job:
            logger.info(f"Next job in queue: {job.job_id} (priority: {job.priority})")

        return job

    async def update_queue_positions(self):
        """Recalculate queue positions after job completion."""
        result = await self.db.execute(
            select(GPUJobRow)
            .where(GPUJobRow.status == JobStatus.QUEUED.value)
            .order_by(GPUJobRow.priority.desc(), GPUJobRow.created_at.asc())
        )
        queued_jobs = result.scalars().all()

        for position, job in enumerate(queued_jobs, start=1):
            await self.db.execute(
                update(GPUJobRow).where(GPUJobRow.job_id == job.job_id).values(queue_position=position)
            )

        await self.db.commit()
        logger.info(f"Updated queue positions for {len(queued_jobs)} jobs")

    async def start_job(self, job_id: str, node_name: str, pod_name: str) -> None:
        """Mark job as running.

        Args:
            job_id: Job identifier
            node_name: Kubernetes node name
            pod_name: Kubernetes pod name
        """
        await self.db.execute(
            update(GPUJobRow)
            .where(GPUJobRow.job_id == job_id)
            .values(
                status=JobStatus.RUNNING.value,
                started_at=datetime.utcnow(),
                node_name=node_name,
                pod_name=pod_name,
            )
        )
        await self.db.commit()

        # Update queue positions
        await self.update_queue_positions()

        logger.info(f"Job {job_id} started on node {node_name}")

    async def complete_job(self, job_id: str, success: bool, error: str | None = None):
        """Mark job as completed or failed.

        Args:
            job_id: Job identifier
            success: Whether job succeeded
            error: Error message if failed
        """
        status = JobStatus.COMPLETED if success else JobStatus.FAILED

        # Calculate actual cost
        result = await self.db.execute(select(GPUJobRow).where(GPUJobRow.job_id == job_id))
        job = result.scalars().first()

        if job and job.started_at:
            duration_hours = (datetime.utcnow() - job.started_at).total_seconds() / 3600
            gpu_cost = GPU_HOURLY_COST.get(job.gpu_type, 0.0)
            actual_cost = duration_hours * gpu_cost * job.gpu_count

            # Apply spot discount if preemptible
            if job.preemptible:
                actual_cost *= 1 - 0.70  # 70% discount

            await self.db.execute(
                update(GPUJobRow)
                .where(GPUJobRow.job_id == job_id)
                .values(
                    status=status.value,
                    completed_at=datetime.utcnow(),
                    error_message=error,
                    actual_cost_usd=actual_cost,
                )
            )
        else:
            await self.db.execute(
                update(GPUJobRow)
                .where(GPUJobRow.job_id == job_id)
                .values(
                    status=status.value,
                    completed_at=datetime.utcnow(),
                    error_message=error,
                )
            )

        await self.db.commit()

        # Update queue positions
        await self.update_queue_positions()

        logger.info(f"Job {job_id} completed with status {status.value}")

    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a pending or running job.

        Args:
            job_id: Job identifier

        Returns:
            True if cancelled successfully
        """
        result = await self.db.execute(select(GPUJobRow).where(GPUJobRow.job_id == job_id))
        job = result.scalars().first()

        if not job:
            return False

        if job.status in [JobStatus.COMPLETED.value, JobStatus.FAILED.value]:
            logger.warning(f"Cannot cancel completed job {job_id}")
            return False

        await self.db.execute(
            update(GPUJobRow)
            .where(GPUJobRow.job_id == job_id)
            .values(status=JobStatus.CANCELLED.value, completed_at=datetime.utcnow())
        )
        await self.db.commit()

        # Update queue positions
        await self.update_queue_positions()

        logger.info(f"Job {job_id} cancelled")
        return True

    async def handle_preemption(self, job_id: str) -> bool:
        """Handle spot instance preemption.

        Args:
            job_id: Job identifier

        Returns:
            True if job will be retried
        """
        result = await self.db.execute(select(GPUJobRow).where(GPUJobRow.job_id == job_id))
        job = result.scalars().first()

        if not job:
            return False

        # Check if retries remaining
        if job.retry_count < job.max_retries:
            await self.db.execute(
                update(GPUJobRow)
                .where(GPUJobRow.job_id == job_id)
                .values(
                    status=JobStatus.QUEUED.value,
                    retry_count=job.retry_count + 1,
                    node_name=None,
                    pod_name=None,
                )
            )
            await self.db.commit()

            # Re-enqueue
            await self.enqueue_job(job_id, JobPriority(job.priority))

            logger.info(f"Job {job_id} preempted, retry {job.retry_count + 1}/{job.max_retries}")
            return True
        else:
            # Max retries exceeded
            await self.complete_job(job_id, success=False, error="Max retries exceeded after preemption")
            logger.error(f"Job {job_id} failed after {job.max_retries} preemptions")
            return False

    async def estimate_start_time(self, job_id: str) -> datetime | None:
        """Estimate when a job will start based on queue position.

        Args:
            job_id: Job identifier

        Returns:
            Estimated start time or None
        """
        result = await self.db.execute(select(GPUJobRow).where(GPUJobRow.job_id == job_id))
        job = result.scalars().first()

        if not job or not job.queue_position:
            return None

        # Simple heuristic: assume 5 min per job ahead in queue
        minutes_to_wait = (job.queue_position - 1) * 5
        estimated_start = datetime.utcnow() + timedelta(minutes=minutes_to_wait)

        return estimated_start

    async def get_queue_stats(self) -> dict[str, Any]:
        """Get queue statistics.

        Returns:
            Queue stats dictionary
        """
        result = await self.db.execute(select(GPUJobRow))
        all_jobs = result.scalars().all()

        stats = {
            "total_jobs": len(all_jobs),
            "queued": sum(1 for j in all_jobs if j.status == JobStatus.QUEUED.value),
            "running": sum(1 for j in all_jobs if j.status == JobStatus.RUNNING.value),
            "completed": sum(1 for j in all_jobs if j.status == JobStatus.COMPLETED.value),
            "failed": sum(1 for j in all_jobs if j.status == JobStatus.FAILED.value),
            "cancelled": sum(1 for j in all_jobs if j.status == JobStatus.CANCELLED.value),
            "preempted": sum(1 for j in all_jobs if j.status == JobStatus.PREEMPTED.value),
        }

        return stats

    async def check_budget_exceeded(self, job_id: str) -> bool:
        """Check if job has exceeded budget limit.

        Args:
            job_id: Job identifier

        Returns:
            True if budget exceeded
        """
        result = await self.db.execute(select(GPUJobRow).where(GPUJobRow.job_id == job_id))
        job = result.scalars().first()

        if not job or not job.budget_limit_usd:
            return False

        if job.actual_cost_usd and job.actual_cost_usd > job.budget_limit_usd:
            logger.warning(f"Job {job_id} exceeded budget: ${job.actual_cost_usd:.2f} > ${job.budget_limit_usd:.2f}")
            return True

        return False

    async def check_timeout(self, job_id: str) -> bool:
        """Check if job has exceeded max duration.

        Args:
            job_id: Job identifier

        Returns:
            True if timeout exceeded
        """
        result = await self.db.execute(select(GPUJobRow).where(GPUJobRow.job_id == job_id))
        job = result.scalars().first()

        if not job or not job.started_at or not job.max_duration_hours:
            return False

        elapsed_hours = (datetime.utcnow() - job.started_at).total_seconds() / 3600

        if elapsed_hours > job.max_duration_hours:
            logger.warning(f"Job {job_id} exceeded timeout: {elapsed_hours:.1f}h > {job.max_duration_hours}h")
            return True

        return False
