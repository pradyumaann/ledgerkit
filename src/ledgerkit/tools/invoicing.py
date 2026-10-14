"""Sales invoices, vendor bills and payments."""

import datetime as dt
from decimal import Decimal

from pydantic import Field
from sqlalchemy import select

from ledgerkit.models import (
    InvoiceKind,
    InvoiceStatus,
    Payment,
    PaymentAllocation,
    PaymentDirection,
    PaymentStatus,
)
from ledgerkit.money import Minor
from ledgerkit.services import invoicing, lookup, payments
from ledgerkit.tools import serializers
from ledgerkit.tools.common import MONEY_NOTE, InvoiceLineIn, to_doc_lines
from ledgerkit.tools.context import ToolContext
from ledgerkit.tools.registry import ToolInput, registry


class CreateSalesInvoiceDraft(ToolInput):
    customer_id: int = Field(description="Party id of the customer. Find it with search_parties.")
    invoice_date: dt.date | None = Field(None, description="Defaults to today.")
    due_date: dt.date | None = Field(None, description="Defaults to 30 days after the invoice date.")
    lines: list[InvoiceLineIn] = Field(min_length=1)
    reference: str | None = Field(None, description="Customer's purchase order number or similar.")
    notes: str | None = None


@registry.tool(
    name="create_sales_invoice_draft",
    description="Create a sales invoice to a customer as a draft. A draft has no effect on the books or "
    "on what the customer owes until it is posted with post_invoice. " + MONEY_NOTE,
    input_model=CreateSalesInvoiceDraft,
    mutating=True,
)
def create_sales_invoice_draft(ctx: ToolContext, p: CreateSalesInvoiceDraft):
    invoice = invoicing.create_invoice_draft(
        ctx.session,
        kind=InvoiceKind.SALES,
        party=lookup.party(ctx.session, p.customer_id),
        invoice_date=p.invoice_date or ctx.today,
        due_date=p.due_date,
        lines=to_doc_lines(ctx, p.lines),
        reference=p.reference,
        notes=p.notes,
        created_by=ctx.actor.label,
    )
    return serializers.invoice(invoice)


class CreateVendorBillDraft(ToolInput):
    vendor_id: int = Field(description="Party id of the vendor. Find it with search_parties.")
    bill_date: dt.date | None = Field(None, description="Date on the vendor's bill. Defaults to today.")
    due_date: dt.date | None = Field(None, description="Defaults to 30 days after the bill date.")
    lines: list[InvoiceLineIn] = Field(min_length=1)
    reference: str | None = Field(None, description="The vendor's own bill or invoice number.")
    notes: str | None = None


@registry.tool(
    name="create_vendor_bill_draft",
    description="Record a bill received from a vendor as a draft. Each line needs an account_code for "
    "the expense (rent, utilities, software and so on), unless the line is a product item being bought "
    "for stock. Nothing is owed in the books until the bill is posted with post_invoice. " + MONEY_NOTE,
    input_model=CreateVendorBillDraft,
    mutating=True,
)
def create_vendor_bill_draft(ctx: ToolContext, p: CreateVendorBillDraft):
    bill = invoicing.create_invoice_draft(
        ctx.session,
        kind=InvoiceKind.PURCHASE,
        party=lookup.party(ctx.session, p.vendor_id),
        invoice_date=p.bill_date or ctx.today,
        due_date=p.due_date,
        lines=to_doc_lines(ctx, p.lines),
        reference=p.reference,
        notes=p.notes,
        created_by=ctx.actor.label,
    )
    return serializers.invoice(bill)


class InvoiceNumber(ToolInput):
    number: str = Field(description="Invoice or bill number, e.g. 'INV-00007' or 'BILL-00003'.")


@registry.tool(
    name="get_invoice",
    description="Show one sales invoice or vendor bill with its lines, status, amount outstanding "
    "and the payments applied to it.",
    input_model=InvoiceNumber,
)
def get_invoice(ctx: ToolContext, p: InvoiceNumber):
    invoice = lookup.invoice(ctx.session, p.number)
    allocations = ctx.session.scalars(
        select(PaymentAllocation)
        .join(Payment, PaymentAllocation.payment_id == Payment.id)
        .where(PaymentAllocation.invoice_id == invoice.id, Payment.status == PaymentStatus.POSTED)
        .order_by(Payment.payment_date, Payment.id)
    )
    return {
        **serializers.invoice(invoice),
        "journal_entry_number": invoice.journal_entry.number if invoice.journal_entry else None,
        "payments": [
            {
                "number": a.payment.number,
                "payment_date": a.payment.payment_date,
                "amount": Minor(a.amount),
                "method": a.payment.method,
            }
            for a in allocations
        ],
    }


class ListInvoices(ToolInput):
    kind: InvoiceKind | None = Field(
        None, description="'sales' for invoices to customers, 'purchase' for vendor bills."
    )
    status: InvoiceStatus | None = None
    party_id: int | None = None
    unpaid_only: bool = Field(False, description="Only posted documents that still have an amount outstanding.")
    date_from: dt.date | None = None
    date_to: dt.date | None = None
    limit: int = Field(50, ge=1, le=500)


@registry.tool(
    name="list_invoices",
    description="List sales invoices and vendor bills, newest first, without their lines. "
    "Use get_invoice for the detail of one document.",
    input_model=ListInvoices,
)
def list_invoices(ctx: ToolContext, p: ListInvoices):
    found = invoicing.list_invoices(
        ctx.session,
        kind=p.kind,
        status=p.status,
        party_id=p.party_id,
        unpaid_only=p.unpaid_only,
        date_from=p.date_from,
        date_to=p.date_to,
        limit=p.limit,
    )
    return {"invoices": [serializers.invoice_summary(i) for i in found], "truncated": len(found) == p.limit}


@registry.tool(
    name="post_invoice",
    description="Post a draft sales invoice or vendor bill to the ledger. From then on it counts as "
    "revenue or expense and as money owed. A posted document cannot be edited, only voided.",
    input_model=InvoiceNumber,
    mutating=True,
    requires_approval=True,
)
def post_invoice(ctx: ToolContext, p: InvoiceNumber):
    invoice = lookup.invoice(ctx.session, p.number)
    return serializers.invoice(invoicing.post_invoice(ctx.session, invoice, created_by=ctx.actor.label))


class VoidInvoice(ToolInput):
    number: str
    void_date: dt.date | None = Field(
        None,
        description="Date of the reversing entry for a posted document. Defaults to the document's own "
        "date; give a later date if that period is locked.",
    )


@registry.tool(
    name="void_invoice",
    description="Cancel a sales invoice or vendor bill. A draft is simply cancelled; a posted document "
    "is reversed in the ledger. A document with payments applied cannot be voided until those payments "
    "are voided.",
    input_model=VoidInvoice,
    mutating=True,
    requires_approval=True,
)
def void_invoice(ctx: ToolContext, p: VoidInvoice):
    invoice = lookup.invoice(ctx.session, p.number)
    return serializers.invoice(
        invoicing.void_invoice(ctx.session, invoice, void_date=p.void_date, created_by=ctx.actor.label)
    )


class AllocationIn(ToolInput):
    invoice_number: str
    amount: Decimal = Field(gt=0)


class RecordPayment(ToolInput):
    direction: PaymentDirection = Field(
        description="'inbound' for money received from a customer, 'outbound' for money paid to a vendor."
    )
    party_id: int
    amount: Decimal = Field(gt=0)
    payment_date: dt.date | None = Field(None, description="Defaults to today.")
    bank_account_code: str | None = Field(
        None, description="Bank or cash account the money moved through. Defaults to the main bank account."
    )
    allocations: list[AllocationIn] | None = Field(
        None,
        description="Which invoices or bills this payment settles. If omitted, the amount is applied to "
        "the party's oldest open documents first. Pass an empty list to record it as an unallocated advance.",
    )
    method: str | None = Field(None, description="e.g. 'bank transfer', 'card', 'cash', 'cheque'.")
    reference: str | None = Field(None, description="Bank reference or cheque number.")


@registry.tool(
    name="record_payment",
    description="Record money received from a customer or paid to a vendor and apply it to their open "
    "invoices or bills. The payment is posted to the ledger immediately. " + MONEY_NOTE,
    input_model=RecordPayment,
    mutating=True,
    requires_approval=True,
)
def record_payment(ctx: ToolContext, p: RecordPayment):
    allocations = None
    if p.allocations is not None:
        allocations = [(lookup.invoice(ctx.session, a.invoice_number), ctx.minor(a.amount)) for a in p.allocations]
    payment = payments.record_payment(
        ctx.session,
        direction=p.direction,
        party=lookup.party(ctx.session, p.party_id),
        payment_date=p.payment_date or ctx.today,
        amount=ctx.minor(p.amount),
        bank_account=lookup.account(ctx.session, p.bank_account_code) if p.bank_account_code else None,
        allocations=allocations,
        method=p.method,
        reference=p.reference,
        created_by=ctx.actor.label,
    )
    return serializers.payment(payment)


class VoidPayment(ToolInput):
    payment_number: str = Field(description="e.g. 'RCPT-00004' or 'PAY-00002'.")
    void_date: dt.date | None = Field(None, description="Date of the reversing entry. Defaults to the payment date.")


@registry.tool(
    name="void_payment",
    description="Cancel a recorded payment, for example one entered by mistake or a bounced cheque. "
    "The ledger entry is reversed and the invoices it settled become outstanding again.",
    input_model=VoidPayment,
    mutating=True,
    requires_approval=True,
)
def void_payment(ctx: ToolContext, p: VoidPayment):
    payment = lookup.payment(ctx.session, p.payment_number)
    return serializers.payment(
        payments.void_payment(ctx.session, payment, void_date=p.void_date, created_by=ctx.actor.label)
    )


class ListPayments(ToolInput):
    direction: PaymentDirection | None = None
    party_id: int | None = None
    status: PaymentStatus | None = None
    date_from: dt.date | None = None
    date_to: dt.date | None = None
    limit: int = Field(50, ge=1, le=500)


@registry.tool(
    name="list_payments",
    description="List customer receipts and vendor payments, newest first, with the documents each one settled.",
    input_model=ListPayments,
)
def list_payments(ctx: ToolContext, p: ListPayments):
    stmt = select(Payment).order_by(Payment.payment_date.desc(), Payment.id.desc()).limit(p.limit)
    if p.direction:
        stmt = stmt.where(Payment.direction == p.direction)
    if p.party_id is not None:
        stmt = stmt.where(Payment.party_id == p.party_id)
    if p.status:
        stmt = stmt.where(Payment.status == p.status)
    if p.date_from is not None:
        stmt = stmt.where(Payment.payment_date >= p.date_from)
    if p.date_to is not None:
        stmt = stmt.where(Payment.payment_date <= p.date_to)
    found = list(ctx.session.scalars(stmt))
    return {"payments": [serializers.payment(x) for x in found], "truncated": len(found) == p.limit}
