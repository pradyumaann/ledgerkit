"""Where the profit comes from: by item, by customer, over time, and against costs."""

import datetime as dt
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ledgerkit.analysis.statements import profit_and_loss
from ledgerkit.models import (
    Account,
    AccountSubtype,
    AccountType,
    EntryStatus,
    Invoice,
    InvoiceKind,
    InvoiceLine,
    InvoiceStatus,
    Item,
    JournalEntry,
    JournalLine,
    Party,
)
from ledgerkit.money import Minor, pct, trim
from ledgerkit.services.company import get_company


def _posted_sales_lines(date_from: dt.date, date_to: dt.date):
    return (
        Invoice.kind == InvoiceKind.SALES,
        Invoice.status == InvoiceStatus.POSTED,
        Invoice.invoice_date >= date_from,
        Invoice.invoice_date <= date_to,
    )


def _margin_report(session: Session, rows: list[dict], date_from: dt.date, date_to: dt.date) -> dict:
    rows.sort(key=lambda r: r["gross_margin"], reverse=True)
    revenue = sum(r["revenue"] for r in rows)
    cost = sum(r["cost"] for r in rows)
    for r in rows:
        r["share_of_revenue_pct"] = pct(r["revenue"], revenue)
    return {
        "period": {"from": date_from, "to": date_to},
        "currency": get_company(session).base_currency,
        "rows": rows,
        "total_revenue": Minor(revenue),
        "total_cost": Minor(cost),
        "total_gross_margin": Minor(revenue - cost),
        "gross_margin_pct": pct(revenue - cost, revenue),
        "basis": "Posted sales invoices, excluding tax. Cost is each product's standard cost when the "
        "invoice line was created; services carry no cost here.",
    }


def margin_by_item(session: Session, date_from: dt.date, date_to: dt.date) -> dict:
    stmt = (
        select(
            Item.sku,
            Item.name,
            Item.kind,
            func.sum(InvoiceLine.quantity),
            func.sum(InvoiceLine.line_subtotal),
            func.sum(InvoiceLine.cost_total),
        )
        .select_from(InvoiceLine)
        .join(Invoice, InvoiceLine.invoice_id == Invoice.id)
        .outerjoin(Item, InvoiceLine.item_id == Item.id)
        .where(*_posted_sales_lines(date_from, date_to))
        .group_by(Item.id, Item.sku, Item.name, Item.kind)
    )
    rows = []
    for sku, name, kind, quantity, revenue, cost in session.execute(stmt):
        revenue, cost = int(revenue or 0), int(cost or 0)
        rows.append(
            {
                "sku": sku,
                "name": name or "(lines without an item)",
                "kind": kind,
                "quantity": trim(Decimal(quantity or 0)),
                "revenue": Minor(revenue),
                "cost": Minor(cost),
                "gross_margin": Minor(revenue - cost),
                "gross_margin_pct": pct(revenue - cost, revenue),
            }
        )
    return _margin_report(session, rows, date_from, date_to)


def margin_by_customer(session: Session, date_from: dt.date, date_to: dt.date) -> dict:
    stmt = (
        select(
            Party.id,
            Party.name,
            func.count(func.distinct(Invoice.id)),
            func.sum(InvoiceLine.line_subtotal),
            func.sum(InvoiceLine.cost_total),
        )
        .select_from(InvoiceLine)
        .join(Invoice, InvoiceLine.invoice_id == Invoice.id)
        .join(Party, Invoice.party_id == Party.id)
        .where(*_posted_sales_lines(date_from, date_to))
        .group_by(Party.id, Party.name)
    )
    rows = []
    for party_id, name, invoice_count, revenue, cost in session.execute(stmt):
        revenue, cost = int(revenue or 0), int(cost or 0)
        rows.append(
            {
                "party_id": party_id,
                "name": name,
                "invoice_count": invoice_count,
                "revenue": Minor(revenue),
                "cost": Minor(cost),
                "gross_margin": Minor(revenue - cost),
                "gross_margin_pct": pct(revenue - cost, revenue),
            }
        )
    return _margin_report(session, rows, date_from, date_to)


def _months(date_from: dt.date, date_to: dt.date) -> list[str]:
    months, year, month = [], date_from.year, date_from.month
    while (year, month) <= (date_to.year, date_to.month):
        months.append(f"{year:04d}-{month:02d}")
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return months


def revenue_trend(session: Session, date_from: dt.date, date_to: dt.date) -> dict:
    """Monthly revenue, cost of goods sold, operating expenses and profit from the ledger."""
    stmt = (
        select(
            JournalEntry.entry_date,
            Account.type,
            Account.subtype,
            func.sum(JournalLine.debit),
            func.sum(JournalLine.credit),
        )
        .select_from(JournalLine)
        .join(JournalEntry, JournalLine.entry_id == JournalEntry.id)
        .join(Account, JournalLine.account_id == Account.id)
        .where(
            JournalEntry.status == EntryStatus.POSTED,
            JournalEntry.entry_date >= date_from,
            JournalEntry.entry_date <= date_to,
            Account.type.in_([AccountType.INCOME, AccountType.EXPENSE]),
        )
        .group_by(JournalEntry.entry_date, Account.type, Account.subtype)
    )
    buckets = {m: {"revenue": 0, "cogs": 0, "opex": 0} for m in _months(date_from, date_to)}
    for entry_date, type_, subtype, debit, credit in session.execute(stmt):
        bucket = buckets[f"{entry_date.year:04d}-{entry_date.month:02d}"]
        debit, credit = int(debit or 0), int(credit or 0)
        if type_ == AccountType.INCOME:
            bucket["revenue"] += credit - debit
        elif subtype == AccountSubtype.COGS:
            bucket["cogs"] += debit - credit
        else:
            bucket["opex"] += debit - credit
    months = []
    for month, b in buckets.items():
        gross = b["revenue"] - b["cogs"]
        net = gross - b["opex"]
        months.append(
            {
                "month": month,
                "revenue": Minor(b["revenue"]),
                "cost_of_goods_sold": Minor(b["cogs"]),
                "gross_profit": Minor(gross),
                "gross_margin_pct": pct(gross, b["revenue"]),
                "operating_expenses": Minor(b["opex"]),
                "net_profit": Minor(net),
                "net_margin_pct": pct(net, b["revenue"]),
            }
        )
    return {
        "period": {"from": date_from, "to": date_to},
        "currency": get_company(session).base_currency,
        "months": months,
        "note": "The first and last month are partial if the period does not start and end on month boundaries.",
    }


def expense_breakdown(session: Session, date_from: dt.date, date_to: dt.date) -> dict:
    statement = profit_and_loss(session, date_from, date_to)
    rows = [
        {**row, "category": category}
        for category, key in (("cost_of_goods_sold", "cost_of_goods_sold"), ("operating", "operating_expenses"))
        for row in statement[key]["accounts"]
    ]
    total = sum(r["amount"] for r in rows)
    revenue = statement["revenue"]["total"]
    for r in rows:
        r["share_of_expenses_pct"] = pct(r["amount"], total)
        r["pct_of_revenue"] = pct(r["amount"], revenue)
    rows.sort(key=lambda r: r["amount"], reverse=True)
    return {
        "period": statement["period"],
        "currency": statement["currency"],
        "expenses": rows,
        "total_expenses": Minor(total),
        "total_revenue": Minor(revenue),
    }


def break_even(session: Session, date_from: dt.date, date_to: dt.date) -> dict:
    statement = profit_and_loss(session, date_from, date_to)
    revenue = int(statement["revenue"]["total"])
    variable = int(statement["cost_of_goods_sold"]["total"])
    fixed = int(statement["operating_expenses"]["total"])
    contribution = revenue - variable
    break_even_revenue = None
    if revenue and contribution > 0:
        # fixed / (contribution / revenue), rounded up to a whole minor unit
        break_even_revenue = -(-fixed * revenue // contribution)
    return {
        "period": statement["period"],
        "currency": statement["currency"],
        "revenue": Minor(revenue),
        "variable_costs": Minor(variable),
        "contribution_margin": Minor(contribution),
        "contribution_margin_pct": pct(contribution, revenue),
        "fixed_costs": Minor(fixed),
        "break_even_revenue": None if break_even_revenue is None else Minor(break_even_revenue),
        "margin_of_safety": None if break_even_revenue is None else Minor(revenue - break_even_revenue),
        "margin_of_safety_pct": None if break_even_revenue is None else pct(revenue - break_even_revenue, revenue),
        "net_profit": statement["net_profit"],
        "assumptions": "Cost of goods sold is treated as the only variable cost and every operating "
        "expense as fixed for the period. break_even_revenue is null when there is no revenue or the "
        "contribution margin is not positive.",
    }
