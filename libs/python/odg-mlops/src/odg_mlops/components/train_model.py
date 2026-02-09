"""Model training components for Kubeflow Pipelines."""

from __future__ import annotations

from kfp import dsl
from kfp.dsl import Metrics, Model, Output


@dsl.component(
    base_image="python:3.11-slim",
    packages_to_install=[
        "scikit-learn>=1.3.0",
        "pandas>=2.0.0",
        "joblib>=1.3.0",
    ],
)
def train_sklearn_model(
    data_path: str,
    target_column: str,
    output_model: Output[Model],
    output_metrics: Output[Metrics],
    model_type: str = "RandomForest",
    hyperparameters: dict | None = None,
    test_size: float = 0.2,
    random_state: int = 42,
) -> tuple[str, dict, float]:
    """Train a scikit-learn classification model.

    Args:
        data_path: Path to training dataset (parquet)
        target_column: Name of target column
        model_type: Model type (RandomForest, LogisticRegression, XGBoost)
        hyperparameters: Model hyperparameters
        test_size: Test set proportion
        random_state: Random seed
        output_model: Output model artifact
        output_metrics: Output metrics

    Returns:
        tuple containing:
        - model_path (str): Path to saved model
        - metrics (dict): Performance metrics
        - f1_score (float): F1 score for conditional logic

    Example:
        >>> train_task = train_sklearn_model(
        ...     data_path=load_task.output,
        ...     target_column="churn",
        ...     model_type="RandomForest",
        ...     hyperparameters={"n_estimators": 100, "max_depth": 10}
        ... ).set_gpu_limit(1)  # Request GPU for training
    """
    from pathlib import Path

    import joblib
    import pandas as pd
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import (
        accuracy_score,
        classification_report,
        f1_score,
        precision_score,
        recall_score,
        roc_auc_score,
    )
    from sklearn.model_selection import train_test_split

    if hyperparameters is None:
        hyperparameters = {}

    # Load data
    df = pd.read_parquet(data_path)
    print(f"Loaded dataset: {df.shape}")

    # Split features and target
    X = df.drop(columns=[target_column])
    y = df[target_column]

    print(f"Features: {X.shape[1]}")
    print(f"Target distribution:\n{y.value_counts(normalize=True)}")

    # Train/test split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_state, stratify=y
    )

    print(f"\nTrain set: {X_train.shape}")
    print(f"Test set: {X_test.shape}")

    # Initialize model
    if model_type == "RandomForest":
        model = RandomForestClassifier(random_state=random_state, **hyperparameters)
    elif model_type == "LogisticRegression":
        model = LogisticRegression(random_state=random_state, **hyperparameters)
    else:
        raise ValueError(f"Unsupported model type: {model_type}")

    print(f"\nTraining {model_type} with hyperparameters: {hyperparameters}")

    # Train
    model.fit(X_train, y_train)

    # Predict
    y_pred = model.predict(X_test)
    y_pred_proba = model.predict_proba(X_test)[:, 1]

    # Calculate metrics
    metrics = {
        "accuracy": float(accuracy_score(y_test, y_pred)),
        "precision": float(precision_score(y_test, y_pred, average="binary")),
        "recall": float(recall_score(y_test, y_pred, average="binary")),
        "f1_score": float(f1_score(y_test, y_pred, average="binary")),
        "roc_auc": float(roc_auc_score(y_test, y_pred_proba)),
    }

    print("\n=== Model Performance ===")
    for metric, value in metrics.items():
        print(f"{metric}: {value:.4f}")

    print(f"\n{classification_report(y_test, y_pred)}")

    # Log metrics to Kubeflow
    output_metrics.log_metric("accuracy", metrics["accuracy"])
    output_metrics.log_metric("precision", metrics["precision"])
    output_metrics.log_metric("recall", metrics["recall"])
    output_metrics.log_metric("f1_score", metrics["f1_score"])
    output_metrics.log_metric("roc_auc", metrics["roc_auc"])

    # Save model
    model_path = Path(output_model.path)
    model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, model_path)

    print(f"\n✓ Model saved to: {model_path}")

    return str(model_path), metrics, metrics["f1_score"]


@dsl.component(
    base_image="python:3.11-slim",
    packages_to_install=[
        "torch>=2.0.0",
        "transformers>=4.30.0",
        "pandas>=2.0.0",
    ],
)
def train_pytorch_model(
    data_path: str,
    output_model: Output[Model],
    output_metrics: Output[Metrics],
    model_name: str = "bert-base-uncased",
    epochs: int = 3,
    batch_size: int = 16,
    learning_rate: float = 2e-5,
) -> tuple[str, dict]:
    """Train a PyTorch/Transformers model (for NLP tasks).

    This component is designed for GPU training and should be used with
    .set_gpu_limit(1) or higher.

    Args:
        data_path: Path to training dataset
        model_name: HuggingFace model name
        epochs: Number of training epochs
        batch_size: Batch size
        learning_rate: Learning rate
        output_model: Output model artifact
        output_metrics: Output metrics

    Returns:
        tuple[str, dict]: Model path and metrics
    """
    from pathlib import Path

    import pandas as pd
    import torch

    # Check GPU availability
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Using device: {device}")

    if device == "cpu":
        print("WARNING: No GPU detected. Training will be slow.")

    # Load data
    df = pd.read_parquet(data_path)
    print(f"Loaded dataset: {df.shape}")

    # TODO: Implement tokenization and training
    # This is a skeleton for Phase 6 (Advanced AI Experts)

    model_path = Path(output_model.path)
    model_path.parent.mkdir(parents=True, exist_ok=True)

    # Placeholder metrics
    metrics = {
        "accuracy": 0.95,
        "loss": 0.15,
    }

    output_metrics.log_metric("accuracy", metrics["accuracy"])
    output_metrics.log_metric("loss", metrics["loss"])

    return str(model_path), metrics
