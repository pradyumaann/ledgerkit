"""MCP adapter: exposes the tool registry to Claude Desktop, Claude Code and other MCP clients.

Every caller that arrives through MCP is an agent. It can read anything and prepare
drafts, but postings, payments and voids are held for a person to approve in the web
interface or with `ledgerkit tool approve_action`.
"""

import json

import anyio
from mcp import types
from mcp.server import Server
from mcp.server.stdio import stdio_server
from sqlalchemy.orm import Session, sessionmaker

from ledgerkit import __version__
from ledgerkit.tools import Actor, ToolRegistry, registry

MCP_ACTOR = Actor("agent", "mcp")

# Deciding approvals is reserved for people, so these are not offered to agents at all.
HUMAN_ONLY = {"approve_action", "reject_action"}

INSTRUCTIONS = """\
ledgerkit is a company's accounting and sales system. These tools read and change its books.

How to work with it:
- Start with get_company_settings to learn the base currency, the fiscal year and today's date.
- Amounts are decimal strings in the base currency, for example "1250.00". Dates are YYYY-MM-DD.
- Look records up before using them: search_parties for customer and vendor ids, list_items for
  SKUs, list_accounts for account codes, list_tax_rates for tax names.
- Figures from the reporting tools (profit_and_loss, margin_by_customer, ar_aging and so on) are
  computed from posted records. Quote them as given and explain them; do not recalculate them.

What needs a person:
- You can create drafts freely: invoices, bills, quotations and journal entries.
- Anything that changes the books (posting, recording or voiding payments, voiding documents,
  new accounts and tax rates, the lock date) is not run when you call it. It is queued, and the
  result has status "pending_approval". When that happens, tell the user what you requested and
  that it is waiting for their approval in ledgerkit. Do not describe it as done, and do not
  retry it.
- A result with status "error" explains what went wrong and usually how to fix it.
"""


def _annotations(mutating: bool) -> types.ToolAnnotations:
    # open_world_hint is false: every tool acts only on this company's own database.
    return types.ToolAnnotations(read_only_hint=not mutating, destructive_hint=False, open_world_hint=False)


def build_server(session_factory: sessionmaker[Session], reg: ToolRegistry = registry) -> Server:
    async def list_tools(_ctx, _params) -> types.ListToolsResult:
        return types.ListToolsResult(
            tools=[
                types.Tool(
                    name=tool.name,
                    description=tool.description,
                    input_schema=tool.input_model.model_json_schema(),
                    annotations=_annotations(tool.mutating),
                )
                for tool in reg.list()
                if tool.name not in HUMAN_ONLY
            ]
        )

    async def call_tool(_ctx, params: types.CallToolRequestParams) -> types.CallToolResult:
        # The registry is synchronous (it owns a database transaction), so run it off the event loop.
        result = await anyio.to_thread.run_sync(
            reg.call, session_factory, params.name, params.arguments or {}, MCP_ACTOR
        )
        return types.CallToolResult(
            content=[types.TextContent(type="text", text=json.dumps(result, indent=2))],
            is_error=result["status"] == "error",
        )

    return Server(
        "ledgerkit",
        version=__version__,
        title="ledgerkit",
        instructions=INSTRUCTIONS,
        on_list_tools=list_tools,
        on_call_tool=call_tool,
    )


async def serve_stdio(session_factory: sessionmaker[Session]) -> None:
    """Serve over stdin/stdout. Nothing else may write to stdout while this runs."""
    server = build_server(session_factory)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())
