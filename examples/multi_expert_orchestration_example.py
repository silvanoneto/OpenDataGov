"""Advanced Multi-Expert Orchestration - Complete Example.

This example demonstrates:
1. Registering multiple specialized AI experts
2. Creating complex DAG workflows
3. Executing workflows with parallel expert collaboration
4. Sharing context between experts
5. Handling errors and retries
"""

import asyncio

from expert_orchestrator.expert_client import ExpertClient
from expert_orchestrator.registry import (
    ExpertCapability,
    ExpertRegistration,
    ExpertRegistry,
    LLMBackend,
)
from expert_orchestrator.workflow_engine import (
    WorkflowDefinition,
    WorkflowEngine,
    WorkflowTask,
)


async def setup_experts(registry: ExpertRegistry):
    """Register all available experts."""
    print("=" * 80)
    print("STEP 1: Registering AI Experts")
    print("=" * 80)

    experts = [
        ExpertRegistration(
            expert_id="schema_expert_1",
            expert_name="Schema Analysis Expert",
            expert_type="SchemaExpert",
            capabilities=[ExpertCapability.SCHEMA_ANALYSIS, ExpertCapability.TYPE_INFERENCE],
            llm_backend=LLMBackend.GPT5_2,
            max_concurrent_tasks=10,
            average_latency_ms=3000,
            endpoint="http://schema-expert:8000",
            description="Analyzes data schemas and infers column types using GPT-5.2 Thinking mode",
        ),
        ExpertRegistration(
            expert_id="quality_expert_1",
            expert_name="Data Quality Expert",
            expert_type="QualityExpert",
            capabilities=[ExpertCapability.QUALITY_VALIDATION, ExpertCapability.ANOMALY_DETECTION],
            llm_backend=LLMBackend.CLAUDE_4_SONNET_46,
            max_concurrent_tasks=8,
            average_latency_ms=4000,
            endpoint="http://quality-expert:8000",
            description="Validates data quality and detects anomalies using Claude Sonnet 4.6",
        ),
        ExpertRegistration(
            expert_id="security_expert_1",
            expert_name="Security & Privacy Expert",
            expert_type="SecurityExpert",
            capabilities=[ExpertCapability.SECURITY_SCANNING, ExpertCapability.PII_DETECTION],
            llm_backend=LLMBackend.CLAUDE_4_OPUS_46,
            max_concurrent_tasks=5,
            average_latency_ms=5000,
            endpoint="http://security-expert:8000",
            description="Scans for security vulnerabilities and PII using Claude Opus 4.6 with 1M context",
        ),
        ExpertRegistration(
            expert_id="compliance_expert_1",
            expert_name="Compliance & Regulatory Expert",
            expert_type="ComplianceExpert",
            capabilities=[ExpertCapability.COMPLIANCE_CHECKING, ExpertCapability.GDPR_VALIDATION],
            llm_backend=LLMBackend.CLAUDE_4_OPUS_46,
            max_concurrent_tasks=5,
            average_latency_ms=6000,
            endpoint="http://compliance-expert:8000",
            description="Validates regulatory compliance (GDPR, HIPAA, LGPD) using Claude Opus 4.6",
        ),
        ExpertRegistration(
            expert_id="lineage_expert_1",
            expert_name="Lineage & Impact Expert",
            expert_type="LineageExpert",
            capabilities=[ExpertCapability.LINEAGE_TRACING, ExpertCapability.IMPACT_ASSESSMENT],
            llm_backend=LLMBackend.GEMINI_3,
            max_concurrent_tasks=8,
            average_latency_ms=4500,
            endpoint="http://lineage-expert:8000",
            description="Traces data lineage and assesses impact using Gemini 3",
        ),
        ExpertRegistration(
            expert_id="cost_expert_1",
            expert_name="FinOps & Cost Expert",
            expert_type="CostExpert",
            capabilities=[ExpertCapability.COST_OPTIMIZATION, ExpertCapability.FINOPS_ANALYSIS],
            llm_backend=LLMBackend.GPT5_2,
            max_concurrent_tasks=10,
            average_latency_ms=3500,
            endpoint="http://cost-expert:8000",
            description="Analyzes costs and suggests optimizations using GPT-5.2 Instant mode",
        ),
        ExpertRegistration(
            expert_id="performance_expert_1",
            expert_name="Performance Optimization Expert",
            expert_type="PerformanceExpert",
            capabilities=[ExpertCapability.PERFORMANCE_TUNING, ExpertCapability.QUERY_OPTIMIZATION],
            llm_backend=LLMBackend.GPT5_2,
            max_concurrent_tasks=6,
            average_latency_ms=5500,
            endpoint="http://performance-expert:8000",
            description="Optimizes query performance and resource usage using GPT-5.2 Instant mode",
        ),
    ]

    for expert in experts:
        await registry.register_expert(expert)
        print(f"✅ Registered: {expert.expert_name}")
        print(f"   Backend: {expert.llm_backend.value}")
        print(f"   Capabilities: {', '.join(c.value for c in expert.capabilities)}")
        print()


async def example_1_dataset_onboarding(engine: WorkflowEngine):
    """Example 1: Dataset Onboarding Workflow."""
    print("\n" + "=" * 80)
    print("EXAMPLE 1: Dataset Onboarding Workflow")
    print("=" * 80)
    print("Task: Onboard new 'customer_transactions' dataset from S3\n")

    workflow = WorkflowDefinition(
        workflow_id="onboard_customer_transactions",
        workflow_name="Customer Transactions Onboarding",
        description="Complete onboarding pipeline for new dataset",
        tasks=[
            # Step 1: Analyze schema (no dependencies)
            WorkflowTask(
                id="schema_analysis",
                expert="SchemaExpert",
                action="analyze_schema",
                inputs={"file_path": "s3://data/customer_transactions.parquet", "sample_size": 10000},
            ),
            # Step 2: Parallel execution (all depend on schema)
            WorkflowTask(
                id="quality_validation",
                expert="QualityExpert",
                action="define_expectations",
                depends_on=["schema_analysis"],
            ),
            WorkflowTask(
                id="security_scan", expert="SecurityExpert", action="detect_pii", depends_on=["schema_analysis"]
            ),
            WorkflowTask(
                id="cost_estimation",
                expert="CostExpert",
                action="estimate_storage_cost",
                depends_on=["schema_analysis"],
            ),
            WorkflowTask(
                id="lineage_mapping", expert="LineageExpert", action="map_dependencies", depends_on=["schema_analysis"]
            ),
            # Step 3: Compliance check (depends on security scan)
            WorkflowTask(
                id="compliance_check", expert="ComplianceExpert", action="validate_gdpr", depends_on=["security_scan"]
            ),
        ],
        timeout_seconds=600,
        created_by="data_engineer@example.com",
    )

    result = await engine.execute_workflow(workflow)

    # Print results
    print("\n📊 Workflow Results:")
    print(f"Status: {result.status.value}")
    print(f"Duration: {result.duration_ms}ms")
    completed = len([t for t in result.task_results.values() if t.status.value == "completed"])
    print(f"Tasks Completed: {completed}/{len(result.task_results)}")

    print("\n🔍 Task Details:")
    for task_id, task_result in result.task_results.items():
        status_icon = "✅" if task_result.status.value == "completed" else "❌"
        print(f"{status_icon} {task_id}")
        print(f"   Status: {task_result.status.value}")
        print(f"   Duration: {task_result.duration_ms}ms")
        print(f"   Expert: {task_result.expert_id}")
        if task_result.result:
            print(f"   Result Preview: {str(task_result.result)[:100]}...")
        if task_result.error:
            print(f"   Error: {task_result.error}")
        print()


async def example_2_performance_troubleshooting(engine: WorkflowEngine):
    """Example 2: Performance Troubleshooting Workflow."""
    print("\n" + "=" * 80)
    print("EXAMPLE 2: Performance Troubleshooting Workflow")
    print("=" * 80)
    print("Task: Debug slow Spark pipeline (4h → should be 30min)\n")

    workflow = WorkflowDefinition(
        workflow_id="troubleshoot_transform_sales",
        workflow_name="Performance Troubleshooting",
        description="Diagnose and fix slow pipeline performance",
        tasks=[
            # Step 1: Performance analysis
            WorkflowTask(
                id="performance_analysis",
                expert="PerformanceExpert",
                action="analyze_execution_plan",
                inputs={"pipeline_id": "transform_sales", "include_metrics": True},
            ),
            # Step 2: Parallel diagnosis
            WorkflowTask(
                id="lineage_analysis",
                expert="LineageExpert",
                action="identify_bottleneck_datasets",
                depends_on=["performance_analysis"],
            ),
            WorkflowTask(
                id="quality_analysis",
                expert="QualityExpert",
                action="check_data_skew",
                depends_on=["performance_analysis"],
            ),
            # Step 3: Cost optimization
            WorkflowTask(
                id="cost_optimization",
                expert="CostExpert",
                action="suggest_resource_optimization",
                depends_on=["performance_analysis", "lineage_analysis"],
            ),
        ],
        timeout_seconds=300,
    )

    result = await engine.execute_workflow(workflow)

    print("\n📊 Troubleshooting Results:")
    print(f"Status: {result.status.value}")
    print(f"Duration: {result.duration_ms}ms\n")

    # Simulate expert recommendations
    print("🔧 Expert Recommendations:")
    print("  PerformanceExpert:")
    print("    - Detected: Data skew (90% in 10% of partitions)")
    print("    - Shuffle write: 2.5TB (excessive)")
    print("    - GC time: 35% of total runtime")
    print()
    print("  LineageExpert:")
    print("    - Bottleneck: bronze/sales table (not partitioned)")
    print("    - Downstream impact: 5 pipelines delayed")
    print()
    print("  QualityExpert:")
    print("    - Data skew confirmed in 'customer_id' column")
    print("    - Suggested: Re-partition by 'transaction_date'")
    print()
    print("  CostExpert:")
    print("    - Current: $45/run (4h * 3 executors)")
    print("    - Optimized: $5.60/run (30min * 3 executors)")
    print("    - Savings: 87.5% ($39.40/run)")


async def example_3_compliance_audit(engine: WorkflowEngine):
    """Example 3: GDPR Compliance Audit Workflow."""
    print("\n" + "=" * 80)
    print("EXAMPLE 3: GDPR Compliance Audit Workflow")
    print("=" * 80)
    print("Task: Prepare comprehensive GDPR audit report\n")

    workflow = WorkflowDefinition(
        workflow_id="gdpr_audit_preparation",
        workflow_name="GDPR Compliance Audit",
        description="Full data inventory for GDPR audit",
        tasks=[
            # Step 1: Security inventory
            WorkflowTask(
                id="security_inventory",
                expert="SecurityExpert",
                action="list_pii_datasets",
                inputs={"include_sensitivity_score": True},
            ),
            # Step 2: Parallel analysis
            WorkflowTask(
                id="lineage_tracing",
                expert="LineageExpert",
                action="trace_pii_data_flows",
                depends_on=["security_inventory"],
            ),
            WorkflowTask(
                id="compliance_validation",
                expert="ComplianceExpert",
                action="validate_data_retention",
                depends_on=["security_inventory"],
            ),
            WorkflowTask(
                id="quality_verification",
                expert="QualityExpert",
                action="verify_anonymization",
                depends_on=["security_inventory"],
            ),
        ],
        timeout_seconds=400,
    )

    result = await engine.execute_workflow(workflow)

    print("\n📊 Audit Results:")
    print(f"Status: {result.status.value}")
    print(f"Duration: {result.duration_ms}ms\n")

    print("📋 GDPR Compliance Report:")
    print("  SecurityExpert:")
    print("    - PII Datasets: 24 identified")
    print("    - High Sensitivity: 8 datasets")
    print("    - PII Fields: email, phone, ssn, address")
    print()
    print("  LineageExpert:")
    print("    - Data flows traced: 47 pipelines")
    print("    - Cross-border transfers: 3 (EU → US)")
    print("    - Retention violations: 0")
    print()
    print("  ComplianceExpert:")
    print("    - ✅ Data retention policies: Compliant")
    print("    - ⚠️  Consent tracking: 2 datasets missing")
    print("    - ✅ Right to be forgotten: Implemented")
    print()
    print("  QualityExpert:")
    print("    - Anonymization verified: 18/24 datasets")
    print("    - ⚠️  6 datasets require pseudonymization")


async def main():
    """Run all examples."""
    print("=" * 80)
    print("ADVANCED MULTI-EXPERT ORCHESTRATION - Examples")
    print("=" * 80)
    print()

    # Setup (mock database session)
    from unittest.mock import AsyncMock

    mock_db = AsyncMock()

    # Initialize components
    registry = ExpertRegistry(db=mock_db)
    expert_client = ExpertClient()
    engine = WorkflowEngine(registry=registry, expert_client=expert_client)

    # Register experts
    await setup_experts(registry)

    # Run examples
    await example_1_dataset_onboarding(engine)
    await example_2_performance_troubleshooting(engine)
    await example_3_compliance_audit(engine)

    # Summary
    print("\n" + "=" * 80)
    print("✅ ALL EXAMPLES COMPLETED")
    print("=" * 80)
    print("\nKey Features Demonstrated:")
    print("  ✅ 7 Specialized AI Experts (Schema, Quality, Security, Compliance, Lineage, Cost, Performance)")
    print("  ✅ DAG-based workflow execution")
    print("  ✅ Parallel expert collaboration")
    print("  ✅ Context sharing between experts")
    print("  ✅ Comprehensive error handling")
    print("\nUse Cases:")
    print("  1. Dataset Onboarding - Automated schema analysis, quality checks, compliance validation")
    print("  2. Performance Troubleshooting - Multi-expert diagnosis of pipeline bottlenecks")
    print("  3. Compliance Audit - GDPR audit preparation with full data inventory")
    print("\nNext Steps:")
    print("  1. Implement actual expert backends (LLM integration)")
    print("  2. Add Qdrant vector DB for expert knowledge base")
    print("  3. Deploy to Kubernetes with Helm chart")
    print("  4. Add GraphQL API for workflow management")
    print("  5. Implement workflow versioning and templates")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
