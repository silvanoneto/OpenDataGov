# Plugin Development Guide

## Overview

OpenDataGov provides a comprehensive plugin architecture that allows you to extend the platform's capabilities without modifying core code. The system supports six types of plugins across different functional areas.

## Plugin Types

| Plugin Type            | Base Class      | Purpose                    | Examples                                   |
| ---------------------- | --------------- | -------------------------- | ------------------------------------------ |
| **Quality Checks**     | `BaseCheck`     | Data quality validation    | Completeness, Uniqueness, Freshness        |
| **Governance Rules**   | `BaseRule`      | Policy enforcement         | Classification rules, Retention policies   |
| **Catalog Connectors** | `BaseConnector` | Metadata extraction        | DataHub, Alation, Collibra                 |
| **Privacy Mechanisms** | `BasePrivacy`   | Data protection            | Differential Privacy, k-anonymity, Masking |
| **Storage Backends**   | `BaseStorage`   | Data storage               | MinIO, S3, Azure Blob, GCS                 |
| **AI Experts**         | `BaseExpert`    | AI-powered recommendations | Data Expert, Schema Expert                 |

## Quick Start

### 1. Create a Quality Check Plugin

```python
from odg_core.quality.base_check import BaseCheck, CheckResult, DAMADimension, Severity
from typing import Any
import pandas as pd

class FreshnessCheck(BaseCheck):
    """Check if data is fresh (recently updated)."""

    def __init__(self, max_age_hours: int = 24):
        self.max_age_hours = max_age_hours

    async def validate(self, data: Any) -> CheckResult:
        """Validate data freshness based on timestamp column."""
        if not isinstance(data, pd.DataFrame):
            return CheckResult(
                passed=False,
                score=0.0,
                failures=["Data must be a pandas DataFrame"],
                metadata={}
            )

        if "updated_at" not in data.columns:
            return CheckResult(
                passed=False,
                score=0.0,
                failures=["Missing 'updated_at' column"],
                metadata={}
            )

        # Calculate age of most recent record
        latest_update = pd.to_datetime(data["updated_at"]).max()
        age_hours = (pd.Timestamp.now() - latest_update).total_seconds() / 3600

        passed = age_hours <= self.max_age_hours
        score = max(0.0, 1.0 - (age_hours / (self.max_age_hours * 2)))

        return CheckResult(
            passed=passed,
            score=score,
            failures=[] if passed else [f"Data is {age_hours:.1f}h old (max: {self.max_age_hours}h)"],
            metadata={
                "latest_update": str(latest_update),
                "age_hours": age_hours,
                "threshold_hours": self.max_age_hours
            }
        )

    def get_dimension(self) -> DAMADimension:
        return DAMADimension.TIMELINESS

    def get_severity(self) -> Severity:
        return Severity.HIGH

    def get_name(self) -> str:
        return "Freshness Check"

    def get_description(self) -> str:
        return f"Validates data was updated within {self.max_age_hours} hours"
```

### 2. Register the Plugin

```python
from odg_core.plugins.registry import PluginRegistry

# Register your custom check
PluginRegistry.register_check("freshness", FreshnessCheck)

# Use it
check_class = PluginRegistry.get_check("freshness")
check = check_class(max_age_hours=12)

result = await check.validate(my_dataframe)
if not result.passed:
    print(f"Freshness check failed: {result.failures}")
```

## Base Classes Reference

### 1. BaseCheck - Quality Checks

**Purpose**: Validate data quality against specific dimensions (DAMA framework).

**Required Methods**:

```python
class BaseCheck(ABC):
    @abstractmethod
    async def validate(self, data: Any) -> CheckResult:
        """Validate the data and return results."""
        ...

    @abstractmethod
    def get_dimension(self) -> DAMADimension:
        """Return DAMA dimension (Completeness, Accuracy, etc.)."""
        ...

    @abstractmethod
    def get_severity(self) -> Severity:
        """Return severity level (LOW, MEDIUM, HIGH, CRITICAL)."""
        ...
```

**Example: Uniqueness Check**

```python
class UniquenessCheck(BaseCheck):
    def __init__(self, key_columns: list[str]):
        self.key_columns = key_columns

    async def validate(self, data: pd.DataFrame) -> CheckResult:
        duplicates = data[self.key_columns].duplicated().sum()
        total_rows = len(data)
        score = 1.0 - (duplicates / total_rows) if total_rows > 0 else 0.0

        return CheckResult(
            passed=duplicates == 0,
            score=score,
            failures=[f"Found {duplicates} duplicate rows"] if duplicates > 0 else [],
            metadata={"duplicates": duplicates, "total_rows": total_rows}
        )

    def get_dimension(self) -> DAMADimension:
        return DAMADimension.UNIQUENESS

    def get_severity(self) -> Severity:
        return Severity.CRITICAL
```

### 2. BaseRule - Governance Rules

**Purpose**: Implement business rules and policies for automated governance.

**Required Methods**:

```python
class BaseRule(ABC):
    @abstractmethod
    async def evaluate(self, context: dict[str, Any]) -> RuleEvaluation:
        """Evaluate rule against context."""
        ...

    @abstractmethod
    def get_conditions(self) -> list[str]:
        """Return list of conditions this rule checks."""
        ...

    @abstractmethod
    def get_actions(self) -> list[str]:
        """Return list of actions this rule can trigger."""
        ...
```

**Example: PII Classification Rule**

```python
from odg_core.governance.base_rule import BaseRule, RuleEvaluation

class PIIClassificationRule(BaseRule):
    """Automatically classify datasets containing PII."""

    PII_PATTERNS = [
        r'email', r'ssn', r'credit_card', r'phone',
        r'address', r'name', r'dob', r'passport'
    ]

    async def evaluate(self, context: dict[str, Any]) -> RuleEvaluation:
        column_names = context.get("column_names", [])

        # Check if any column name matches PII patterns
        has_pii = any(
            any(pattern in col.lower() for pattern in self.PII_PATTERNS)
            for col in column_names
        )

        if has_pii:
            return RuleEvaluation(
                matched=True,
                actions=["classify_as_sensitive", "require_masking"],
                conditions_met={
                    "contains_pii_columns": True,
                    "column_count": len(column_names)
                }
            )

        return RuleEvaluation(
            matched=False,
            actions=[],
            conditions_met={"contains_pii_columns": False}
        )

    def get_conditions(self) -> list[str]:
        return ["Column names match PII patterns"]

    def get_actions(self) -> list[str]:
        return ["classify_as_sensitive", "require_masking", "notify_data_owner"]
```

### 3. BaseConnector - Catalog Connectors

**Purpose**: Extract metadata from external systems using ETL pattern.

**Required Methods**:

```python
class BaseConnector(ABC):
    @abstractmethod
    async def extract(self) -> MetadataExtract:
        """Extract raw metadata from source system."""
        ...

    @abstractmethod
    async def transform(self, raw: MetadataExtract) -> list[DatasetMetadata]:
        """Transform raw data to standard format."""
        ...

    @abstractmethod
    async def load(self, metadata: list[DatasetMetadata]) -> None:
        """Load transformed metadata into OpenDataGov."""
        ...
```

**Example: PostgreSQL Connector**

```python
from odg_core.metadata.base_connector import BaseConnector, MetadataExtract, DatasetMetadata
import asyncpg

class PostgreSQLConnector(BaseConnector):
    def __init__(self, connection_string: str):
        self.connection_string = connection_string

    async def extract(self) -> MetadataExtract:
        """Extract table metadata from PostgreSQL."""
        conn = await asyncpg.connect(self.connection_string)

        # Get all tables
        tables = await conn.fetch("""
            SELECT table_schema, table_name, column_name, data_type
            FROM information_schema.columns
            WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
            ORDER BY table_schema, table_name, ordinal_position
        """)

        await conn.close()

        return MetadataExtract(
            datasets=[{"table": row} for row in tables],
            lineage=[],
            metadata={"source": "postgresql", "connection": self.connection_string}
        )

    async def transform(self, raw: MetadataExtract) -> list[DatasetMetadata]:
        """Transform to OpenDataGov format."""
        datasets = {}
        for item in raw.datasets:
            row = item["table"]
            table_id = f"{row['table_schema']}.{row['table_name']}"

            if table_id not in datasets:
                datasets[table_id] = DatasetMetadata(
                    id=table_id,
                    name=row['table_name'],
                    description=f"PostgreSQL table: {table_id}",
                    schema=row['table_schema'],
                    columns=[],
                    tags=["postgresql", row['table_schema']]
                )

            datasets[table_id].columns.append({
                "name": row['column_name'],
                "type": row['data_type']
            })

        return list(datasets.values())

    async def load(self, metadata: list[DatasetMetadata]) -> None:
        """Load into DataHub or OpenDataGov catalog."""
        # Implementation would send to DataHub API or internal catalog
        for dataset in metadata:
            print(f"Loading dataset: {dataset.id} with {len(dataset.columns)} columns")

    def get_connector_type(self) -> str:
        return "postgresql"
```

### 4. BasePrivacy - Privacy Mechanisms

**Purpose**: Apply privacy-preserving transformations to data.

**Required Methods**:

```python
class BasePrivacy(ABC):
    @abstractmethod
    async def apply(self, data: Any, config: PrivacyConfig) -> PrivacyResult:
        """Apply privacy mechanism to data."""
        ...

    @abstractmethod
    async def audit(self) -> dict[str, Any]:
        """Return audit trail of privacy budget usage."""
        ...

    @abstractmethod
    def get_mechanism_type(self) -> str:
        """Return mechanism type identifier."""
        ...
```

**Example: Column Masking**

```python
from odg_core.privacy.base_privacy import BasePrivacy, PrivacyConfig, PrivacyResult
import hashlib

class ColumnMaskingMechanism(BasePrivacy):
    """Mask sensitive columns with hash or redaction."""

    def __init__(self):
        self.masked_columns_count = 0

    async def apply(self, data: pd.DataFrame, config: PrivacyConfig) -> PrivacyResult:
        """Mask specified columns."""
        sensitive_columns = config.parameters.get("sensitive_columns", [])
        mask_type = config.parameters.get("mask_type", "hash")  # hash, redact, partial

        masked_data = data.copy()

        for col in sensitive_columns:
            if col not in data.columns:
                continue

            if mask_type == "hash":
                masked_data[col] = data[col].apply(
                    lambda x: hashlib.sha256(str(x).encode()).hexdigest()[:8]
                )
            elif mask_type == "redact":
                masked_data[col] = "***REDACTED***"
            elif mask_type == "partial":
                masked_data[col] = data[col].apply(
                    lambda x: str(x)[:2] + "****" if len(str(x)) > 2 else "****"
                )

            self.masked_columns_count += 1

        return PrivacyResult(
            transformed_data=masked_data,
            privacy_loss=0.0,  # No differential privacy budget consumed
            audit_metadata={
                "mechanism": "column_masking",
                "masked_columns": sensitive_columns,
                "mask_type": mask_type,
                "timestamp": pd.Timestamp.now().isoformat()
            },
            statistics={
                "columns_masked": len(sensitive_columns),
                "rows_affected": len(data)
            }
        )

    async def audit(self) -> dict[str, Any]:
        return {
            "total_columns_masked": self.masked_columns_count,
            "privacy_budget_consumed": 0.0
        }

    def get_mechanism_type(self) -> str:
        return "column_masking"
```

### 5. BaseStorage - Storage Backends

**Purpose**: Abstract storage operations for different backends.

**Required Methods**:

```python
class BaseStorage(ABC):
    @abstractmethod
    async def read(self, path: str) -> bytes:
        """Read data from storage."""
        ...

    @abstractmethod
    async def write(self, path: str, data: bytes) -> None:
        """Write data to storage."""
        ...

    @abstractmethod
    async def list(self, prefix: str = "") -> list[str]:
        """List objects with given prefix."""
        ...

    @abstractmethod
    async def delete(self, path: str) -> None:
        """Delete object from storage."""
        ...

    @abstractmethod
    def get_storage_type(self) -> str:
        """Return storage backend type."""
        ...
```

**Example: Local Filesystem Storage**

```python
from odg_core.storage.base_storage import BaseStorage, StorageMetadata
import aiofiles
import os
from pathlib import Path

class FilesystemStorage(BaseStorage):
    """Local filesystem storage backend."""

    def __init__(self, base_path: str):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    async def read(self, path: str) -> bytes:
        full_path = self.base_path / path
        if not full_path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        async with aiofiles.open(full_path, 'rb') as f:
            return await f.read()

    async def write(self, path: str, data: bytes) -> None:
        full_path = self.base_path / path
        full_path.parent.mkdir(parents=True, exist_ok=True)

        async with aiofiles.open(full_path, 'wb') as f:
            await f.write(data)

    async def list(self, prefix: str = "") -> list[str]:
        search_path = self.base_path / prefix
        if not search_path.exists():
            return []

        paths = []
        for root, dirs, files in os.walk(search_path):
            for file in files:
                rel_path = Path(root) / file
                paths.append(str(rel_path.relative_to(self.base_path)))
        return paths

    async def delete(self, path: str) -> None:
        full_path = self.base_path / path
        if not full_path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        full_path.unlink()

    def get_storage_type(self) -> str:
        return "filesystem"

    async def get_metadata(self, path: str) -> StorageMetadata:
        full_path = self.base_path / path
        stat = full_path.stat()

        return StorageMetadata(
            path=path,
            size_bytes=stat.st_size,
            last_modified=pd.Timestamp.fromtimestamp(stat.st_mtime).isoformat()
        )
```

### 6. BaseExpert - AI Experts

**Purpose**: Provide AI-powered recommendations and insights.

See existing `BaseExpert` in `libs/python/odg-core/src/odg_core/expert.py`.

## Plugin Registry

### Registration

```python
from odg_core.plugins.registry import PluginRegistry

# Register plugins
PluginRegistry.register_check("freshness", FreshnessCheck)
PluginRegistry.register_rule("pii_classification", PIIClassificationRule)
PluginRegistry.register_connector("postgresql", PostgreSQLConnector)
PluginRegistry.register_privacy("masking", ColumnMaskingMechanism)
PluginRegistry.register_storage("filesystem", FilesystemStorage)
```

### Discovery

```python
# List all available plugins
checks = PluginRegistry.list_checks()
print(f"Available checks: {list(checks.keys())}")

# Get specific plugin
check_class = PluginRegistry.get_check("freshness")
if check_class:
    check = check_class(max_age_hours=24)
```

### Statistics

```python
stats = PluginRegistry.get_stats()
print(f"Total plugins: {stats['total']}")
print(f"Checks: {stats['checks']}, Rules: {stats['rules']}")
```

## Best Practices

### 1. Configuration Management

Use Pydantic models for plugin configuration:

```python
from pydantic import BaseModel, Field

class FreshnessCheckConfig(BaseModel):
    max_age_hours: int = Field(default=24, ge=1, le=168)
    timestamp_column: str = "updated_at"

class FreshnessCheck(BaseCheck):
    def __init__(self, config: FreshnessCheckConfig):
        self.config = config
```

### 2. Error Handling

Provide clear error messages:

```python
async def validate(self, data: Any) -> CheckResult:
    if not isinstance(data, pd.DataFrame):
        return CheckResult(
            passed=False,
            score=0.0,
            failures=["Expected pandas DataFrame, got {type(data).__name__}"],
            metadata={"error": "type_mismatch"}
        )

    try:
        # Validation logic
        pass
    except Exception as e:
        return CheckResult(
            passed=False,
            score=0.0,
            failures=[f"Validation error: {str(e)}"],
            metadata={"error": "exception", "exception_type": type(e).__name__}
        )
```

### 3. Async Operations

Use async/await for I/O operations:

```python
async def extract(self) -> MetadataExtract:
    async with httpx.AsyncClient() as client:
        response = await client.get("https://api.example.com/metadata")
        data = response.json()
    return MetadataExtract(datasets=data["datasets"], ...)
```

### 4. Testing

Write comprehensive tests:

```python
import pytest
from odg_core.plugins.registry import PluginRegistry

@pytest.fixture
def sample_data():
    return pd.DataFrame({
        "id": [1, 2, 3],
        "updated_at": [
            pd.Timestamp.now() - pd.Timedelta(hours=1),
            pd.Timestamp.now() - pd.Timedelta(hours=48),
            pd.Timestamp.now()
        ]
    })

@pytest.mark.asyncio
async def test_freshness_check(sample_data):
    check = FreshnessCheck(max_age_hours=24)
    result = await check.validate(sample_data)

    assert not result.passed
    assert result.score < 1.0
    assert len(result.failures) > 0
```

### 5. Documentation

Document your plugin:

```python
class MyCustomCheck(BaseCheck):
    """Custom data quality check for specific business logic.

    This check validates that critical business rules are met:
    - Revenue values are positive
    - Transaction dates are within valid range
    - Customer IDs match expected format

    Args:
        min_revenue: Minimum acceptable revenue value
        date_range_days: Maximum age of transactions in days

    Example:
        >>> check = MyCustomCheck(min_revenue=100, date_range_days=30)
        >>> result = await check.validate(transactions_df)
        >>> print(f"Score: {result.score}")
    """
```

## Packaging & Distribution

### Create a Plugin Package

```
my-odg-plugin/
├── pyproject.toml
├── README.md
├── src/
│   └── my_odg_plugin/
│       ├── __init__.py
│       ├── checks.py
│       └── rules.py
└── tests/
    ├── test_checks.py
    └── test_rules.py
```

**pyproject.toml**:

```toml
[project]
name = "my-odg-plugin"
version = "0.1.0"
dependencies = ["odg-core>=0.1.0"]

[project.entry-points."odg.plugins"]
my_check = "my_odg_plugin.checks:MyCheck"
my_rule = "my_odg_plugin.rules:MyRule"
```

### Auto-Registration via Entry Points

```python
# OpenDataGov can auto-discover plugins via entry points
import importlib.metadata

def discover_plugins():
    for entry_point in importlib.metadata.entry_points().get("odg.plugins", []):
        plugin_class = entry_point.load()
        PluginRegistry.register_check(entry_point.name, plugin_class)
```

## Examples Repository

Complete plugin examples available at:

```
libs/python/odg-core/src/odg_core/quality/checks/     # Quality check examples
libs/python/odg-core/src/odg_core/governance/rules/   # Governance rule examples
libs/python/odg-core/src/odg_core/metadata/connectors/ # Connector examples
```

## Support

For plugin development questions:

- **Documentation**: [docs/PLUGINS.md](docs/PLUGINS.md)
- **Examples**: Check existing plugin implementations in `odg-core`
- **Issues**: [GitHub Issues](https://github.com/opendatagov/issues)
- **Community**: OpenDataGov Slack #plugin-development
