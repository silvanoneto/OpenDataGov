"""Workflow Engine - Executes DAG-based multi-expert workflows."""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict, deque
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from expert_orchestrator.context_manager import SharedContext
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from expert_orchestrator.expert_client import ExpertClient
    from expert_orchestrator.registry import ExpertRegistry

logger = logging.getLogger(__name__)


class TaskStatus(StrEnum):
    """Status of a workflow task."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class WorkflowStatus(StrEnum):
    """Status of entire workflow."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WorkflowTask(BaseModel):
    """A single task in a workflow DAG."""

    id: str = Field(..., description="Unique task ID")
    expert: str = Field(..., description="Expert type to use")
    action: str = Field(..., description="Action to perform")
    inputs: dict[str, Any] = Field(default_factory=dict, description="Task inputs")
    depends_on: list[str] = Field(default_factory=list, description="Task dependencies")
    timeout_seconds: int = Field(default=300, description="Task timeout")
    retry_count: int = Field(default=0, description="Number of retries")
    max_retries: int = Field(default=3, description="Max retry attempts")


class WorkflowDefinition(BaseModel):
    """Workflow definition with DAG of tasks."""

    workflow_id: str = Field(..., description="Unique workflow ID")
    workflow_name: str = Field(..., description="Human-readable name")
    description: str | None = None
    tasks: list[WorkflowTask] = Field(..., description="Tasks to execute")
    timeout_seconds: int = Field(default=3600, description="Overall workflow timeout")
    created_by: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class TaskResult(BaseModel):
    """Result of a single task execution."""

    task_id: str
    status: TaskStatus
    expert_id: str | None = None
    result: dict[str, Any] | None = None
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_ms: int | None = None
    retries: int = 0


class WorkflowResult(BaseModel):
    """Result of entire workflow execution."""

    workflow_id: str
    status: WorkflowStatus
    task_results: dict[str, TaskResult] = Field(default_factory=dict)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_ms: int | None = None
    error: str | None = None


class WorkflowEngine:
    """Executes DAG-based expert workflows."""

    def __init__(self, registry: ExpertRegistry, expert_client: ExpertClient):
        """Initialize workflow engine.

        Args:
            registry: Expert registry for finding experts
            expert_client: Client for invoking experts
        """
        self.registry = registry
        self.expert_client = expert_client

    async def execute_workflow(self, workflow_def: WorkflowDefinition) -> WorkflowResult:
        """Execute a complete workflow.

        Args:
            workflow_def: Workflow definition

        Returns:
            Workflow execution result

        Example:
            >>> workflow = WorkflowDefinition(
            ...     workflow_id="onboard_dataset",
            ...     workflow_name="Dataset Onboarding",
            ...     tasks=[
            ...         WorkflowTask(
            ...             id="schema",
            ...             expert="SchemaExpert",
            ...             action="analyze_schema",
            ...             inputs={"file_path": "s3://data/file.parquet"}
            ...         ),
            ...         WorkflowTask(
            ...             id="quality",
            ...             expert="QualityExpert",
            ...             action="define_expectations",
            ...             depends_on=["schema"]
            ...         )
            ...     ]
            ... )
            >>> result = await engine.execute_workflow(workflow)
        """
        logger.info(f"🚀 Starting workflow: {workflow_def.workflow_id}")

        start_time = datetime.utcnow()
        context = SharedContext()
        result = WorkflowResult(
            workflow_id=workflow_def.workflow_id, status=WorkflowStatus.RUNNING, started_at=start_time
        )

        try:
            # Validate workflow (check for cycles, missing deps)
            self._validate_workflow(workflow_def)

            # Build dependency graph
            graph = self._build_dependency_graph(workflow_def.tasks)

            # Topological sort to get execution levels
            execution_levels = self._topological_sort(graph, workflow_def.tasks)

            logger.info(f"Workflow has {len(execution_levels)} execution levels")

            # Execute tasks level by level
            for level_index, level_tasks in enumerate(execution_levels):
                logger.info(f"📋 Level {level_index + 1}: Executing {len(level_tasks)} tasks in parallel")

                # Execute all tasks in this level concurrently
                level_results = await asyncio.gather(
                    *[self._execute_task(task, result.task_results, context) for task in level_tasks],
                    return_exceptions=True,
                )

                # Store results and check for failures
                for task, task_result in zip(level_tasks, level_results, strict=False):
                    if isinstance(task_result, Exception):
                        logger.error(f"Task {task.id} failed with exception: {task_result}")
                        result.task_results[task.id] = TaskResult(
                            task_id=task.id, status=TaskStatus.FAILED, error=str(task_result)
                        )
                        # Fail entire workflow on task failure
                        raise task_result
                    else:
                        result.task_results[task.id] = task_result

                        if task_result.status == TaskStatus.FAILED:
                            error_msg = f"Task {task.id} failed: {task_result.error}"
                            logger.error(error_msg)
                            result.status = WorkflowStatus.FAILED
                            result.error = error_msg
                            return result

            # All tasks completed successfully
            result.status = WorkflowStatus.COMPLETED
            result.completed_at = datetime.utcnow()
            result.duration_ms = int((result.completed_at - start_time).total_seconds() * 1000)

            logger.info(f"✅ Workflow completed: {workflow_def.workflow_id} ({result.duration_ms}ms)")

            return result

        except Exception as e:
            logger.error(f"❌ Workflow failed: {workflow_def.workflow_id} - {e}")
            result.status = WorkflowStatus.FAILED
            result.error = str(e)
            result.completed_at = datetime.utcnow()
            result.duration_ms = int((result.completed_at - start_time).total_seconds() * 1000)
            return result

    async def _execute_task(
        self, task: WorkflowTask, previous_results: dict[str, TaskResult], context: SharedContext
    ) -> TaskResult:
        """Execute a single task.

        Args:
            task: Task to execute
            previous_results: Results from previous tasks
            context: Shared context

        Returns:
            Task execution result
        """
        logger.info(f"▶️  Executing task: {task.id} (expert={task.expert})")
        start_time = datetime.utcnow()

        task_result = TaskResult(task_id=task.id, status=TaskStatus.RUNNING, started_at=start_time)

        try:
            # Get inputs from task definition
            task_inputs = task.inputs.copy()

            # Add outputs from dependent tasks to inputs
            for dep_task_id in task.depends_on:
                dep_result = previous_results.get(dep_task_id)
                if dep_result and dep_result.result:
                    task_inputs[f"from_{dep_task_id}"] = dep_result.result

            # Add shared context
            task_inputs["_context"] = await context.get_all()

            # Find appropriate expert
            from expert_orchestrator.registry import ExpertCapability

            # Map action to capability (simplified)
            capability_map = {
                "analyze_schema": ExpertCapability.SCHEMA_ANALYSIS,
                "define_expectations": ExpertCapability.QUALITY_VALIDATION,
                "detect_pii": ExpertCapability.PII_DETECTION,
                "validate_gdpr": ExpertCapability.GDPR_VALIDATION,
                "estimate_storage_cost": ExpertCapability.COST_OPTIMIZATION,
                "map_dependencies": ExpertCapability.LINEAGE_TRACING,
                "analyze_execution_plan": ExpertCapability.PERFORMANCE_TUNING,
                "identify_bottleneck_datasets": ExpertCapability.LINEAGE_TRACING,
                "check_data_skew": ExpertCapability.ANOMALY_DETECTION,
                "suggest_resource_optimization": ExpertCapability.COST_OPTIMIZATION,
            }

            capability = capability_map.get(
                task.action,
                ExpertCapability.SCHEMA_ANALYSIS,  # fallback
            )

            expert_registration = await self.registry.get_least_loaded_expert(capability)

            if not expert_registration:
                raise RuntimeError(f"No available expert for capability: {capability}")

            task_result.expert_id = expert_registration.expert_id

            # Increment load
            await self.registry.increment_load(expert_registration.expert_id)

            try:
                # Execute task with timeout
                expert_result = await asyncio.wait_for(
                    self.expert_client.invoke_expert(
                        expert_id=expert_registration.expert_id,
                        endpoint=expert_registration.endpoint,
                        action=task.action,
                        inputs=task_inputs,
                    ),
                    timeout=task.timeout_seconds,
                )

                task_result.result = expert_result
                task_result.status = TaskStatus.COMPLETED

                # Store result in shared context
                await context.set(f"task_{task.id}_result", expert_result)

                # Record successful invocation
                end_time = datetime.utcnow()
                latency_ms = int((end_time - start_time).total_seconds() * 1000)
                await self.registry.record_invocation(expert_registration.expert_id, latency_ms, success=True)

            finally:
                # Decrement load
                await self.registry.decrement_load(expert_registration.expert_id)

        except TimeoutError:
            task_result.status = TaskStatus.FAILED
            task_result.error = f"Task timed out after {task.timeout_seconds}s"
            logger.error(f"⏱️  Task {task.id} timed out")

        except Exception as e:
            task_result.status = TaskStatus.FAILED
            task_result.error = str(e)
            logger.error(f"❌ Task {task.id} failed: {e}")

            # Record failed invocation
            if task_result.expert_id:
                end_time = datetime.utcnow()
                latency_ms = int((end_time - start_time).total_seconds() * 1000)
                await self.registry.record_invocation(task_result.expert_id, latency_ms, success=False)

        finally:
            task_result.completed_at = datetime.utcnow()
            task_result.duration_ms = int((task_result.completed_at - start_time).total_seconds() * 1000)

        logger.info(f"✓ Task {task.id} {task_result.status.value} ({task_result.duration_ms}ms)")

        return task_result

    def _validate_workflow(self, workflow_def: WorkflowDefinition) -> None:
        """Validate workflow definition.

        Args:
            workflow_def: Workflow to validate

        Raises:
            ValueError: If workflow is invalid
        """
        task_ids = {task.id for task in workflow_def.tasks}

        # Check for duplicate task IDs
        if len(task_ids) != len(workflow_def.tasks):
            raise ValueError("Duplicate task IDs found in workflow")

        # Check that all dependencies exist
        for task in workflow_def.tasks:
            for dep in task.depends_on:
                if dep not in task_ids:
                    raise ValueError(f"Task {task.id} depends on non-existent task: {dep}")

        # Check for cycles
        graph = self._build_dependency_graph(workflow_def.tasks)
        if self._has_cycle(graph):
            raise ValueError("Workflow contains circular dependencies")

    def _build_dependency_graph(self, tasks: list[WorkflowTask]) -> dict[str, list[str]]:
        """Build dependency graph from tasks.

        Args:
            tasks: List of tasks

        Returns:
            Adjacency list representation of graph
        """
        graph = defaultdict(list)

        for task in tasks:
            if not task.depends_on:
                graph[task.id] = []
            else:
                for dep in task.depends_on:
                    graph[dep].append(task.id)

        return dict(graph)

    def _has_cycle(self, graph: dict[str, list[str]]) -> bool:
        """Check if graph has a cycle using DFS.

        Args:
            graph: Dependency graph

        Returns:
            True if cycle exists
        """
        visited = set()
        rec_stack = set()

        def dfs(node: str) -> bool:
            visited.add(node)
            rec_stack.add(node)

            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    if dfs(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True

            rec_stack.remove(node)
            return False

        return any(node not in visited and dfs(node) for node in graph)

    def _topological_sort(self, graph: dict[str, list[str]], tasks: list[WorkflowTask]) -> list[list[WorkflowTask]]:
        """Topological sort to determine execution levels.

        Args:
            graph: Dependency graph
            tasks: List of tasks

        Returns:
            List of execution levels (each level can run in parallel)
        """
        # Calculate in-degree for each node
        in_degree = {task.id: len(task.depends_on) for task in tasks}

        # Find all nodes with in-degree 0 (no dependencies)
        queue = deque([task.id for task in tasks if in_degree[task.id] == 0])

        levels = []
        task_map = {task.id: task for task in tasks}

        while queue:
            # All tasks in current level have no remaining dependencies
            current_level = []
            level_size = len(queue)

            for _ in range(level_size):
                task_id = queue.popleft()
                current_level.append(task_map[task_id])

                # Decrease in-degree for neighbors
                for neighbor in graph.get(task_id, []):
                    in_degree[neighbor] -= 1
                    if in_degree[neighbor] == 0:
                        queue.append(neighbor)

            levels.append(current_level)

        return levels
