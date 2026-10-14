"""Aged receivables and payables."""

import datetime as dt

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ledgerkit.models import (
    Invoice,
    InvoiceKind,
    InvoiceStatus,
    Party,
    Payment,
    PaymentAllocation,
    PaymentStatus,
)
from ledgerkit.money import Minor
from ledgerkit.services.company import get_company

BUCKETS = ("current", "1_30", "31_60", "61_90", "over_90")


def _bucket(days_overdue: int) -> str:
    if days_overdue <= 0:
        return "current"
    if days_overdue <= 30:
        return "1_30"
    if days_overdue <= 60:
        return "31_60"
    if days_overdue <= 90:
        return "61_90"
    return "over_90"


def aging(session: Session, kind: str, as_of: dt.date) -> dict:
    """Outstanding invoices of one kind as of a date, bucketed by days past due."""
    paid = (
        select(PaymentAllocation.invoice_id, func.sum(PaymentAllocation.amount).label("paid"))
        .join(Payment, PaymentAllocation.payment_id == Payment.id)
        .where(Payment.status == PaymentStatus.POSTED, Payment.payment_date <= as_of)
        .group_by(PaymentAllocation.invoice_id)
        .subquery()
    )
    stmt = (
        select(Invoice, Party.name, func.coalesce(paid.c.paid, 0))
        .join(Party, Invoice.party_id == Party.id)
        .outerjoin(paid, paid.c.invoice_id == Invoice.id)
        .where(Invoice.kind == kind, Invoice.status == InvoiceStatus.POSTED, Invoice.invoice_date <= as_of)
        .order_by(Invoice.due_date, Invoice.id)
    )
    parties: dict[int, dict] = {}
    invoices = []
    totals = dict.fromkeys(BUCKETS, 0)
    for invoice, party_name, paid_amount in session.execute(stmt):
        outstanding = invoice.total - int(paid_amount)
        if outstanding <= 0:
            continue
        days_overdue = (as_of - invoice.due_date).days
        bucket = _bucket(days_overdue)
        totals[bucket] += outstanding
        row = parties.setdefault(
            invoice.party_id,
            {"party_id": invoice.party_id, "name": party_name, **dict.fromkeys(BUCKETS, 0), "total": 0},
        )
        row[bucket] += outstanding
        row["total"] += outstanding
        invoices.append(
            {
                "number": invoice.number,
                "party": party_name,
                "invoice_date": invoice.invoice_date,
                "due_date": invoice.due_date,
                "days_overdue": max(days_overdue, 0),
                "bucket": bucket,
                "outstanding": Minor(outstanding),
            }
        )
    rows = sorted(parties.values(), key=lambda r: r["total"], reverse=True)
    for row in rows:
        for key in (*BUCKETS, "total"):
            row[key] = Minor(row[key])
    grand_total = sum(totals.values())
    return {
        "kind": "receivables" if kind == InvoiceKind.SALES else "payables",
        "as_of": as_of,
        "currency": get_company(session).base_currency,
        "buckets": {key: Minor(value) for key, value in totals.items()},
        "total_outstanding": Minor(grand_total),
        "total_overdue": Minor(grand_total - totals["current"]),
        "by_party": rows,
        "invoices": invoices,
        "note": "Buckets are days past the due date. Invoices that are void today are excluded.",
    }
