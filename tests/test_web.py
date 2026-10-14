"""Serving the web interface, the /api/me endpoint, and the list tools the screens use."""

import pytest
from fastapi.testclient import TestClient

from ledgerkit.adapters.rest import create_app
from ledgerkit.config import Settings
from tests.conftest import AGENT

OPEN = Settings(_env_file=None, user_token=None, agent_token=None)


@pytest.fixture
def built_web(tmp_path):
    dist = tmp_path / "web_dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>app shell</title>", encoding="utf-8")
    (dist / "assets" / "app.js").write_text("console.log('app')", encoding="utf-8")
    (dist / "favicon.svg").write_text("<svg/>", encoding="utf-8")
    return dist


def test_app_shell_is_served_for_root_and_client_routes(session_factory, built_web):
    client = TestClient(create_app(session_factory, OPEN, web_dist=built_web))
    for path in ("/", "/invoices", "/reports/profit-and-loss"):
        response = client.get(path)
        assert response.status_code == 200 and "app shell" in response.text, path
    assert client.get("/assets/app.js").text == "console.log('app')"
    assert client.get("/favicon.svg").text == "<svg/>"


def test_files_outside_the_build_folder_are_never_served(session_factory, built_web):
    (built_web.parent / "secret.txt").write_text("secret", encoding="utf-8")
    client = TestClient(create_app(session_factory, OPEN, web_dist=built_web))
    response = client.get("/..%2Fsecret.txt")
    assert "secret" not in response.text or "app shell" in response.text
    assert response.text != "secret"


def test_unknown_api_path_is_a_json_404_not_the_app_shell(session_factory, built_web):
    client = TestClient(create_app(session_factory, OPEN, web_dist=built_web))
    response = client.get("/api/nothing-here")
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")


def test_hint_page_when_the_web_interface_is_not_built(session_factory, tmp_path):
    client = TestClient(create_app(session_factory, OPEN, web_dist=tmp_path / "missing"))
    response = client.get("/")
    assert response.status_code == 200 and "npm run build" in response.text
    assert client.get("/api/health").json()["status"] == "ok"


def test_me_reports_the_actor(session_factory):
    open_client = TestClient(create_app(session_factory, OPEN))
    assert open_client.get("/api/me").json() == {"actor": "user", "auth_required": False}
    assert open_client.get("/api/me", headers={"X-Ledgerkit-Actor": "agent"}).json()["actor"] == "agent"

    secured = TestClient(
        create_app(session_factory, Settings(_env_file=None, user_token="user-secret", agent_token="agent-secret"))
    )
    assert secured.get("/api/me").status_code == 401
    assert secured.get("/api/me", headers={"Authorization": "Bearer user-secret"}).json() == {
        "actor": "user",
        "auth_required": True,
    }
    assert secured.get("/api/me", headers={"Authorization": "Bearer agent-secret"}).json()["actor"] == "agent"


def test_acting_as_agent_can_only_reduce_rights(session_factory):
    secured = TestClient(
        create_app(session_factory, Settings(_env_file=None, user_token="user-secret", agent_token="agent-secret"))
    )
    # An agent token cannot claim to be a user.
    headers = {"Authorization": "Bearer agent-secret", "X-Ledgerkit-Actor": "user"}
    assert secured.get("/api/me", headers=headers).json()["actor"] == "agent"
    # A user who chooses to act as an agent is held for approval like one.
    headers = {"Authorization": "Bearer user-secret", "X-Ledgerkit-Actor": "agent"}
    held = secured.post("/api/tools/set_lock_date", json={"lock_date": "2026-01-31"}, headers=headers)
    assert held.status_code == 202


def test_list_tools_for_the_screens(call, raw_call, catalogue):
    invoice = call(
        "create_sales_invoice_draft",
        customer_id=catalogue["customer"],
        invoice_date="2026-03-01",
        lines=[{"item_sku": "WIDGET", "quantity": 2}],
    )
    call("post_invoice", number=invoice["number"])
    payment = call(
        "record_payment",
        direction="inbound",
        party_id=catalogue["customer"],
        amount="100.00",
        payment_date="2026-03-05",
    )

    detail = call("get_invoice", number=invoice["number"])
    assert detail["payments"] == [
        {"number": payment["number"], "payment_date": "2026-03-05", "amount": "100.00", "method": None}
    ]
    assert detail["journal_entry_number"].startswith("JE-")

    assert [p["number"] for p in call("list_payments")["payments"]] == [payment["number"]]
    assert call("list_payments", direction="outbound")["payments"] == []

    party = call("get_party", party_id=catalogue["customer"])
    assert (party["receivable"], party["payable"]) == ("120.00", "0.00")  # 220 invoiced, 100 paid

    entries = call("list_journal_entries")["entries"]
    assert [e["source_type"] for e in entries] == ["payment", "invoice"]
    assert "lines" not in entries[0]
    assert call("list_journal_entries", manual_only=True)["entries"] == []

    opportunity = call("create_opportunity", title="Deal", party_id=catalogue["customer"], expected_value=500)
    call("update_opportunity_stage", opportunity_id=opportunity["id"], stage="lost", lost_reason="Price")
    assert [o["customer"] for o in call("list_opportunities")["opportunities"]] == ["Acme"]
    assert call("list_opportunities", open_only=True)["opportunities"] == []

    bank = next(r for r in call("trial_balance", as_of="2026-12-31")["accounts"] if r["code"] == "1000")
    assert bank["subtype"] == "bank"

    raw_call("post_invoice", _actor=AGENT, number="INV-00099")
    log = call("list_audit_log", limit=3)["entries"]
    assert (log[0]["tool"], log[0]["actor"], log[0]["status"]) == ("post_invoice", "agent:test", "pending_approval")
    assert all(e["status"] == "pending_approval" for e in call("list_audit_log", status="pending_approval")["entries"])
