"""GPU Cluster Management - Complete Examples.

This example demonstrates:
1. Submitting GPU jobs with different priorities
2. Training models with PyTorch on multi-GPU
3. Running distributed training with Ray
4. Integration with Kubeflow Pipelines
5. Monitoring GPU utilization and costs
6. Handling spot instance preemptions
"""

import asyncio

from odg_core.gpu.client import (
    GPUManagerClient,
    GPUManagerClientSync,
    GPUType,
    JobPriority,
    JobStatus,
)


async def example_1_submit_pytorch_training():
    """Example 1: Submit PyTorch training job."""
    print("\n" + "=" * 80)
    print("EXAMPLE 1: Submit PyTorch Training Job (4x A100 GPUs)")
    print("=" * 80)

    async with GPUManagerClient(api_url="http://gpu-manager:8000") as client:
        # Submit job
        job = await client.submit_job(
            job_name="finetune_llama_7b",
            project_id="ml-research",
            priority=JobPriority.HIGH,
            gpu_type=GPUType.A100_80GB,
            gpu_count=4,
            container_image="nvcr.io/nvidia/pytorch:24.01-py3",
            container_command=["python", "train.py"],
            container_args=["--model", "llama-7b", "--epochs", "10"],
            container_env={
                "CUDA_VISIBLE_DEVICES": "0,1,2,3",
                "NCCL_DEBUG": "INFO",
                "MASTER_ADDR": "localhost",
                "MASTER_PORT": "12355",
            },
            cpu="32",
            memory="256Gi",
            budget_limit_usd=100.0,
            max_duration_hours=12,
            preemptible=True,
            checkpoint_s3_path="s3://ml-checkpoints/llama-7b/",
        )

        print("\n✅ Job submitted successfully!")
        print(f"   Job ID: {job.job_id}")
        print(f"   Status: {job.status}")
        print(f"   Queue Position: {job.queue_position}")
        print(f"   Estimated Cost: ${job.estimated_cost_usd:.2f}")
        print(f"   Estimated Start: {job.estimated_start_time}")

        # Wait for job to start
        print("\n⏳ Waiting for job to start...")
        while True:
            job = await client.get_job(job.job_id)
            print(f"   Status: {job.status}")

            if job.status == JobStatus.RUNNING:
                print(f"\n🚀 Job started at {job.started_at}")
                break

            elif job.status in [JobStatus.FAILED, JobStatus.CANCELLED]:
                print(f"\n❌ Job failed: {job.error_message}")
                return

            await asyncio.sleep(10)

        # Monitor logs
        print("\n📋 Fetching logs...")
        logs = await client.get_logs(job.job_id, tail_lines=20)
        print(logs)


async def example_2_distributed_training_ray():
    """Example 2: Distributed training with Ray on 8x H100 GPUs."""
    print("\n" + "=" * 80)
    print("EXAMPLE 2: Distributed Training with Ray (8x H100 GPUs)")
    print("=" * 80)

    async with GPUManagerClient() as client:
        job = await client.submit_job(
            job_name="ray_distributed_training",
            project_id="ml-production",
            priority=JobPriority.CRITICAL,
            gpu_type=GPUType.H100_80GB,
            gpu_count=8,
            container_image="rayproject/ray-ml:2.9.0-gpu",
            container_command=["python", "ray_train.py"],
            container_args=[
                "--num-workers",
                "8",
                "--model",
                "gpt-3-175b",
                "--checkpoint-freq",
                "100",
            ],
            container_env={
                "RAY_ADDRESS": "auto",
                "RAY_OBJECT_STORE_MEMORY": "100000000000",  # 100GB
            },
            cpu="64",
            memory="512Gi",
            budget_limit_usd=500.0,
            max_duration_hours=24,
            preemptible=False,  # Critical workload, use on-demand
            checkpoint_s3_path="s3://ml-checkpoints/gpt-3/",
        )

        print(f"\n✅ Ray job submitted: {job.job_id}")
        print(f"   Priority: {job.priority} (on-demand instances)")
        print(f"   Estimated Cost: ${job.estimated_cost_usd:.2f}")

        # Wait for completion
        print("\n⏳ Waiting for job to complete (timeout: 24h)...")
        final_job = await client.wait_for_completion(job.job_id, timeout_minutes=1440)

        print("\n✅ Job completed!")
        print(f"   Status: {final_job.status}")
        print(f"   Duration: {(final_job.completed_at - final_job.started_at).total_seconds() / 3600:.1f}h")
        print(f"   Actual Cost: ${final_job.actual_cost_usd:.2f}")


async def example_3_batch_inference():
    """Example 3: Batch inference with T4 GPUs (cost-optimized)."""
    print("\n" + "=" * 80)
    print("EXAMPLE 3: Batch Inference (4x T4 GPUs, Spot Instances)")
    print("=" * 80)

    async with GPUManagerClient() as client:
        job = await client.submit_job(
            job_name="batch_inference_embeddings",
            project_id="ml-production",
            priority=JobPriority.LOW,  # Can wait
            gpu_type=GPUType.T4_16GB,
            gpu_count=4,
            container_image="nvcr.io/nvidia/tensorflow:24.01-tf2-py3",
            container_command=["python", "inference.py"],
            container_args=["--input", "s3://data/images/", "--batch-size", "128"],
            cpu="16",
            memory="64Gi",
            budget_limit_usd=10.0,
            max_duration_hours=6,
            preemptible=True,  # Spot instances = 70% cheaper
        )

        print(f"\n✅ Batch inference job submitted: {job.job_id}")
        print("   GPU Type: T4 (cost-optimized)")
        print("   Preemptible: Yes (spot instances)")
        print(f"   Estimated Cost: ${job.estimated_cost_usd:.2f}")


async def example_4_kubeflow_integration():
    """Example 4: Integration with Kubeflow Pipelines."""
    print("\n" + "=" * 80)
    print("EXAMPLE 4: Kubeflow Pipeline Integration")
    print("=" * 80)

    from kfp import dsl

    @dsl.pipeline(name="gpu-training-pipeline")
    def gpu_training_pipeline(model_name: str, dataset_path: str):
        """Kubeflow pipeline using GPU Manager."""
        # This would be integrated into Kubeflow's executor
        # For demonstration, showing the concept

        print("📊 Kubeflow Pipeline Task:")
        print(f"   Model: {model_name}")
        print(f"   Dataset: {dataset_path}")
        print("   GPUs: 4x A100 80GB")
        print("\n   Task would be submitted to GPU Manager via SDK")

    # Example pipeline execution
    gpu_training_pipeline(model_name="bert-large", dataset_path="s3://datasets/nlp/sst2")


async def example_5_monitor_cluster():
    """Example 5: Monitor GPU cluster stats."""
    print("\n" + "=" * 80)
    print("EXAMPLE 5: GPU Cluster Monitoring")
    print("=" * 80)

    async with GPUManagerClient() as client:
        stats = await client.get_cluster_stats()

        print("\n📊 GPU Cluster Statistics:")
        print(f"   Total GPUs: {stats.total_gpus}")
        print(f"   Available GPUs: {stats.available_gpus}")
        print(f"   In-Use GPUs: {stats.in_use_gpus}")
        print(f"   GPU Utilization: {stats.gpu_utilization_avg:.1f}%")
        print("\n📋 Job Queue:")
        print(f"   Total Jobs: {stats.total_jobs}")
        print(f"   Running: {stats.running_jobs}")
        print(f"   Queued: {stats.queued_jobs}")
        print("\n💰 Cost:")
        print(f"   Today's Cost: ${stats.total_cost_today_usd:.2f}")
        print(f"   Spot Instances: {stats.spot_instance_percentage:.1f}%")


async def example_6_list_jobs_by_project():
    """Example 6: List all jobs for a project."""
    print("\n" + "=" * 80)
    print("EXAMPLE 6: List Jobs by Project")
    print("=" * 80)

    async with GPUManagerClient() as client:
        jobs = await client.list_jobs(project_id="ml-research", limit=10)

        print("\n📋 Jobs for project 'ml-research' (last 10):")
        for job in jobs:
            status_icon = {
                JobStatus.COMPLETED: "✅",
                JobStatus.RUNNING: "🏃",
                JobStatus.QUEUED: "⏳",
                JobStatus.FAILED: "❌",
                JobStatus.CANCELLED: "🚫",
            }.get(job.status, "❓")

            print(f"\n{status_icon} {job.job_name} ({job.job_id})")
            print(f"   Status: {job.status}")
            print(f"   Priority: {job.priority}")

            if job.actual_cost_usd:
                print(f"   Cost: ${job.actual_cost_usd:.2f}")
            else:
                print(f"   Estimated Cost: ${job.estimated_cost_usd:.2f}")

            if job.started_at and job.completed_at:
                duration = (job.completed_at - job.started_at).total_seconds() / 3600
                print(f"   Duration: {duration:.1f}h")


async def example_7_spot_preemption_handling():
    """Example 7: Spot instance preemption handling."""
    print("\n" + "=" * 80)
    print("EXAMPLE 7: Spot Instance Preemption Handling")
    print("=" * 80)

    async with GPUManagerClient() as client:
        # Submit preemptible job with checkpointing
        job = await client.submit_job(
            job_name="long_training_with_checkpoints",
            project_id="ml-research",
            priority=JobPriority.MEDIUM,
            gpu_type=GPUType.A100_80GB,
            gpu_count=4,
            container_image="pytorch:latest",
            container_command=["python", "train_with_checkpointing.py"],
            container_args=["--checkpoint-every", "900"],  # 15 min
            budget_limit_usd=50.0,
            max_duration_hours=24,
            preemptible=True,
            checkpoint_s3_path="s3://ml-checkpoints/long-training/",
        )

        print(f"\n✅ Preemptible job submitted: {job.job_id}")
        print("   Checkpointing: Every 15 minutes to S3")
        print("   Max Retries: 3 (after preemption)")
        print("   Cost Savings: ~70% vs. on-demand")

        print("\n📝 Preemption Handling:")
        print("   1. Job runs on spot instance")
        print("   2. Checkpoints saved to S3 every 15min")
        print("   3. If preempted → automatically retried (up to 3x)")
        print("   4. Resumes from last checkpoint")
        print("   5. If spot unavailable → falls back to on-demand")


def example_8_synchronous_client():
    """Example 8: Using synchronous client (non-async)."""
    print("\n" + "=" * 80)
    print("EXAMPLE 8: Synchronous Client (for scripts/notebooks)")
    print("=" * 80)

    # For users who don't want to use async/await
    client = GPUManagerClientSync(api_url="http://gpu-manager:8000")

    # Submit job (synchronous)
    job = client.submit_job(
        job_name="quick_experiment",
        project_id="ml-research",
        priority=JobPriority.MEDIUM,
        gpu_type=GPUType.A10G_24GB,
        gpu_count=1,
        container_image="pytorch:latest",
        container_command=["python", "experiment.py"],
    )

    print(f"\n✅ Job submitted: {job.job_id}")
    print(f"   Queue Position: {job.queue_position}")

    # Get cluster stats (synchronous)
    stats = client.get_cluster_stats()
    print(f"\n📊 Available GPUs: {stats.available_gpus}/{stats.total_gpus}")


async def main():
    """Run all examples."""
    print("=" * 80)
    print("GPU CLUSTER MANAGEMENT - Examples")
    print("=" * 80)

    await example_1_submit_pytorch_training()
    await example_2_distributed_training_ray()
    await example_3_batch_inference()
    await example_4_kubeflow_integration()
    await example_5_monitor_cluster()
    await example_6_list_jobs_by_project()
    await example_7_spot_preemption_handling()
    example_8_synchronous_client()

    print("\n" + "=" * 80)
    print("✅ ALL EXAMPLES COMPLETED")
    print("=" * 80)
    print("\n📚 Key Features Demonstrated:")
    print("  ✅ GPU job submission with priority scheduling")
    print("  ✅ Multi-GPU training (PyTorch, Ray)")
    print("  ✅ Spot instance support (70% cost savings)")
    print("  ✅ Automatic preemption handling with checkpointing")
    print("  ✅ Budget limits and cost tracking")
    print("  ✅ Kubeflow Pipelines integration")
    print("  ✅ Cluster monitoring and stats")
    print("  ✅ Both async and sync client APIs")

    print("\n💰 Cost Optimization:")
    print("  • Spot instances: 70% cheaper than on-demand")
    print("  • Auto-scaling: Only pay for GPUs when needed")
    print("  • Budget alerts: Prevent overspending")
    print("  • T4 for inference: 5x cheaper than A100")

    print("\n🚀 Next Steps:")
    print("  1. Deploy GPU Manager: helm install gpu-manager ./deploy/helm/gpu-manager")
    print("  2. Install SDK: pip install odg-core[gpu]")
    print("  3. Submit your first job: python examples/gpu_cluster_management_example.py")
    print("  4. Monitor dashboard: https://grafana.opendatagov.io/d/gpu-cluster")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
