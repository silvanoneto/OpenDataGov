"""Config commands."""

from __future__ import annotations

import click
from rich.console import Console
from rich.table import Table

console = Console()


@click.group()
def config() -> None:
    """Manage CLI configuration."""


@config.command("set")
@click.argument("key")
@click.argument("value")
@click.pass_context
def config_set(ctx: click.Context, key: str, value: str) -> None:
    """Set a configuration value.

    Example:
        odg config set api_url http://localhost:8000
        odg config set api_key sk_your_key_here
    """
    config_manager = ctx.obj["config_manager"]

    # Type conversion for known keys
    if key == "timeout":
        value = float(value)  # type: ignore[assignment]

    config_manager.set(key, value)
    console.print(f"[green]✓[/green] Set {key} = {value}")


@config.command("get")
@click.argument("key")
@click.pass_context
def config_get(ctx: click.Context, key: str) -> None:
    """Get a configuration value.

    Example:
        odg config get api_url
    """
    config_manager = ctx.obj["config_manager"]
    value = config_manager.get(key)

    if value is None:
        console.print(f"[yellow]Configuration key '{key}' not set[/yellow]")
    else:
        console.print(f"{key} = {value}")


@config.command("list")
@click.pass_context
def config_list(ctx: click.Context) -> None:
    """List all configuration values.

    Example:
        odg config list
    """
    config_manager = ctx.obj["config_manager"]
    config = config_manager.load()

    table = Table(title="OpenDataGov Configuration")
    table.add_column("Key", style="cyan")
    table.add_column("Value", style="white")

    for key, value in config.model_dump(exclude_none=True).items():
        # Mask API key for security
        if key == "api_key" and value:
            value = f"{value[:8]}...{value[-4:]}" if len(value) > 12 else "***"
        table.add_row(key, str(value))

    console.print(table)


@config.command("delete")
@click.argument("key")
@click.pass_context
def config_delete(ctx: click.Context, key: str) -> None:
    """Delete a configuration value (reset to default).

    Example:
        odg config delete api_key
    """
    config_manager = ctx.obj["config_manager"]
    config_manager.delete(key)
    console.print(f"[green]✓[/green] Deleted {key}")
