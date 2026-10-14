"""Command-line adapter."""

import json
import sys
from pathlib import Path
from typing import Annotated

import typer

from ledgerkit.adapters.schema_export import export_tool_schemas
from ledgerkit.config import get_settings
from ledgerkit.db import make_engine, make_session_factory, run_migrations
from ledgerkit.errors import DomainError
from ledgerkit.services.company import init_company
from ledgerkit.tools import Actor, registry

app = typer.Typer(help="ledgerkit: an open-source ERP core with a tool layer built for Claude.", no_args_is_help=True)


def _session_factory():
    return make_session_factory(make_engine())


def _print(data) -> None:
    typer.echo(json.dumps(data, indent=2, ensure_ascii=False))


@app.command()
def init(
    name: Annotated[str, typer.Option(help="Company name.")] = "My Company",
    currency: Annotated[str, typer.Option(help="Base currency code, e.g. USD, EUR, INR.")] = "USD",
    decimals: Annotated[int, typer.Option(help="Decimal places of the currency (0 for JPY).")] = 2,
    fiscal_start_month: Annotated[int, typer.Option(help="Month the fiscal year starts (1-12).")] = 1,
):
    """Create the database, the company and the default chart of accounts."""
    run_migrations()
    with _session_factory()() as session:
        try:
            company = init_company(
                session,
                name=name,
                base_currency=currency,
                currency_decimals=decimals,
                fiscal_year_start_month=fiscal_start_month,
            )
        except DomainError as exc:
            typer.echo(f"Error: {exc.message}", err=True)
            raise typer.Exit(1) from exc
        session.commit()
        typer.echo(f"Ready: {company.name} ({company.base_currency}) in {get_settings().database_url}")


@app.command("seed-demo")
def seed_demo():
    """Fill an initialised, empty database with six months of demo activity."""
    from ledgerkit.demo import seed_demo_data

    try:
        summary = seed_demo_data(_session_factory())
    except DomainError as exc:
        typer.echo(f"Error: {exc.message}", err=True)
        raise typer.Exit(1) from exc
    _print(summary)


@app.command()
def serve(
    host: Annotated[str, typer.Option()] = "127.0.0.1",
    port: Annotated[int, typer.Option()] = 8000,
):
    """Run the web interface and the REST API. API docs are at /api/docs."""
    import uvicorn

    from ledgerkit.adapters.rest import create_app

    settings = get_settings()
    if not settings.user_token and not settings.agent_token:
        typer.echo(
            "Warning: no API tokens are set, so every caller is treated as a human user. "
            "Set LEDGERKIT_USER_TOKEN and LEDGERKIT_AGENT_TOKEN before exposing this beyond your machine.",
            err=True,
        )
    uvicorn.run(create_app(settings=settings), host=host, port=port)


@app.command()
def mcp():
    """Run the MCP server on stdin/stdout, for Claude Desktop, Claude Code and other MCP clients."""
    try:
        import anyio

        from ledgerkit.adapters.mcp_server import serve_stdio
    except ImportError as exc:
        typer.echo('The MCP server needs an extra package. Install it with: pip install "ledgerkit[mcp]"', err=True)
        raise typer.Exit(1) from exc
    # stdout carries the protocol, so this command must never print to it.
    anyio.run(serve_stdio, _session_factory())


@app.command()
def tools():
    """List the available tools."""
    for tool in registry.list():
        flag = "approval" if tool.requires_approval else ("write" if tool.mutating else "read")
        typer.echo(f"{tool.name:32} [{flag:8}] {tool.description}")


@app.command()
def tool(
    name: Annotated[str, typer.Argument(help="Tool name; see `ledgerkit tools`.")],
    json_input: Annotated[str, typer.Option("--json", help="Tool input as a JSON object.")] = "{}",
    input_file: Annotated[
        Path | None, typer.Option("--file", help="Read the JSON input from a file, or '-' for stdin.")
    ] = None,
    actor: Annotated[str, typer.Option(help="'user' or 'agent'. An agent's postings wait for approval.")] = "user",
):
    """Call one tool and print its result as JSON."""
    if actor not in ("user", "agent"):
        raise typer.BadParameter("actor must be 'user' or 'agent'")
    if input_file is not None:
        json_input = sys.stdin.read() if str(input_file) == "-" else input_file.read_text(encoding="utf-8")
    try:
        payload = json.loads(json_input)
    except json.JSONDecodeError as exc:
        raise typer.BadParameter(f"Input is not valid JSON: {exc}") from exc
    result = registry.call(_session_factory(), name, payload, Actor(actor, "cli"))
    _print(result)
    if result["status"] == "error":
        raise typer.Exit(1)


@app.command("export-schemas")
def export_schemas(
    out: Annotated[Path | None, typer.Option(help="Write to this file instead of stdout.")] = None,
):
    """Export every tool as {name, description, input_schema} for the Claude API or an MCP server."""
    text = json.dumps(export_tool_schemas(), indent=2)
    if out is None:
        typer.echo(text)
    else:
        out.write_text(text + "\n", encoding="utf-8")
        typer.echo(f"Wrote {len(registry.list())} tool schemas to {out}")
