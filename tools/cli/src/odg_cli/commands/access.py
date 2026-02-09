"""Access request commands."""

from __future__ import annotations

import asyncio

import click
from odg_sdk import OpenDataGovClient
from rich.console import Console

console = Console()


@click.group()
def access() -> None:
    """Manage access requests."""


@access.command("request")
@click.option("--dataset", "dataset_id", required=True, help="Dataset ID")
@click.option("--requester", "requester_id", required=True, help="Requester user ID")
@click.option("--purpose", required=True, help="Purpose of access")
@click.option("--duration", "duration_days", default=30, help="Access duration in days")
@click.option("--justification", default="", help="Optional justification")
@click.pass_context
def access_request(
    ctx: click.Context,
    dataset_id: str,
    requester_id: str,
    purpose: str,
    duration_days: int,
    justification: str,
) -> None:
    """Request access to a dataset.

    Example:
        odg access request \\
          --dataset gold.customers \\
          --requester analyst-1 \\
          --purpose "Q1 2024 revenue analysis" \\
          --duration 30
    """
    config_manager = ctx.obj["config_manager"]
    config = config_manager.load()

    async def _request():
        async with OpenDataGovClient(config.api_url, config.api_key) as client:
            return await client.access.create(
                dataset_id=dataset_id,
                requester_id=requester_id,
                purpose=purpose,
                duration_days=duration_days,
                justification=justification,
            )

    request = asyncio.run(_request())

    console.print(f"[green]✓[/green] Access request created: {request.request_id}")
    console.print(f"  Dataset:  {request.dataset_id}")
    console.print(f"  Status:   {request.status}")
    console.print(f"  Purpose:  {request.purpose}")

    if request.decision_id:
        console.print(f"  Decision: {request.decision_id}")


@access.command("get")
@click.argument("request_id")
@click.pass_context
def access_get(ctx: click.Context, request_id: str) -> None:
    """Get access request status.

    Example:
        odg access get 123e4567-e89b-12d3-a456-426614174000
    """
    config_manager = ctx.obj["config_manager"]
    config = config_manager.load()

    async def _get():
        async with OpenDataGovClient(config.api_url, config.api_key) as client:
            return await client.access.get(request_id)

    request = asyncio.run(_get())

    console.print(f"\n[bold]Access Request {request.request_id}[/bold]\n")
    console.print(f"Dataset:    {request.dataset_id}")
    console.print(f"Requester:  {request.requester_id}")
    console.print(f"Status:     {request.status}")
    console.print(f"Purpose:    {request.purpose}")
    console.print(f"Created:    {request.created_at}")

    if request.decision_id:
        console.print(f"Decision:   {request.decision_id}")
