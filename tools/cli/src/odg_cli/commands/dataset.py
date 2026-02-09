"""Dataset commands."""

from __future__ import annotations

import asyncio

import click
from odg_sdk import OpenDataGovClient
from rich.console import Console
from rich.table import Table

console = Console()


@click.group()
def dataset() -> None:
    """Manage datasets."""


@click.command("list")
@click.option("--layer", help="Filter by layer")
@click.option("--domain", "domain_id", help="Filter by domain")
@click.option("--limit", default=50, help="Max results")
@click.pass_context
def dataset_list(
    ctx: click.Context,
    layer: str | None,
    domain_id: str | None,
    limit: int,
) -> None:
    """List datasets.

    Example:
        odg dataset list --layer gold --limit 10
    """
    config_manager = ctx.obj["config_manager"]
    config = config_manager.load()

    async def _list():
        async with OpenDataGovClient(config.api_url, config.api_key) as client:
            return await client.datasets.list(
                domain_id=domain_id,
                layer=layer,
                limit=limit,
            )

    datasets = asyncio.run(_list())

    table = Table(title="Datasets")
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="white")
    table.add_column("Layer", style="blue")
    table.add_column("Classification", style="yellow")
    table.add_column("Quality Score", style="green")

    for d in datasets:
        quality = f"{d.get('qualityScore', 0):.2f}" if d.get("qualityScore") else "N/A"
        table.add_row(
            d.get("id", ""),
            d.get("name", ""),
            d.get("layer", ""),
            d.get("classification", ""),
            quality,
        )

    console.print(table)
    console.print(f"\nShowing {len(datasets)} datasets")


@click.command("search")
@click.argument("query")
@click.option("--domain", help="Filter by domain")
@click.option("--layer", help="Filter by layer")
@click.option("--limit", default=20, help="Max results")
@click.pass_context
def dataset_search(
    ctx: click.Context,
    query: str,
    domain: str | None,
    layer: str | None,
    limit: int,
) -> None:
    """Search datasets.

    Example:
        odg dataset search customer --domain crm
    """
    config_manager = ctx.obj["config_manager"]
    config = config_manager.load()

    async def _search():
        async with OpenDataGovClient(config.api_url, config.api_key) as client:
            return await client.datasets.search(
                query=query,
                domain=domain,
                layer=layer,
                limit=limit,
            )

    results = asyncio.run(_search())

    table = Table(title=f"Search Results: '{query}'")
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="white")
    table.add_column("Description", style="dim")
    table.add_column("Layer", style="blue")

    for r in results:
        desc = r.get("description", "")
        if len(desc) > 50:
            desc = desc[:47] + "..."
        table.add_row(
            r.get("dataset_id", ""),
            r.get("name", ""),
            desc,
            r.get("layer", ""),
        )

    console.print(table)
    console.print(f"\nFound {len(results)} datasets")


# Add commands to group
dataset.add_command(dataset_list)
dataset.add_command(dataset_search)
