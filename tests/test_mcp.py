"""The MCP adapter, exercised through a real MCP client connected in-process."""

import asyncio
import json

import pytest

pytest.importorskip("mcp")

from mcp import Client  # noqa: E402

from ledgerkit.adapters.mcp_server import HUMAN_ONLY, build_server  # noqa: E402
from ledgerkit.tools import registry  # noqa: E402
from tests.conftest import AGENT  # noqa: E402


def run(session_factory, scenario):
    async def main():
        async with Client(build_server(session_factory)) as client:
            return await scenario(client)

    return asyncio.run(main())


def payload(result) -> dict:
    return json.loads(result.content[0].text)


def test_lists_every_tool_except_the_human_only_ones(session_factory):
    async def scenario(client):
        return client.instructions, (await client.list_tools()).tools

    instructions, tools = run(session_factory, scenario)
    names = {tool.name for tool in tools}
    assert names == {tool.name for tool in registry.list()} - HUMAN_ONLY
    assert not names & {"approve_action", "reject_action"}
    assert "pending_approval" in instructions

    by_name = {tool.name: tool for tool in tools}
    assert by_name["profit_and_loss"].annotations.read_only_hint is True
    assert by_name["post_invoice"].annotations.read_only_hint is False
    assert by_name["create_customer"].input_schema["required"] == ["name"]
    assert len(by_name["margin_by_customer"].description) > 30


def test_agent_can_read_and_draft_but_posting_is_held(session_factory, call):
    async def scenario(client):
        customer = payload(await client.call_tool("create_customer", {"name": "Acme"}))
        draft = payload(
            await client.call_tool(
                "create_sales_invoice_draft",
                {
                    "customer_id": customer["data"]["id"],
                    "lines": [{"description": "Consulting", "unit_price": "400.00"}],
                },
            )
        )
        held = await client.call_tool("post_invoice", {"number": draft["data"]["number"]})
        report = payload(await client.call_tool("trial_balance", {}))
        return draft, held, report

    draft, held, report = run(session_factory, scenario)
    assert draft["status"] == "ok" and draft["data"]["status"] == "draft"
    assert held.is_error is False
    assert payload(held)["status"] == "pending_approval"
    assert report["data"]["accounts"] == []  # nothing reached the ledger

    # The person approves outside MCP, and only then is it posted.
    pending = call("list_pending_approvals")["actions"]
    assert [(a["tool"], a["requested_by"]) for a in pending] == [("post_invoice", "agent:mcp")]
    assert call("approve_action", action_id=pending[0]["id"])["result"]["status"] == "posted"


def test_agent_cannot_approve_even_by_calling_the_hidden_tool(session_factory, raw_call):
    held = raw_call("set_lock_date", _actor=AGENT, lock_date="2026-01-31")
    action_id = held["data"]["pending_action_id"]

    async def scenario(client):
        return await client.call_tool("approve_action", {"action_id": action_id})

    result = run(session_factory, scenario)
    assert result.is_error is True
    assert payload(result)["error"]["code"] == "forbidden"


def test_errors_are_marked_and_explain_how_to_recover(session_factory):
    async def scenario(client):
        missing = await client.call_tool("get_invoice", {"number": "INV-404"})
        invalid = await client.call_tool("create_customer", {})
        unknown = await client.call_tool("no_such_tool", {})
        return missing, invalid, unknown

    missing, invalid, unknown = run(session_factory, scenario)
    assert missing.is_error and "list_invoices" in payload(missing)["error"]["message"]
    assert invalid.is_error and payload(invalid)["error"]["code"] == "invalid_input"
    assert unknown.is_error and payload(unknown)["error"]["code"] == "unknown_tool"
