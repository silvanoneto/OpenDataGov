"""Load and validate data contract YAML files (ADR-051)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from odg_core.models import DataContract, DataContractSchema, SLADefinition


def load_contract(path: str | Path) -> DataContract:
    """Load a data contract from a YAML file.

    Raises:
        FileNotFoundError: If the contract file does not exist.
        ValueError: If the contract YAML is invalid.
    """
    file_path = Path(path)
    if not file_path.exists():
        msg = f"Contract file not found: {file_path}"
        raise FileNotFoundError(msg)

    with file_path.open() as f:
        raw: dict[str, Any] = yaml.safe_load(f)

    if not isinstance(raw, dict):
        msg = f"Contract file must be a YAML mapping: {file_path}"
        raise ValueError(msg)

    # Parse schema
    schema_raw = raw.get("schema", {})
    schema = DataContractSchema(**schema_raw) if schema_raw else DataContractSchema()

    # Parse SLA
    sla_raw = raw.get("sla", {})
    sla = SLADefinition(**sla_raw) if sla_raw else SLADefinition()

    return DataContract(
        name=raw.get("name", file_path.stem),
        dataset_id=raw["dataset_id"],
        domain_id=raw["domain_id"],
        owner_id=raw["owner_id"],
        schema_definition=schema,
        sla_definition=sla,
        jurisdiction=raw.get("jurisdiction"),
    )


def load_contracts_from_dir(directory: str | Path) -> list[DataContract]:
    """Load all data contracts from YAML files in a directory."""
    dir_path = Path(directory)
    contracts = []
    for file_path in sorted(dir_path.glob("*.yaml")):
        contracts.append(load_contract(file_path))
    return contracts
