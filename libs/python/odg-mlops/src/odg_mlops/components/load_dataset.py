"""Dataset loading components for Kubeflow Pipelines.

Loads curated data from OpenDataGov medallion lakehouse layers.
"""

from __future__ import annotations

from kfp import dsl
from kfp.dsl import Dataset, Output


@dsl.component(
    base_image="python:3.11-slim",
    packages_to_install=["pandas>=2.0.0", "pyarrow>=14.0.0", "boto3>=1.28.0"],
)
def load_gold_dataset(
    dataset_id: str,
    output_data: Output[Dataset],
    minio_endpoint: str = "minio:9000",
    bucket: str = "lakehouse",
) -> str:
    """Load curated dataset from Gold layer (medallion lakehouse).

    Gold layer datasets are curated, governed, and meet DQ score >= 0.95.
    This is the recommended source for ML training.

    Args:
        dataset_id: Dataset identifier (e.g., "gold/finance/revenue")
        minio_endpoint: MinIO endpoint URL
        bucket: S3 bucket name
        output_data: Output dataset artifact

    Returns:
        str: Path to loaded dataset

    Example:
        >>> load_task = load_gold_dataset(
        ...     dataset_id="gold/customer/churn"
        ... )
        >>> train_task = train_sklearn_model(
        ...     data_path=load_task.output
        ... )
    """
    from pathlib import Path

    import boto3
    import pandas as pd

    # Configure S3 client for MinIO
    s3_client = boto3.client(
        "s3",
        endpoint_url=f"http://{minio_endpoint}",
        aws_access_key_id="minioadmin",  # TODO: Use Vault secrets
        aws_secret_access_key="minioadmin",
        region_name="us-east-1",
    )

    # Parse dataset path
    # Format: "gold/finance/revenue" -> s3://lakehouse/gold/finance/revenue.parquet
    s3_key = f"{dataset_id}.parquet"

    print(f"Loading dataset from S3: s3://{bucket}/{s3_key}")

    # Download from MinIO
    local_path = Path("/tmp/dataset.parquet")
    s3_client.download_file(bucket, s3_key, str(local_path))

    # Read parquet file
    df = pd.read_parquet(local_path)

    print(f"Loaded dataset: {df.shape[0]} rows, {df.shape[1]} columns")
    print(f"Columns: {list(df.columns)}")
    print(f"\nFirst 5 rows:\n{df.head()}")
    print(f"\nDataset info:\n{df.info()}")

    # Save to output artifact
    output_path = Path(output_data.path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(output_path)

    return str(output_path)


@dsl.component(
    base_image="python:3.11-slim",
    packages_to_install=["pandas>=2.0.0", "pyarrow>=14.0.0"],
)
def load_platinum_dataset(
    dataset_id: str,
    output_data: Output[Dataset],
    minio_endpoint: str = "minio:9000",
    bucket: str = "lakehouse",
) -> str:
    """Load semantically enriched dataset from Platinum layer.

    Platinum layer includes:
    - Semantic annotations
    - Business glossary terms
    - Lineage metadata
    - Privacy classifications

    Args:
        dataset_id: Dataset identifier (e.g., "platinum/customer/360")
        minio_endpoint: MinIO endpoint URL
        bucket: S3 bucket name
        output_data: Output dataset artifact

    Returns:
        str: Path to loaded dataset
    """
    from pathlib import Path

    import boto3
    import pandas as pd

    s3_client = boto3.client(
        "s3",
        endpoint_url=f"http://{minio_endpoint}",
        aws_access_key_id="minioadmin",
        aws_secret_access_key="minioadmin",
        region_name="us-east-1",
    )

    s3_key = f"{dataset_id}.parquet"
    print(f"Loading Platinum dataset: s3://{bucket}/{s3_key}")

    local_path = Path("/tmp/platinum_dataset.parquet")
    s3_client.download_file(bucket, s3_key, str(local_path))

    df = pd.read_parquet(local_path)

    print(f"✓ Loaded Platinum dataset: {df.shape[0]} rows, {df.shape[1]} columns")

    output_path = Path(output_data.path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(output_path)

    return str(output_path)


@dsl.component(
    base_image="python:3.11-slim",
    packages_to_install=["pandas>=2.0.0"],
)
def split_train_test(
    data_path: str,
    train_output: Output[Dataset],
    test_output: Output[Dataset],
    test_size: float = 0.2,
    random_state: int = 42,
) -> tuple[str, str]:
    """Split dataset into train and test sets.

    Args:
        data_path: Path to input dataset
        test_size: Proportion of data for test set (default: 0.2)
        random_state: Random seed for reproducibility
        train_output: Output train dataset
        test_output: Output test dataset

    Returns:
        tuple[str, str]: Paths to train and test datasets
    """
    from pathlib import Path

    import pandas as pd
    from sklearn.model_selection import train_test_split

    # Load dataset
    df = pd.read_parquet(data_path)
    print(f"Total samples: {len(df)}")

    # Split
    train_df, test_df = train_test_split(df, test_size=test_size, random_state=random_state)

    print(f"Train samples: {len(train_df)} ({len(train_df) / len(df) * 100:.1f}%)")
    print(f"Test samples: {len(test_df)} ({len(test_df) / len(df) * 100:.1f}%)")

    # Save splits
    train_path = Path(train_output.path)
    test_path = Path(test_output.path)

    train_path.parent.mkdir(parents=True, exist_ok=True)
    test_path.parent.mkdir(parents=True, exist_ok=True)

    train_df.to_parquet(train_path)
    test_df.to_parquet(test_path)

    return str(train_path), str(test_path)
