from sqlalchemy import select

from ledgerkit.models import AuditLog
from tests.conftest import AGENT


def _draft_invoice(call, catalogue, actor=None):
    kwargs = {"_actor": actor} if actor else {}
    return call(
        "create_sales_invoice_draft",
        customer_id=catalogue["customer"],
        invoice_date="2026-03-01",
        lines=[{"item_sku": "WIDGET", "quantity": 2}],
        **kwargs,
    )


def test_unknown_tool_lists_the_available_ones(raw_call):
    result = raw_call("no_such_tool")
    assert result["error"]["code"] == "unknown_tool"
    assert "profit_and_loss" in result["error"]["details"]["available"]


def test_invalid_input_names_the_bad_field(raw_call):
    result = raw_call("create_customer", nmae="Typo")
    assert result["error"]["code"] == "invalid_input"
    assert "name" in result["error"]["message"] and "nmae" in result["error"]["message"]


def test_lookup_errors_say_how_to_recover(raw_call):
    result = raw_call("get_ledger", account_code="9999")
    assert result["error"]["code"] == "not_found"
    assert "list_accounts" in result["error"]["message"]


def test_agent_can_draft_but_posting_waits_for_approval(call, raw_call, catalogue):
    invoice = _draft_invoice(call, catalogue, actor=AGENT)
    assert invoice["status"] == "draft"

    held = raw_call("post_invoice", _actor=AGENT, number=invoice["number"])
    assert held["status"] == "pending_approval"
    assert "NOT executed" in held["data"]["message"]
    assert call("get_invoice", number=invoice["number"])["status"] == "draft"
    assert call("trial_balance")["accounts"] == []

    pending = call("list_pending_approvals")["actions"]
    assert [(a["tool"], a["input"], a["requested_by"]) for a in pending] == [
        ("post_invoice", {"number": invoice["number"]}, "agent:test")
    ]

    approved = call("approve_action", action_id=held["data"]["pending_action_id"])
    assert approved["action"]["status"] == "approved"
    assert approved["result"]["status"] == "posted"
    assert call("list_pending_approvals")["actions"] == []


def test_agent_cannot_approve_or_reject(call, raw_call, catalogue):
    invoice = _draft_invoice(call, catalogue, actor=AGENT)
    action_id = raw_call("post_invoice", _actor=AGENT, number=invoice["number"])["data"]["pending_action_id"]
    for tool in ("approve_action", "reject_action"):
        assert raw_call(tool, _actor=AGENT, action_id=action_id)["error"]["code"] == "forbidden"
    assert call("get_invoice", number=invoice["number"])["status"] == "draft"


def test_rejected_action_never_runs(call, raw_call, catalogue):
    invoice = _draft_invoice(call, catalogue, actor=AGENT)
    action_id = raw_call("post_invoice", _actor=AGENT, number=invoice["number"])["data"]["pending_action_id"]
    rejected = call("reject_action", action_id=action_id, reason="Wrong customer")
    assert (rejected["status"], rejected["reason"]) == ("rejected", "Wrong customer")
    assert raw_call("approve_action", action_id=action_id)["error"]["code"] == "invalid_status"
    assert call("get_invoice", number=invoice["number"])["status"] == "draft"


def test_failed_approval_leaves_the_action_pending(call, raw_call):
    action_id = raw_call("post_invoice", _actor=AGENT, number="INV-99999")["data"]["pending_action_id"]
    assert raw_call("approve_action", action_id=action_id)["error"]["code"] == "not_found"
    assert [a["id"] for a in call("list_pending_approvals")["actions"]] == [action_id]


def test_every_approval_gated_tool_is_held_for_an_agent(session_factory):
    from ledgerkit.tools import registry

    gated = [t.name for t in registry.list() if t.requires_approval]
    assert {"post_invoice", "post_journal_entry", "record_payment", "void_invoice", "void_payment"} <= set(gated)
    for tool in registry.list():
        if tool.requires_approval:
            # Input is invalid for most of these, which must be reported before anything is queued.
            result = registry.call(session_factory, tool.name, {}, AGENT)
            assert result["status"] in ("pending_approval", "error")
            assert result["status"] != "ok"


def test_mutations_are_audited_and_reads_are_not(call, raw_call, catalogue, session):
    invoice = _draft_invoice(call, catalogue, actor=AGENT)
    raw_call("post_invoice", _actor=AGENT, number=invoice["number"])
    raw_call("post_invoice", number="INV-99999")
    call("get_invoice", number=invoice["number"])

    rows = session.execute(
        select(AuditLog.tool, AuditLog.actor_type, AuditLog.status).order_by(AuditLog.id.desc()).limit(3)
    ).all()
    assert rows == [
        ("post_invoice", "user", "error"),
        ("post_invoice", "agent", "pending_approval"),
        ("create_sales_invoice_draft", "agent", "ok"),
    ]
    logged = session.scalars(select(AuditLog).where(AuditLog.tool == "create_sales_invoice_draft")).one()
    assert logged.input["customer_id"] == catalogue["customer"]
    assert logged.result["number"] == invoice["number"]


def test_failed_call_changes_nothing(raw_call, call, catalogue):
    # The second line is invalid, so the first must not be saved either.
    result = raw_call(
        "create_sales_invoice_draft",
        customer_id=catalogue["customer"],
        lines=[{"item_sku": "WIDGET"}, {"item_sku": "MISSING"}],
    )
    assert result["error"]["code"] == "not_found"
    assert call("list_invoices")["invoices"] == []


def test_journal_entry_tools(call, raw_call):
    entry = call(
        "create_journal_entry_draft",
        entry_date="2026-03-31",
        memo="Salaries",
        lines=[{"account_code": "6000", "debit": "4500.00"}, {"account_code": "1000", "credit": "4000.00"}],
    )
    assert entry["balanced"] is False
    unbalanced = raw_call("post_journal_entry", entry_number=entry["number"])
    assert unbalanced["error"]["code"] == "unbalanced"
    assert "500.00 USD" in unbalanced["error"]["message"]
    assert call("discard_journal_entry_draft", entry_number=entry["number"]) == {"discarded": entry["number"]}

    entry = call(
        "create_journal_entry_draft",
        entry_date="2026-03-31",
        memo="Salaries",
        lines=[{"account_code": "6000", "debit": "4500.00"}, {"account_code": "1000", "credit": "4500.00"}],
    )
    call("post_journal_entry", entry_number=entry["number"])
    assert raw_call("discard_journal_entry_draft", entry_number=entry["number"])["error"]["code"] == "not_draft"

    ledger = call("get_ledger", account_code="1000", date_from="2026-01-01", date_to="2026-12-31")
    assert (ledger["opening_balance"], ledger["closing_balance"]) == ("0.00", "-4500.00")

    call("reverse_journal_entry", entry_number=entry["number"], reversal_date="2026-04-01")
    assert call("trial_balance", as_of="2026-12-31")["accounts"] == []


def test_lock_date_blocks_posting(call, raw_call, catalogue):
    invoice = _draft_invoice(call, catalogue)
    call("set_lock_date", lock_date="2026-03-31")
    assert raw_call("post_invoice", number=invoice["number"])["error"]["code"] == "period_locked"
    call("set_lock_date", lock_date=None)
    assert call("post_invoice", number=invoice["number"])["status"] == "posted"
