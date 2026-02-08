"""Tests for data contract loading and validation."""

import tempfile
from pathlib import Path
from typing import Any

import pytest
import yaml

from odg_core.contracts.breaking import detect_breaking_changes
from odg_core.contracts.loader import load_contract, load_contracts_from_dir
from odg_core.contracts.validator import validate_data
from odg_core.models import ColumnDefinition, DataContractSchema


def _write_contract(path: Path, data: dict[str, Any]) -> Path:
    file = path / "test_contract.yaml"
    with file.open("w") as f:
        yaml.dump(data, f)
    return file


class TestLoadContract:
    def test_load_valid_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            contract_data = {
                "name": "test_dataset",
                "dataset_id": "test/dataset",
                "domain_id": "test",
                "owner_id": "team-a",
                "schema": {
                    "columns": [
                        {"name": "id", "data_type": "string", "nullable": False},
                        {"name": "value", "data_type": "float", "nullable": True},
                    ],
                    "primary_key": ["id"],
                },
                "sla": {"freshness_hours": 24, "completeness_threshold": 0.9},
            }
            path = _write_contract(Path(tmp), contract_data)
            contract = load_contract(path)

            assert contract.name == "test_dataset"
            assert contract.dataset_id == "test/dataset"
            assert len(contract.schema_definition.columns) == 2
            assert contract.sla_definition.freshness_hours == 24

    def test_load_missing_file(self) -> None:
        with pytest.raises(FileNotFoundError):
            load_contract("/nonexistent/path.yaml")

    def test_load_invalid_yaml_not_dict(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.yaml"
            path.write_text("- just\n- a\n- list\n")
            with pytest.raises(ValueError, match="YAML mapping"):
                load_contract(path)

    def test_load_contracts_from_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            for name in ["a", "b"]:
                data = {
                    "name": name,
                    "dataset_id": f"{name}/d",
                    "domain_id": name,
                    "owner_id": "o",
                    "schema": {"columns": [{"name": "id", "data_type": "string"}]},
                }
                (Path(tmp) / f"{name}.yaml").write_text(yaml.dump(data))
            contracts = load_contracts_from_dir(tmp)
            assert len(contracts) == 2
            assert contracts[0].name == "a"
            assert contracts[1].name == "b"


class TestValidateData:
    def test_valid_data(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            contract_data = {
                "name": "test",
                "dataset_id": "t/d",
                "domain_id": "t",
                "owner_id": "o",
                "schema": {
                    "columns": [
                        {"name": "id", "data_type": "string"},
                        {"name": "value", "data_type": "float"},
                    ],
                },
            }
            path = _write_contract(Path(tmp), contract_data)
            contract = load_contract(path)

            actual = [{"name": "id", "data_type": "string"}, {"name": "value", "data_type": "float"}]
            result = validate_data(contract, actual)
            assert result["valid"] is True
            assert result["missing_columns"] == []
            assert result["type_mismatches"] == []

    def test_missing_column(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            contract_data = {
                "name": "test",
                "dataset_id": "t/d",
                "domain_id": "t",
                "owner_id": "o",
                "schema": {
                    "columns": [
                        {"name": "id", "data_type": "string"},
                        {"name": "value", "data_type": "float"},
                    ],
                },
            }
            path = _write_contract(Path(tmp), contract_data)
            contract = load_contract(path)

            actual = [{"name": "id", "data_type": "string"}]
            result = validate_data(contract, actual)
            assert result["valid"] is False
            assert "value" in result["missing_columns"]

    def test_type_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            contract_data = {
                "name": "test",
                "dataset_id": "t/d",
                "domain_id": "t",
                "owner_id": "o",
                "schema": {
                    "columns": [{"name": "id", "data_type": "string"}],
                },
            }
            path = _write_contract(Path(tmp), contract_data)
            contract = load_contract(path)

            actual = [{"name": "id", "data_type": "integer"}]
            result = validate_data(contract, actual)
            assert result["valid"] is False
            assert len(result["type_mismatches"]) == 1


class TestBreakingChanges:
    def test_no_changes(self) -> None:
        schema = DataContractSchema(columns=[ColumnDefinition(name="id", data_type="string", nullable=False)])
        result = detect_breaking_changes(schema, schema)
        assert result["has_breaking"] is False

    def test_column_removed_is_breaking(self) -> None:
        old = DataContractSchema(
            columns=[
                ColumnDefinition(name="id", data_type="string"),
                ColumnDefinition(name="name", data_type="string"),
            ]
        )
        new = DataContractSchema(columns=[ColumnDefinition(name="id", data_type="string")])
        result = detect_breaking_changes(old, new)
        assert result["has_breaking"] is True
        assert any(c["type"] == "column_removed" for c in result["breaking_changes"])

    def test_type_change_is_breaking(self) -> None:
        old = DataContractSchema(columns=[ColumnDefinition(name="id", data_type="string")])
        new = DataContractSchema(columns=[ColumnDefinition(name="id", data_type="integer")])
        result = detect_breaking_changes(old, new)
        assert result["has_breaking"] is True
        assert any(c["type"] == "type_changed" for c in result["breaking_changes"])

    def test_nullable_column_added_is_non_breaking(self) -> None:
        old = DataContractSchema(columns=[ColumnDefinition(name="id", data_type="string")])
        new = DataContractSchema(
            columns=[
                ColumnDefinition(name="id", data_type="string"),
                ColumnDefinition(name="notes", data_type="string", nullable=True),
            ]
        )
        result = detect_breaking_changes(old, new)
        assert result["has_breaking"] is False
        assert len(result["non_breaking_changes"]) == 1

    def test_non_nullable_column_added_is_breaking(self) -> None:
        old = DataContractSchema(columns=[ColumnDefinition(name="id", data_type="string")])
        new = DataContractSchema(
            columns=[
                ColumnDefinition(name="id", data_type="string"),
                ColumnDefinition(name="required_field", data_type="string", nullable=False),
            ]
        )
        result = detect_breaking_changes(old, new)
        assert result["has_breaking"] is True
        assert any(c["type"] == "non_nullable_column_added" for c in result["breaking_changes"])

    def test_nullable_to_non_nullable_is_breaking(self) -> None:
        old = DataContractSchema(columns=[ColumnDefinition(name="email", data_type="string", nullable=True)])
        new = DataContractSchema(columns=[ColumnDefinition(name="email", data_type="string", nullable=False)])
        result = detect_breaking_changes(old, new)
        assert result["has_breaking"] is True
        assert any(c["type"] == "nullable_to_non_nullable" for c in result["breaking_changes"])
