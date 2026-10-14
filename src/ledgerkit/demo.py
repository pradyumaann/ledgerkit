"""Demo data: six months of a small trading and services business.

Everything is created through the tool registry, exactly as a user or agent would,
so this also serves as a worked example of the tool layer.
"""

import datetime as dt
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from ledgerkit.errors import DomainError
from ledgerkit.models import Party
from ledgerkit.tools import Actor, registry

MONTHS = 6
ACTOR = Actor("user", "demo")


def _month_start(today: dt.date, months_back: int) -> dt.date:
    index = today.year * 12 + today.month - 1 - months_back
    return dt.date(index // 12, index % 12 + 1, 1)


def seed_demo_data(session_factory: sessionmaker[Session], today: dt.date | None = None) -> dict:
    today = today or dt.date.today()
    with session_factory() as session:
        if session.scalar(select(func.count()).select_from(Party)):
            raise DomainError(
                "not_empty", "The database already has data. Demo data can only be added to an empty one."
            )

    def call(tool: str, **payload):
        payload = {k: (v.isoformat() if isinstance(v, dt.date) else v) for k, v in payload.items()}
        result = registry.call(session_factory, tool, payload, ACTOR)
        if result["status"] != "ok":
            raise DomainError("demo_failed", f"{tool} failed: {result['error']['message']}")
        return result["data"]

    tax = call("create_tax_rate", name="Sales Tax 10%", rate_pct=10)["name"]
    call("create_item", sku="WIDGET", name="Widget", kind="product", sale_price=120, standard_cost=70, tax_rate=tax)
    call("create_item", sku="GADGET", name="Gadget", kind="product", sale_price=300, standard_cost=210, tax_rate=tax)
    call(
        "create_item",
        sku="CONSULT",
        name="Consulting hour",
        kind="service",
        sale_price=150,
        income_account_code="4100",
        tax_rate=tax,
    )
    call(
        "create_item",
        sku="SUPPORT",
        name="Monthly support plan",
        kind="service",
        sale_price=500,
        income_account_code="4100",
        tax_rate=tax,
    )

    customer = {
        name: call("create_customer", name=name)["id"]
        for name in ("Acme Corp", "Globex Ltd", "Initech", "Umbrella Retail")
    }
    vendor = {
        name: call("create_vendor", name=name)["id"]
        for name in ("Parts Supply Co", "Cityside Properties", "CloudHost Inc", "Brightside Media")
    }

    def journal(on: dt.date, memo: str, debit: str, credit: str, amount: int) -> None:
        entry = call(
            "create_journal_entry_draft",
            entry_date=on,
            memo=memo,
            lines=[{"account_code": debit, "debit": amount}, {"account_code": credit, "credit": amount}],
        )
        call("post_journal_entry", entry_number=entry["number"])

    def bill(vendor_name: str, on: dt.date, lines: list[dict], pay_on: dt.date) -> None:
        if on > today:
            return
        doc = call("create_vendor_bill_draft", vendor_id=vendor[vendor_name], bill_date=on, lines=lines)
        call("post_invoice", number=doc["number"])
        if pay_on <= today:
            call(
                "record_payment",
                direction="outbound",
                party_id=vendor[vendor_name],
                amount=doc["total"],
                payment_date=pay_on,
                allocations=[{"invoice_number": doc["number"], "amount": doc["total"]}],
            )

    def invoice(
        customer_name: str, on: dt.date, lines: list[dict], pay_on: dt.date | None, pay_half: bool = False
    ) -> None:
        if on > today:
            return
        doc = call("create_sales_invoice_draft", customer_id=customer[customer_name], invoice_date=on, lines=lines)
        call("post_invoice", number=doc["number"])
        if pay_on is not None and pay_on <= today:
            amount = Decimal(doc["total"])
            if pay_half:
                amount = (amount / 2).quantize(Decimal("0.01"))
            call(
                "record_payment",
                direction="inbound",
                party_id=customer[customer_name],
                amount=str(amount),
                payment_date=pay_on,
                method="bank transfer",
                allocations=[{"invoice_number": doc["number"], "amount": str(amount)}],
            )

    def expense(description: str, account_code: str, amount: int) -> dict:
        return {"description": description, "account_code": account_code, "unit_price": amount, "tax_rate": "none"}

    start = _month_start(today, MONTHS - 1)
    journal(start, "Owner's initial investment", "1000", "3000", 60000)

    for i in range(MONTHS):
        first = _month_start(today, MONTHS - 1 - i)

        def day(n: int, first=first) -> dt.date:
            return first + dt.timedelta(days=n - 1)

        bill("Cityside Properties", day(1), [expense("Office rent", "6100", 1500)], day(5))
        bill(
            "Parts Supply Co",
            day(2),
            [{"item_sku": "WIDGET", "quantity": 60 + 10 * i}, {"item_sku": "GADGET", "quantity": 15 + 3 * i}],
            day(2) + dt.timedelta(days=30),
        )
        bill("CloudHost Inc", day(3), [expense("Hosting and software", "6400", 400)], day(10))
        bill("Brightside Media", day(4), [expense("Advertising", "6300", 600 + 150 * i)], day(20))
        if day(28) <= today:
            journal(day(28), "Monthly salaries", "6000", "1000", 4500)

        invoice(
            "Acme Corp",
            day(6),
            [{"item_sku": "WIDGET", "quantity": 30 + 6 * i}, {"item_sku": "CONSULT", "quantity": 20}],
            day(6) + dt.timedelta(days=20),
        )
        invoice(
            "Globex Ltd",
            day(12),
            [{"item_sku": "GADGET", "quantity": 8 + 2 * i}, {"item_sku": "SUPPORT", "quantity": 2}],
            day(12) + dt.timedelta(days=35),
        )
        # Initech negotiated a gadget discount and pays only half of each invoice.
        invoice(
            "Initech",
            day(18),
            [{"item_sku": "WIDGET", "quantity": 15}, {"item_sku": "GADGET", "quantity": 3 + i, "unit_price": 260}],
            day(18) + dt.timedelta(days=30),
            pay_half=True,
        )
        # Umbrella buys at a thin margin and stopped paying three months ago.
        invoice(
            "Umbrella Retail",
            day(22),
            [{"item_sku": "WIDGET", "quantity": 10 + 4 * i, "unit_price": 95}],
            day(22) + dt.timedelta(days=25) if i < MONTHS - 3 else None,
        )

    lead_a = call("create_lead", name="Dana Park", company_name="Northwind Traders", source="website")["id"]
    call("create_lead", name="Lee Okafor", company_name="Soylent Foods", source="trade show")
    lead_c = call("create_lead", name="Sam Rivera", company_name="Hooli", source="referral")["id"]
    call(
        "create_opportunity",
        title="Gadget rollout to all branches",
        party_id=customer["Globex Ltd"],
        expected_value=18000,
        stage="negotiation",
        expected_close=today + dt.timedelta(days=21),
    )
    call(
        "create_opportunity",
        title="Support contract",
        lead_id=lead_a,
        expected_value=6000,
        stage="proposal",
        expected_close=today + dt.timedelta(days=45),
    )
    lost = call("create_opportunity", title="Widget bulk order", lead_id=lead_c, expected_value=9000)["id"]
    call("update_opportunity_stage", opportunity_id=lost, stage="lost", lost_reason="Chose a cheaper supplier")
    retainer = call(
        "create_opportunity",
        title="Consulting retainer",
        party_id=customer["Acme Corp"],
        expected_value=7500,
        stage="proposal",
    )["id"]
    quotation = call(
        "create_quotation",
        customer_id=customer["Acme Corp"],
        opportunity_id=retainer,
        quotation_date=today - dt.timedelta(days=20),
        lines=[{"item_sku": "CONSULT", "quantity": 50}],
    )
    order = call(
        "convert_quotation_to_order", quotation_number=quotation["number"], order_date=today - dt.timedelta(days=12)
    )
    retainer_invoice = call(
        "invoice_sales_order", order_number=order["number"], invoice_date=today - dt.timedelta(days=10)
    )
    call("post_invoice", number=retainer_invoice["number"])

    statement = call("profit_and_loss", date_from=start, date_to=today)
    return {
        "period": statement["period"],
        "currency": statement["currency"],
        "revenue": statement["revenue"]["total"],
        "gross_profit": statement["gross_profit"],
        "net_profit": statement["net_profit"],
        "customers": len(customer),
        "vendors": len(vendor),
    }
