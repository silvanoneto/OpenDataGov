"""OpenDataGov CLI main entry point."""

from __future__ import annotations

import asyncio
import sys

import click
from rich.console import Console

from odg_cli.commands import access as access_cmd
from odg_cli.commands import config as config_cmd
from odg_cli.commands import dataset as dataset_cmd
from odg_cli.commands import decision as decision_cmd
from odg_cli.config import ConfigManager

console = Console()


@click.group()
@click.version_option(version="0.1.0", prog_name="odg")
@click.pass_context
def cli(ctx: click.Context) -> None:
    """OpenDataGov command-line interface.

    Manage governance decisions, datasets, and access requests from the command line.
    """
    # Initialize config manager in context
    ctx.ensure_object(dict)
    ctx.obj["config_manager"] = ConfigManager()


# Register command groups
cli.add_command(config_cmd.config)
cli.add_command(decision_cmd.decision)
cli.add_command(dataset_cmd.dataset)
cli.add_command(access_cmd.access)


def run_async(coro):
    """Run an async coroutine in a synchronous context."""
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    return asyncio.run(coro)


if __name__ == "__main__":
    cli()
