"""Metadata rule model and YAML loader (ADR-042)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class MetadataRule(BaseModel):
    """A declarative metadata rule: trigger -> condition -> action."""

    name: str
    trigger: str  # e.g. "on_ingest", "on_promotion", "scheduled"
    condition: str  # e.g. "column matches cpf|ssn|email"
    action: str  # e.g. "set_pii=true", "add_tag=sensitive"
    auto_approve: bool = Field(default=False)
    description: str = Field(default="")


def load_rules(path: str | Path) -> list[MetadataRule]:
    """Load metadata rules from a YAML file."""
    file_path = Path(path)
    if not file_path.exists():
        return []

    with file_path.open() as f:
        data: dict[str, Any] = yaml.safe_load(f)

    rules_raw = data.get("rules", [])
    return [MetadataRule(**r) for r in rules_raw]
