"""Tests for odg_core.airflow.dag_versioning module."""

from __future__ import annotations

import hashlib
import json
from unittest.mock import MagicMock

from odg_core.airflow.dag_versioning import (
    VersionedDAG,
    VersionedDAGRunHook,
    on_dagrun_failure,
    on_dagrun_success,
)

# ──── helpers ───────────────────────────────────────────────────


def _make_task(task_id: str, task_type: str = "PythonOperator", upstream_ids: list[str] | None = None) -> MagicMock:
    """Create a mock Airflow task."""
    task = MagicMock()
    task.task_id = task_id
    task.__class__ = type(task_type, (), {})  # Give it a class with the right __name__
    task.__class__.__name__ = task_type
    task.upstream_task_ids = set(upstream_ids or [])
    return task


def _make_dag(
    dag_id: str = "transform_sales",
    tasks: list[MagicMock] | None = None,
    schedule_interval: str = "@daily",
) -> MagicMock:
    """Create a mock Airflow DAG."""
    dag = MagicMock()
    dag.dag_id = dag_id
    dag.tasks = tasks or []
    dag.schedule_interval = schedule_interval
    return dag


# ──── VersionedDAG.__init__ ─────────────────────────────────────


class TestVersionedDAGInit:
    """Tests for VersionedDAG initialization."""

    def test_init_stores_dag_and_commit(self) -> None:
        dag = _make_dag()
        versioned = VersionedDAG(dag, git_commit="abc123")

        assert versioned.dag is dag
        assert versioned.git_commit == "abc123"

    def test_init_computes_version_hash(self) -> None:
        dag = _make_dag(tasks=[_make_task("extract"), _make_task("load")])
        versioned = VersionedDAG(dag)

        assert versioned.version_hash is not None
        assert len(versioned.version_hash) == 12


# ──── _compute_version_hash ─────────────────────────────────────


class TestComputeVersionHash:
    """Tests for VersionedDAG._compute_version_hash."""

    def test_compute_version_hash_returns_12_chars(self) -> None:
        dag = _make_dag(tasks=[_make_task("t1")])
        versioned = VersionedDAG(dag)

        assert len(versioned.version_hash) == 12

    def test_compute_version_hash_deterministic(self) -> None:
        dag1 = _make_dag(
            dag_id="test_dag",
            tasks=[_make_task("extract"), _make_task("transform", upstream_ids=["extract"])],
            schedule_interval="@hourly",
        )
        dag2 = _make_dag(
            dag_id="test_dag",
            tasks=[_make_task("extract"), _make_task("transform", upstream_ids=["extract"])],
            schedule_interval="@hourly",
        )

        v1 = VersionedDAG(dag1)
        v2 = VersionedDAG(dag2)

        assert v1.version_hash == v2.version_hash

    def test_compute_version_hash_different_dags_different_hash(self) -> None:
        dag1 = _make_dag(dag_id="dag_a", tasks=[_make_task("t1")])
        dag2 = _make_dag(dag_id="dag_b", tasks=[_make_task("t1")])

        v1 = VersionedDAG(dag1)
        v2 = VersionedDAG(dag2)

        assert v1.version_hash != v2.version_hash

    def test_compute_version_hash_task_order_independent(self) -> None:
        # Tasks are sorted by task_id in _compute_version_hash, so order should not matter
        task_a = _make_task("alpha")
        task_b = _make_task("beta")

        dag_ab = _make_dag(dag_id="dag", tasks=[task_a, task_b])
        dag_ba = _make_dag(dag_id="dag", tasks=[task_b, task_a])

        v_ab = VersionedDAG(dag_ab)
        v_ba = VersionedDAG(dag_ba)

        assert v_ab.version_hash == v_ba.version_hash

    def test_compute_version_hash_matches_expected(self) -> None:
        task = _make_task("extract", task_type="BashOperator", upstream_ids=[])
        dag = _make_dag(dag_id="my_dag", tasks=[task], schedule_interval="@daily")

        versioned = VersionedDAG(dag)

        # Reproduce the expected hash manually
        dag_structure = {
            "dag_id": "my_dag",
            "tasks": sorted(
                [
                    {
                        "task_id": "extract",
                        "task_type": "BashOperator",
                        "upstream_task_ids": [],
                    }
                ],
                key=lambda x: str(x["task_id"]),
            ),
            "schedule_interval": "@daily",
        }
        dag_json = json.dumps(dag_structure, sort_keys=True)
        expected = hashlib.sha256(dag_json.encode()).hexdigest()[:12]

        assert versioned.version_hash == expected


# ──── register_version ──────────────────────────────────────────


class TestRegisterVersion:
    """Tests for VersionedDAG.register_version."""

    def test_register_version_returns_0_on_error(self) -> None:
        dag = _make_dag(tasks=[_make_task("t1")])
        versioned = VersionedDAG(dag)

        # Without a database, register_version should catch the exception and return 0
        result = versioned.register_version()
        assert result == 0


# ──── VersionedDAGRunHook._get_dag_version ──────────────────────


class TestGetDagVersion:
    """Tests for VersionedDAGRunHook._get_dag_version."""

    def test_get_dag_version_returns_0_on_error(self) -> None:
        # Without a database, _get_dag_version should catch the exception and return 0
        result = VersionedDAGRunHook._get_dag_version("test_dag", "abc123def456")
        assert result == 0


# ──── on_dagrun_success / on_dagrun_failure ─────────────────────


class TestDagRunCallbacks:
    """Tests for DAG run callback methods."""

    def test_on_dagrun_success_swallows_errors(self) -> None:
        # Passing an invalid context (missing required keys) should not raise
        VersionedDAGRunHook.on_dagrun_success({})

    def test_on_dagrun_failure_swallows_errors(self) -> None:
        # Passing an invalid context (missing required keys) should not raise
        VersionedDAGRunHook.on_dagrun_failure({})

    def test_exported_callbacks_are_static_methods(self) -> None:
        # on_dagrun_success and on_dagrun_failure are module-level aliases
        # for the static methods on VersionedDAGRunHook
        assert on_dagrun_success is VersionedDAGRunHook.on_dagrun_success
        assert on_dagrun_failure is VersionedDAGRunHook.on_dagrun_failure
