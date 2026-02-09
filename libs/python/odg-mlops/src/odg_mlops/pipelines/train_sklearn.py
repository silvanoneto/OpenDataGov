"""Complete training pipeline example for scikit-learn models.

This pipeline demonstrates:
1. Quality gate validation (DQ score >= 0.95)
2. Loading data from Gold layer
3. Training with GPU support
4. Logging to MLflow
5. Requesting governance approval for production promotion
"""

from __future__ import annotations

from kfp import dsl

from odg_mlops.components import (
    load_gold_dataset,
    log_to_mlflow,
    register_model,
    request_governance_approval,
    train_sklearn_model,
    validate_training_data,
)


@dsl.pipeline(
    name="customer-churn-training",
    description="Train customer churn prediction model with governance approval",
)
def training_pipeline(
    dataset_id: str = "gold/customer/churn",
    target_column: str = "churn",
    model_name: str = "customer-churn",
    experiment_name: str = "customer-churn-experiment",
    model_type: str = "RandomForest",
    min_dq_score: float = 0.95,
    f1_threshold: float = 0.8,
    hyperparameters: dict | None = None,
):
    """Complete training pipeline with quality gates and governance.

    Args:
        dataset_id: Dataset identifier (e.g., "gold/customer/churn")
        target_column: Name of target column in dataset
        model_name: Name for model registration
        experiment_name: MLflow experiment name
        model_type: Model type (RandomForest, LogisticRegression, etc.)
        min_dq_score: Minimum DQ score required (default: 0.95 for Gold layer)
        f1_threshold: Minimum F1 score to request production promotion
        hyperparameters: Model hyperparameters

    Pipeline Steps:
        1. Validate DQ score >= 0.95 (Quality Gate)
        2. Load data from Gold layer (Medallion Lakehouse)
        3. Train model with configurable hyperparameters
        4. Log model and metrics to MLflow
        5. Register model in MLflow registry
        6. If F1 > threshold: Request governance approval for production

    Example Usage:
        ```python
        from kfp import Client
        from odg_mlops.pipelines import training_pipeline

        client = Client(host="http://kubeflow-pipelines:8888")

        run = client.create_run_from_pipeline_func(
            training_pipeline,
            arguments={
                "dataset_id": "gold/finance/churn",
                "model_name": "churn-predictor",
                "hyperparameters": {
                    "n_estimators": 100,
                    "max_depth": 10,
                    "min_samples_split": 5
                },
                "f1_threshold": 0.85
            }
        )
        ```
    """
    if hyperparameters is None:
        hyperparameters = {
            "n_estimators": 100,
            "max_depth": 10,
            "min_samples_split": 2,
        }

    # Step 1: Quality Gate - Validate DQ score
    validate_task = validate_training_data(
        dataset_id=dataset_id,
        min_dq_score=min_dq_score,
    )
    validate_task.set_display_name("1. Validate Data Quality")

    # Step 2: Load curated data from Gold layer
    load_task = load_gold_dataset(dataset_id=dataset_id).after(validate_task)
    load_task.set_display_name("2. Load Gold Dataset")

    # Step 3: Train model (with GPU if available)
    train_task = train_sklearn_model(
        data_path=load_task.output,
        target_column=target_column,
        model_type=model_type,
        hyperparameters=hyperparameters,
    )
    train_task.set_display_name("3. Train Model")
    # Request GPU for training (medium/large profiles)
    train_task.set_gpu_limit(1)
    train_task.set_memory_limit("8Gi")
    train_task.set_cpu_limit("4")

    # Step 4: Log to MLflow
    log_task = log_to_mlflow(
        model_path=train_task.outputs["output_model"],
        metrics=train_task.outputs["metrics"],
        experiment_name=experiment_name,
        run_name=f"{model_name}-{dsl.PIPELINE_RUN_ID_PLACEHOLDER}",
        params=hyperparameters,
    )
    log_task.set_display_name("4. Log to MLflow")

    # Step 5: Register model in MLflow registry
    register_task = register_model(
        model_uri=log_task.outputs["model_uri"],
        model_name=model_name,
    )
    register_task.set_display_name("5. Register Model")

    # Step 6: Conditional governance approval
    # Only request approval if F1 score exceeds threshold
    with dsl.Condition(train_task.outputs["f1_score"] > f1_threshold):
        approval_task = request_governance_approval(
            model_name=model_name,
            model_version=register_task.outputs["version"],
            mlflow_run_id=log_task.outputs["run_id"],
            mlflow_model_uri=log_task.outputs["model_uri"],
            source_stage="staging",
            target_stage="production",
            justification=(
                f"Model achieves F1 score > {f1_threshold}. Ready for production deployment."
            ),
            performance_metrics=train_task.outputs["metrics"],
        )
        approval_task.set_display_name("6. Request Production Approval")


@dsl.pipeline(
    name="customer-churn-inference",
    description="Batch inference pipeline using production model",
)
def inference_pipeline(
    dataset_id: str = "gold/customer/features",
    model_name: str = "customer-churn",
    model_stage: str = "Production",
    output_path: str = "predictions/customer-churn",
):
    """Batch inference pipeline using production model from MLflow.

    Args:
        dataset_id: Input dataset identifier
        model_name: Model name in MLflow registry
        model_stage: Model stage (Production, Staging)
        output_path: Output path for predictions

    Example:
        ```python
        client.create_run_from_pipeline_func(
            inference_pipeline,
            arguments={
                "dataset_id": "gold/customer/features",
                "model_name": "churn-predictor",
                "output_path": "predictions/2026-02-08"
            }
        )
        ```
    """
    from odg_mlops.components.mlflow_integration import load_model_from_registry

    # Load data
    load_gold_dataset(dataset_id=dataset_id)

    # Load production model
    load_model_from_registry(
        model_name=model_name,
        stage=model_stage,
    )

    # TODO: Add inference component
    # predict_task = batch_predict(
    #     data=load_task.output,
    #     model_uri=load_model_task.output,
    #     output_path=output_path
    # )


@dsl.pipeline(
    name="model-retraining-on-drift",
    description="Automated retraining pipeline triggered by drift detection",
)
def retraining_pipeline(
    model_name: str = "customer-churn",
    drift_score: float = 0.85,
    dataset_id: str = "gold/customer/churn",
):
    """Automated retraining pipeline triggered by drift monitoring.

    This pipeline is typically invoked by the drift monitor service when
    significant data/concept drift is detected.

    Args:
        model_name: Name of model to retrain
        drift_score: Drift score that triggered retraining
        dataset_id: Dataset to use for retraining

    Example:
        # Triggered automatically by drift monitor
        # Or manually via API:
        ```python
        client.create_run_from_pipeline_func(
            retraining_pipeline,
            arguments={
                "model_name": "churn-predictor",
                "drift_score": 0.87,
                "dataset_id": "gold/customer/churn_latest"
            }
        )
        ```
    """
    # Step 1: Create governance decision for retraining
    # This requests approval from Data Scientist/Architect

    # Log drift event
    print(f"Drift detected for {model_name}: score={drift_score}")

    # Request approval to retrain
    # TODO: Implement retraining approval component
    # approval_task = request_retraining_approval(
    #     model_name=model_name,
    #     drift_score=drift_score,
    #     reason=f"Data drift detected (score: {drift_score})"
    # )

    # After approval, execute training pipeline
    # training_task = training_pipeline(
    #     dataset_id=dataset_id,
    #     model_name=model_name
    # ).after(approval_task)

    pass
