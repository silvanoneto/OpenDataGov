"""CLI configuration management."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic_settings import BaseSettings


class CLIConfig(BaseSettings):
    """CLI configuration."""

    api_url: str = "http://localhost:8000"
    api_key: str | None = None
    timeout: float = 30.0
    output_format: str = "table"  # table, json, yaml

    model_config = {
        "env_prefix": "ODG_",
    }


class ConfigManager:
    """Manage CLI configuration."""

    def __init__(self, config_path: Path | None = None):
        if config_path is None:
            config_path = Path.home() / ".odg" / "config.json"
        self.config_path = config_path
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> CLIConfig:
        """Load configuration from file."""
        if not self.config_path.exists():
            # Return default config
            return CLIConfig()

        with open(self.config_path) as f:
            data = json.load(f)
            return CLIConfig(**data)

    def save(self, config: CLIConfig) -> None:
        """Save configuration to file."""
        with open(self.config_path, "w") as f:
            json.dump(config.model_dump(exclude_none=True), f, indent=2)

    def get(self, key: str) -> Any:
        """Get a configuration value."""
        config = self.load()
        return getattr(config, key, None)

    def set(self, key: str, value: Any) -> None:
        """Set a configuration value."""
        config = self.load()
        setattr(config, key, value)
        self.save(config)

    def delete(self, key: str) -> None:
        """Delete a configuration value (reset to default)."""
        config = self.load()
        if hasattr(config, key):
            setattr(config, key, None)
            self.save(config)
