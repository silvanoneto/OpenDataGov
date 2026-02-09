"""MLflow integration components for Kubeflow Pipelines."""

from __future__ import annotations

from kfp import dsl


@dsl.component(
    base_image="python:3.11-slim",
    packages_to_install=["mlflow>=2.10.0", "joblib>=1.3.0"],
)
def log_to_mlflow(
    model_path: str,
    metrics: dict,
    experiment_name: str,
    run_name: str | None = None,
    params: dict | None = None,
    mlflow_tracking_uri: str = "http://mlflow:5000",
) -> tuple[str, str, str]:
    """Log model and metrics to MLflow.

    Args:
        model_path: Path to trained model artifact
        metrics: Performance metrics dict
        experiment_name: MLflow experiment name
        run_name: Optional run name
        params: Optional hyperparameters to log
        mlflow_tracking_uri: MLflow tracking server URL

    Returns:
        tuple containing:
        - run_id (str): MLflow run ID
        - model_uri (str): MLflow model URI
        - experiment_id (str): MLflow experiment ID

    Example:
        >>> log_task = log_to_mlflow(
        ...     model_path=train_task.outputs['model'],
        ...     metrics=train_task.outputs['metrics'],
        ...     experiment_name="customer-churn"
        ... )
    """

    import joblib
    import mlflow

    # Configure MLflow
    mlflow.set_tracking_uri(mlflow_tracking_uri)
    mlflow.set_experiment(experiment_name)

    print(f"MLflow Tracking URI: {mlflow_tracking_uri}")
    print(f"Experiment: {experiment_name}")

    # Start run
    with mlflow.start_run(run_name=run_name) as run:
        # Log parameters
        if params:
            mlflow.log_params(params)
            print(f"Logged parameters: {params}")

        # Log metrics
        mlflow.log_metrics(metrics)
        print(f"Logged metrics: {metrics}")

        # Load and log model
        model = joblib.load(model_path)
        mlflow.sklearn.log_model(model, "model")

        # Get run info
        run_id = run.info.run_id
        experiment_id = run.info.experiment_id
        model_uri = f"runs:/{run_id}/model"

        print("\n✓ MLflow Run:")
        print(f"  Run ID: {run_id}")
        print(f"  Experiment ID: {experiment_id}")
        print(f"  Model URI: {model_uri}")

    return run_id, model_uri, experiment_id


@dsl.component(
    base_image="python:3.11-slim",
    packages_to_install=["mlflow>=2.10.0"],
)
def register_model(
    model_uri: str,
    model_name: str,
    mlflow_tracking_uri: str = "http://mlflow:5000",
) -> tuple[str, int]:
    """Register model in MLflow Model Registry.

    Args:
        model_uri: MLflow model URI (from log_to_mlflow)
        model_name: Name to register model under
        mlflow_tracking_uri: MLflow tracking server URL

    Returns:
        tuple containing:
        - model_name (str): Registered model name
        - version (int): Model version number

    Example:
        >>> register_task = register_model(
        ...     model_uri=log_task.outputs['model_uri'],
        ...     model_name="customer-churn"
        ... )
    """
    import mlflow
    from mlflow.tracking import MlflowClient

    mlflow.set_tracking_uri(mlflow_tracking_uri)
    MlflowClient()

    print(f"Registering model: {model_name}")
    print(f"Model URI: {model_uri}")

    # Register model
    model_details = mlflow.register_model(model_uri, model_name)

    print("\n✓ Model registered:")
    print(f"  Name: {model_details.name}")
    print(f"  Version: {model_details.version}")

    return model_details.name, int(model_details.version)


@dsl.component(
    base_image="python:3.11-slim",
    packages_to_install=["mlflow>=2.10.0"],
)
def transition_model_stage(
    model_name: str,
    version: int,
    stage: str = "Staging",
    archive_existing: bool = True,
    mlflow_tracking_uri: str = "http://mlflow:5000",
) -> str:
    """Transition model to a specific stage (Dev profile only, no governance).

    For Medium/Large profiles, use request_governance_approval instead.

    Args:
        model_name: Model name
        version: Model version
        stage: Target stage (None, Staging, Production, Archived)
        archive_existing: Archive existing models in target stage
        mlflow_tracking_uri: MLflow tracking server URL

    Returns:
        str: New stage

    Example:
        >>> # Dev profile: Direct transition (no approval)
        >>> transition_task = transition_model_stage(
        ...     model_name="customer-churn",
        ...     version=1,
        ...     stage="Staging"
        ... )
    """
    import mlflow
    from mlflow.tracking import MlflowClient

    mlflow.set_tracking_uri(mlflow_tracking_uri)
    client = MlflowClient()

    print(f"Transitioning model {model_name} v{version} to {stage}")

    # Transition stage
    client.transition_model_version_stage(
        name=model_name,
        version=version,
        stage=stage,
        archive_existing_versions=archive_existing,
    )

    print(f"✓ Model transitioned to {stage}")

    return stage


@dsl.component(
    base_image="python:3.11-slim",
    packages_to_install=["mlflow>=2.10.0"],
)
def load_model_from_registry(
    model_name: str,
    stage: str = "Production",
    mlflow_tracking_uri: str = "http://mlflow:5000",
) -> str:
    """Load model from MLflow registry for inference.

    Args:
        model_name: Model name
        stage: Model stage (Staging, Production)
        mlflow_tracking_uri: MLflow tracking server URL

    Returns:
        str: Model URI

    Example:
        >>> model_uri = load_model_from_registry(
        ...     model_name="customer-churn",
        ...     stage="Production"
        ... )
    """
    import mlflow

    mlflow.set_tracking_uri(mlflow_tracking_uri)

    model_uri = f"models:/{model_name}/{stage}"

    print(f"Loading model: {model_uri}")

    # Verify model exists
    model = mlflow.sklearn.load_model(model_uri)

    print("✓ Model loaded successfully")
    print(f"  Model type: {type(model).__name__}")

    return model_uri
