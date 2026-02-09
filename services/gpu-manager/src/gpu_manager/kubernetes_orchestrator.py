"""Kubernetes Orchestrator - Creates and manages GPU jobs in K8s."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any

from gpu_manager.models import GPUJobRow, GPUType
from kubernetes import client, config
from kubernetes.client.rest import ApiException

if TYPE_CHECKING:
    from kubernetes.client import V1Job

logger = logging.getLogger(__name__)


class KubernetesOrchestrator:
    """Manages GPU job execution in Kubernetes."""

    def __init__(self, namespace: str = "gpu-workloads"):
        """Initialize Kubernetes orchestrator.

        Args:
            namespace: Kubernetes namespace for GPU jobs
        """
        try:
            config.load_incluster_config()
        except config.ConfigException:
            config.load_kube_config()

        self.batch_v1 = client.BatchV1Api()
        self.core_v1 = client.CoreV1Api()
        self.namespace = namespace

        # GPU instance type mapping
        self.gpu_instance_types = {
            GPUType.A100_80GB: "p4d.24xlarge",
            GPUType.H100_80GB: "p5.48xlarge",
            GPUType.L40S_48GB: "g6.48xlarge",
            GPUType.A10G_24GB: "g5.xlarge",
            GPUType.T4_16GB: "g4dn.xlarge",
        }

    def create_job_spec(self, job: GPUJobRow) -> V1Job:
        """Create Kubernetes Job specification.

        Args:
            job: GPU job database row

        Returns:
            Kubernetes Job object
        """
        # Container spec
        container = client.V1Container(
            name="gpu-job",
            image=job.container_image,
            command=job.container_command,
            args=job.container_args,
            env=[client.V1EnvVar(name=k, value=v) for k, v in (job.container_env or {}).items()],
            resources=client.V1ResourceRequirements(
                requests={
                    "cpu": job.cpu_request,
                    "memory": job.memory_request,
                    "nvidia.com/gpu": str(job.gpu_count),
                },
                limits={
                    "nvidia.com/gpu": str(job.gpu_count),
                },
            ),
            volume_mounts=[
                client.V1VolumeMount(name="dshm", mount_path="/dev/shm"),  # Shared memory for multi-GPU
            ],
        )

        # Pod spec
        pod_spec = client.V1PodSpec(
            containers=[container],
            restart_policy="Never",
            volumes=[
                client.V1Volume(
                    name="dshm",
                    empty_dir=client.V1EmptyDirVolumeSource(medium="Memory"),
                )
            ],
            node_selector={
                "gpu-type": job.gpu_type.lower().replace("_", "-"),
                "workload-type": "gpu-training",
            },
            tolerations=[client.V1Toleration(key="nvidia.com/gpu", operator="Exists", effect="NoSchedule")],
            # Priority class for preemption
            priority_class_name="gpu-workload-high" if job.priority == "high" else "gpu-workload-medium",
        )

        # If preemptible, prefer spot instances
        if job.preemptible:
            pod_spec.node_selector["karpenter.sh/capacity-type"] = "spot"

        # Job spec
        job_spec = client.V1JobSpec(
            template=client.V1PodTemplateSpec(
                metadata=client.V1ObjectMeta(
                    labels={
                        "app": "gpu-job",
                        "job-id": job.job_id,
                        "project-id": job.project_id,
                        "gpu-type": job.gpu_type,
                    }
                ),
                spec=pod_spec,
            ),
            backoff_limit=0,  # Don't retry (handled by JobQueueManager)
            ttl_seconds_after_finished=3600,  # Delete job after 1h
        )

        # Create Job
        k8s_job = client.V1Job(
            api_version="batch/v1",
            kind="Job",
            metadata=client.V1ObjectMeta(
                name=job.job_id,
                namespace=self.namespace,
                labels={
                    "job-id": job.job_id,
                    "project-id": job.project_id,
                    "priority": job.priority,
                },
                annotations={
                    "budget-limit-usd": str(job.budget_limit_usd or 0),
                    "max-duration-hours": str(job.max_duration_hours),
                },
            ),
            spec=job_spec,
        )

        return k8s_job

    async def submit_job(self, job: GPUJobRow) -> dict[str, str]:
        """Submit job to Kubernetes.

        Args:
            job: GPU job to submit

        Returns:
            Job metadata (namespace, job_name)

        Raises:
            ApiException: If job submission fails
        """
        k8s_job = self.create_job_spec(job)

        try:
            response = self.batch_v1.create_namespaced_job(namespace=self.namespace, body=k8s_job)

            logger.info(f"Created Kubernetes job {response.metadata.name} in namespace {self.namespace}")

            return {
                "namespace": self.namespace,
                "job_name": response.metadata.name,
            }

        except ApiException as e:
            logger.error(f"Failed to create Kubernetes job: {e}")
            raise

    async def get_job_status(self, job_id: str) -> dict[str, Any]:
        """Get job status from Kubernetes.

        Args:
            job_id: Job identifier

        Returns:
            Job status dictionary
        """
        try:
            job = self.batch_v1.read_namespaced_job(name=job_id, namespace=self.namespace)

            status = {
                "active": job.status.active or 0,
                "succeeded": job.status.succeeded or 0,
                "failed": job.status.failed or 0,
                "start_time": job.status.start_time,
                "completion_time": job.status.completion_time,
            }

            # Get pod info
            pods = self.core_v1.list_namespaced_pod(namespace=self.namespace, label_selector=f"job-name={job_id}")

            if pods.items:
                pod = pods.items[0]
                status["pod_name"] = pod.metadata.name
                status["node_name"] = pod.spec.node_name
                status["pod_phase"] = pod.status.phase

            return status

        except ApiException as e:
            logger.error(f"Failed to get job status: {e}")
            return {}

    async def delete_job(self, job_id: str) -> bool:
        """Delete job from Kubernetes.

        Args:
            job_id: Job identifier

        Returns:
            True if deleted successfully
        """
        try:
            self.batch_v1.delete_namespaced_job(
                name=job_id,
                namespace=self.namespace,
                propagation_policy="Foreground",  # Delete pods too
            )

            logger.info(f"Deleted Kubernetes job {job_id}")
            return True

        except ApiException as e:
            logger.error(f"Failed to delete job: {e}")
            return False

    async def get_pod_logs(self, pod_name: str, tail_lines: int = 100) -> str:
        """Get pod logs.

        Args:
            pod_name: Pod name
            tail_lines: Number of lines to retrieve

        Returns:
            Pod logs
        """
        try:
            logs = self.core_v1.read_namespaced_pod_log(name=pod_name, namespace=self.namespace, tail_lines=tail_lines)
            return logs

        except ApiException as e:
            logger.error(f"Failed to get pod logs: {e}")
            return ""

    async def watch_job(self, job_id: str, callback: callable):
        """Watch job status changes.

        Args:
            job_id: Job identifier
            callback: Function to call on status change
        """
        from kubernetes import watch

        w = watch.Watch()

        try:
            for event in w.stream(
                self.batch_v1.list_namespaced_job,
                namespace=self.namespace,
                field_selector=f"metadata.name={job_id}",
                timeout_seconds=3600,  # 1 hour timeout
            ):
                event_type = event["type"]  # ADDED, MODIFIED, DELETED
                job = event["object"]

                await callback(event_type, job)

                # Stop watching if job completed or failed
                if job.status.succeeded or job.status.failed:
                    w.stop()
                    break

        except ApiException as e:
            logger.error(f"Error watching job: {e}")

    async def get_node_gpu_capacity(self) -> dict[str, dict[str, int]]:
        """Get GPU capacity of all nodes.

        Returns:
            Dict mapping node name to GPU info
        """
        nodes = self.core_v1.list_node(label_selector="gpu-type")

        gpu_capacity = {}

        for node in nodes.items:
            node_name = node.metadata.name
            gpu_count = int(node.status.allocatable.get("nvidia.com/gpu", 0))
            gpu_type = node.metadata.labels.get("gpu-type", "unknown")

            gpu_capacity[node_name] = {
                "gpu_count": gpu_count,
                "gpu_type": gpu_type,
                "capacity_type": node.metadata.labels.get("karpenter.sh/capacity-type", "on-demand"),
            }

        return gpu_capacity

    async def get_available_gpus(self) -> int:
        """Get number of available (unallocated) GPUs.

        Returns:
            Number of available GPUs
        """
        nodes = self.core_v1.list_node(label_selector="gpu-type")

        total_available = 0

        for node in nodes.items:
            allocatable = int(node.status.allocatable.get("nvidia.com/gpu", 0))
            # Get pods running on this node
            pods = self.core_v1.list_pod_for_all_namespaces(field_selector=f"spec.nodeName={node.metadata.name}")

            allocated = sum(
                int(container.resources.requests.get("nvidia.com/gpu", 0))
                for pod in pods.items
                for container in pod.spec.containers
            )

            available = allocatable - allocated
            total_available += max(0, available)

        return total_available

    async def trigger_karpenter_scale_up(self, gpu_type: str, gpu_count: int):
        """Signal Karpenter to provision new GPU nodes.

        Args:
            gpu_type: GPU type to provision
            gpu_count: Number of GPUs needed

        Note:
            Karpenter automatically scales based on pending pods,
            so we create a placeholder pod to trigger scaling.
        """
        placeholder_pod = client.V1Pod(
            metadata=client.V1ObjectMeta(
                name=f"placeholder-{gpu_type.lower()}-{datetime.utcnow().strftime('%s')}",
                namespace=self.namespace,
                labels={"placeholder": "true"},
            ),
            spec=client.V1PodSpec(
                containers=[
                    client.V1Container(
                        name="placeholder",
                        image="pause:latest",
                        resources=client.V1ResourceRequirements(requests={"nvidia.com/gpu": str(gpu_count)}),
                    )
                ],
                node_selector={"gpu-type": gpu_type.lower().replace("_", "-")},
                tolerations=[client.V1Toleration(key="nvidia.com/gpu", operator="Exists", effect="NoSchedule")],
            ),
        )

        try:
            self.core_v1.create_namespaced_pod(namespace=self.namespace, body=placeholder_pod)
            logger.info(f"Created placeholder pod to trigger Karpenter scale-up for {gpu_type}")

        except ApiException as e:
            logger.error(f"Failed to create placeholder pod: {e}")
