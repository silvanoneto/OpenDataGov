"""Decision commands."""

from __future__ import annotations

import asyncio

import click
from odg_sdk import OpenDataGovClient
from rich.console import Console
from rich.table import Table

console = Console()


@click.group()
def decision() -> None:
    """Manage governance decisions."""


@decision.command("create")
@click.option("--type", "decision_type", required=True, help="Decision type")
@click.option("--title", required=True, help="Decision title")
@click.option("--description", required=True, help="Decision description")
@click.option("--domain", "domain_id", required=True, help="Domain ID")
@click.option("--created-by", required=True, help="User creating the decision")
@click.pass_context
def decision_create(
    ctx: click.Context,
    decision_type: str,
    title: str,
    description: str,
    domain_id: str,
    created_by: str,
) -> None:
    """Create a new governance decision.

    Example:
        odg decision create \\
          --type data_promotion \\
          --title "Promote sales to Gold" \\
          --description "Quality gates passed" \\
          --domain finance \\
          --created-by user-1
    """
    config_manager = ctx.obj["config_manager"]
    config = config_manager.load()

    async def _create():
        async with OpenDataGovClient(config.api_url, config.api_key) as client:
            decision = await client.decisions.create(
                decision_type=decision_type,
                title=title,
                description=description,
                domain_id=domain_id,
                created_by=created_by,
            )
            return decision

    decision = asyncio.run(_create())
    console.print(f"[green]✓[/green] Decision created: {decision.id}")
    console.print(f"  Status: {decision.status}")


@decision.command("list")
@click.option("--domain", "domain_id", help="Filter by domain")
@click.option("--status", help="Filter by status")
@click.option("--limit", default=10, help="Max results")
@click.pass_context
def decision_list(
    ctx: click.Context,
    domain_id: str | None,
    status: str | None,
    limit: int,
) -> None:
    """List governance decisions.

    Example:
        odg decision list --domain finance --status pending
    """
    config_manager = ctx.obj["config_manager"]
    config = config_manager.load()

    async def _list():
        async with OpenDataGovClient(config.api_url, config.api_key) as client:
            return await client.decisions.list(
                domain_id=domain_id,
                status=status,
                limit=limit,
            )

    decisions = asyncio.run(_list())

    table = Table(title="Governance Decisions")
    table.add_column("ID", style="cyan")
    table.add_column("Title", style="white")
    table.add_column("Type", style="blue")
    table.add_column("Status", style="yellow")
    table.add_column("Domain", style="magenta")

    for d in decisions:
        table.add_row(
            str(d.id)[:8],
            d.title,
            d.decision_type,
            d.status,
            d.domain_id,
        )

    console.print(table)
    console.print(f"\nShowing {len(decisions)} of {len(decisions)} decisions")


@decision.command("get")
@click.argument("decision_id")
@click.pass_context
def decision_get(ctx: click.Context, decision_id: str) -> None:
    """Get decision details.

    Example:
        odg decision get 123e4567-e89b-12d3-a456-426614174000
    """
    config_manager = ctx.obj["config_manager"]
    config = config_manager.load()

    async def _get():
        async with OpenDataGovClient(config.api_url, config.api_key) as client:
            return await client.decisions.get(decision_id)

    decision = asyncio.run(_get())

    console.print(f"\n[bold]Decision {decision.id}[/bold]\n")
    console.print(f"Title:       {decision.title}")
    console.print(f"Type:        {decision.decision_type}")
    console.print(f"Status:      {decision.status}")
    console.print(f"Domain:      {decision.domain_id}")
    console.print(f"Created by:  {decision.created_by}")
    console.print(f"Created at:  {decision.created_at}")

    if decision.metadata:
        console.print("\n[bold]Metadata:[/bold]")
        for key, value in decision.metadata.items():
            console.print(f"  {key}: {value}")


@decision.command("approve")
@click.argument("decision_id")
@click.option("--voter", "voter_id", required=True, help="User casting vote")
@click.option("--vote", default="approve", help="Vote (approve/reject)")
@click.option("--comment", help="Optional comment")
@click.pass_context
def decision_approve(
    ctx: click.Context,
    decision_id: str,
    voter_id: str,
    vote: str,
    comment: str | None,
) -> None:
    """Cast an approval vote.

    Example:
        odg decision approve 123e4567... --voter user-1 --vote approve --comment "LGTM"
    """
    config_manager = ctx.obj["config_manager"]
    config = config_manager.load()

    async def _approve():
        async with OpenDataGovClient(config.api_url, config.api_key) as client:
            return await client.decisions.approve(
                decision_id=decision_id,
                voter_id=voter_id,
                vote=vote,
                comment=comment,
            )

    decision = asyncio.run(_approve())
    console.print(f"[green]✓[/green] Vote cast: {vote}")
    console.print(f"  Decision status: {decision.status}")
