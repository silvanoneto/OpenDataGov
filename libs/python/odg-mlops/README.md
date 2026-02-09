# ODG MLOps - Pipeline Components

Kubeflow Pipelines components for OpenDataGov MLOps workflows with integrated governance and quality gates.

## Features

- **Quality Gate Integration**: Validate data quality before training (Gold layer >= 0.95)
- **Lakehouse Integration**: Load data from medallion layers (Bronze/Silver/Gold/Platinum)
- **MLflow Integration**: Automatic experiment tracking and model registration
- **Governance Approval**: Request B-Swarm approval for model promotion
- **GPU Support**: Training components with GPU acceleration

## Installation

```bash
pip install odg-mlops
```

## Usage

### Build a Training Pipeline

```python
from kfp import dsl
from odg_mlops.components import (
    validate_training_data,
    load_gold_dataset,
    train_sklearn_model,
    log_to_mlflow,
    request_governance_approval
)

@dsl.pipeline(name='customer-churn-training')
def training_pipeline(
    dataset_id: str,
    model_name: str,
    experiment_name: str
):
    # Step 1: Validate DQ score
    validate_task = validate_training_data(
        dataset_id=dataset_id,
        min_dq_score=0.95
    )

    # Step 2: Load Gold layer data
    load_task = load_gold_dataset(
        dataset_id=dataset_id
    ).after(validate_task)

    # Step 3: Train model (GPU-enabled)
    train_task = train_sklearn_model(
        data=load_task.output,
        model_name=model_name,
        hyperparameters={'alpha': 0.5, 'max_depth': 10}
    ).set_gpu_limit(1)

    # Step 4: Log to MLflow
    log_task = log_to_mlflow(
        model=train_task.outputs['model'],
        metrics=train_task.outputs['metrics'],
        experiment_name=experiment_name
    )

    # Step 5: Request approval if f1 > 0.8
    with dsl.Condition(train_task.outputs['f1_score'] > 0.8):
        request_governance_approval(
            model_name=model_name,
            model_version=log_task.outputs['version']
        )
```

## Components

### validate_training_data

Validates that dataset meets minimum DQ score threshold.

**Parameters**:

- `dataset_id` (str): Dataset identifier
- `min_dq_score` (float): Minimum DQ score (default: 0.95)

**Outputs**:

- `validation_passed` (bool): Whether validation passed

### load_gold_dataset

Loads curated data from Gold layer (medallion lakehouse).

**Parameters**:

- `dataset_id` (str): Dataset identifier
- `format` (str): Data format (parquet, csv, etc.)

**Outputs**:

- `data_path` (str): Path to loaded data

### train_sklearn_model

Trains a scikit-learn model with configurable hyperparameters.

**Parameters**:

- `data_path` (str): Path to training data
- `model_name` (str): Model name
- `hyperparameters` (dict): Model hyperparameters
- `test_size` (float): Train/test split ratio

**Outputs**:

- `model_path` (str): Path to trained model
- `metrics` (dict): Performance metrics
- `f1_score` (float): F1 score

### log_to_mlflow

Logs model and metrics to MLflow.

**Parameters**:

- `model_path` (str): Path to model artifact
- `metrics` (dict): Performance metrics
- `experiment_name` (str): MLflow experiment name

**Outputs**:

- `run_id` (str): MLflow run ID
- `model_uri` (str): MLflow model URI
- `version` (int): Registered model version

### request_governance_approval

Creates B-Swarm governance decision for model promotion.

**Parameters**:

- `model_name` (str): Model name
- `model_version` (int): Model version
- `justification` (str): Promotion justification

**Outputs**:

- `decision_id` (str): Governance decision ID
- `approval_required` (bool): Whether approval is required

## Development

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black src/ tests/

# Lint
ruff check src/ tests/

# Type check
mypy src/
```

## License

Apache-2.0
