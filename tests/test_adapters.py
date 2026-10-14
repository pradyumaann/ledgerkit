import json
import re

import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator
from sqlalchemy import inspect

from ledgerkit.adapters.rest import create_app
from ledgerkit.adapters.schema_export import export_tool_schemas
from ledgerkit.config import Settings
from ledgerkit.db import make_engine, run_migrations
from ledgerkit.models import Base


def test_every_tool_schema_is_valid_and_described():
    schemas = export_tool_schemas()
    assert len(schemas) >= 40
    assert len({s["name"] for s in schemas}) == len(schemas)
    for schema in schemas:
        assert set(schema) == {"name", "description", "input_schema"}
        assert re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", schema["name"])  # Claude API tool-name rule
        assert len(schema["description"]) >= 30, schema["name"]
        assert schema["input_schema"]["type"] == "object"
        Draft202012Validator.check_schema(schema["input_schema"])
    json.dumps(schemas)  # must be serialisable as is


def test_migrations_build_the_same_schema_as_the_models(tmp_path):
    url = f"sqlite:///{(tmp_path / 'migrated.db').as_posix()}"
    run_migrations(url)
    engine = make_engine(url)
    inspector = inspect(engine)
    migrated = set(inspector.get_table_names()) - {"alembic_version"}
    assert migrated == set(Base.metadata.tables)
    for name, table in Base.metadata.tables.items():
        assert {c["name"] for c in inspector.get_columns(name)} == {c.name for c in table.columns}, name
    engine.dispose()


@pytest.fixture
def open_client(session_factory):
    return TestClient(create_app(session_factory, Settings(_env_file=None, user_token=None, agent_token=None)))


@pytest.fixture
def secured_app(session_factory):
    settings = Settings(_env_file=None, user_token="user-secret", agent_token="agent-secret")
    return TestClient(create_app(session_factory, settings))


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_rest_lists_tools_and_documents_each_one(open_client):
    tools = open_client.get("/api/tools").json()
    by_name = {t["name"]: t for t in tools}
    assert by_name["post_invoice"]["requires_approval"] is True
    assert by_name["profit_and_loss"]["mutating"] is False
    paths = open_client.get("/api/openapi.json").json()["paths"]
    assert all(f"/api/tools/{name}" in paths for name in by_name)


def test_rest_end_to_end_flow(open_client):
    def post(tool, **body):
        response = open_client.post(f"/api/tools/{tool}", json=body)
        assert response.status_code == 200, response.text
        return response.json()["data"]

    customer = post("create_customer", name="Acme")
    post("create_item", sku="W", name="Widget", kind="product", sale_price=100, standard_cost=40)
    invoice = post(
        "create_sales_invoice_draft",
        customer_id=customer["id"],
        invoice_date="2026-05-01",
        lines=[{"item_sku": "W", "quantity": 5}],
    )
    post("post_invoice", number=invoice["number"])
    post("record_payment", direction="inbound", party_id=customer["id"], amount=500, payment_date="2026-05-10")
    margins = post("margin_by_customer", date_from="2026-05-01", date_to="2026-05-31")
    assert margins["rows"][0] | {"share_of_revenue_pct": None} == {
        "party_id": customer["id"],
        "name": "Acme",
        "invoice_count": 1,
        "revenue": "500.00",
        "cost": "200.00",
        "gross_margin": "300.00",
        "gross_margin_pct": "60.00",
        "share_of_revenue_pct": None,
    }
    assert post("ar_aging", as_of="2026-05-31")["total_outstanding"] == "0.00"


def test_rest_maps_errors_to_http_status(open_client):
    assert open_client.post("/api/tools/get_invoice", json={"number": "INV-404"}).status_code == 404
    assert open_client.post("/api/tools/no_such_tool", json={}).status_code == 404
    assert open_client.post("/api/tools/create_customer", json={}).status_code == 422
    response = open_client.post("/api/tools/create_customer", json={"name": "Acme"})
    assert response.status_code == 200
    duplicate = open_client.post("/api/tools/create_customer", json={"name": "Acme"})
    assert duplicate.status_code == 400 and duplicate.json()["error"]["code"] == "duplicate"


def test_rest_token_decides_the_actor(secured_app):
    assert secured_app.get("/api/tools").status_code == 401
    assert secured_app.get("/api/tools", headers=_auth("wrong")).status_code == 401
    assert secured_app.get("/api/health").status_code == 200

    customer = secured_app.post("/api/tools/create_customer", json={"name": "Acme"}, headers=_auth("agent-secret"))
    assert customer.status_code == 200
    draft = secured_app.post(
        "/api/tools/create_sales_invoice_draft",
        json={"customer_id": customer.json()["data"]["id"], "lines": [{"description": "Work", "unit_price": 100}]},
        headers=_auth("agent-secret"),
    ).json()["data"]

    held = secured_app.post("/api/tools/post_invoice", json={"number": draft["number"]}, headers=_auth("agent-secret"))
    assert held.status_code == 202 and held.json()["status"] == "pending_approval"
    action_id = held.json()["data"]["pending_action_id"]

    as_agent = secured_app.post(
        "/api/tools/approve_action", json={"action_id": action_id}, headers=_auth("agent-secret")
    )
    assert as_agent.status_code == 403
    as_user = secured_app.post("/api/tools/approve_action", json={"action_id": action_id}, headers=_auth("user-secret"))
    assert as_user.status_code == 200 and as_user.json()["data"]["result"]["status"] == "posted"
